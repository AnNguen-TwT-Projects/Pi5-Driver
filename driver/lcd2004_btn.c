// SPDX-License-Identifier: GPL-2.0
/*
 * lcd2004_btn - Driver LCD2004 (HD44780 qua backpack I2C PCF8574)
 *               + 4 nút nhấn (nút 1 đến 4) cho Raspberry Pi 5.
 *
 * Ba lớp:
 *   1. Truyền I2C : pcf_write() ghi 1 byte xuống PCF8574
 *   2. HD44780    : khởi tạo 4-bit, gửi lệnh/ký tự, định vị con trỏ
 *   3. Linux      : /dev/lcd2004 (write, ioctl, read, poll)
 */

#include <linux/module.h>
#include <linux/i2c.h>
#include <linux/miscdevice.h>
#include <linux/mutex.h>
#include <linux/fs.h>
#include <linux/bits.h>
#include <linux/delay.h>	/* udelay, usleep_range, msleep */
#include <linux/uaccess.h>	/* copy_from_user, copy_to_user */
#include <linux/gpio/consumer.h>	/* gpiod_* */
#include <linux/interrupt.h>	/* devm_request_irq */
#include <linux/workqueue.h>	/* delayed_work */
#include <linux/kfifo.h>	/* hàng đợi sự kiện nút */
#include <linux/wait.h>
#include <linux/poll.h>
#include <linux/spinlock.h>

#include "lcd2004_ioctl.h"	/* LCD_ROWS, LCD_COLS, lệnh ioctl (dùng chung với app) */

/* Bit map PCF8574: P0=RS, P1=RW, P2=E, P3=đèn nền, P4..P7 = D4..D7 */
#define LCD_RS	BIT(0)	/* 0 = lệnh, 1 = dữ liệu (ký tự) */
#define LCD_RW	BIT(1)	/* luôn 0: chỉ ghi, không đọc LCD */
#define LCD_EN	BIT(2)	/* chân Enable, tạo xung để LCD chốt dữ liệu */
#define LCD_BL	BIT(3)	/* đèn nền */

/* Địa chỉ DDRAM đầu mỗi hàng của LCD2004 (thứ tự hàng là 0, 2, 1, 3) */
static const u8 row_addr[LCD_ROWS] = { 0x00, 0x40, 0x14, 0x54 };

#define DEBOUNCE_MS	30	/* chờ 30ms cho tiếp điểm nút hết nảy rồi mới đọc */

struct lcd2004;

/* Trạng thái của một nút nhấn */
struct lcd_btn {
	struct lcd2004 *lcd;
	struct gpio_desc *gpio;
	int irq;
	struct delayed_work work;	/* chạy sau DEBOUNCE_MS kể từ lần ngắt cuối */
	bool pressed;			/* nút đang được giữ? Chỉ work của nút này đụng tới */
	char code;			/* mã gửi cho user-space (LCD_BTN_*) */
};

/* Trạng thái của một LCD (mỗi thiết bị I2C khớp overlay có một bản) */
struct lcd2004 {
	struct i2c_client *client;
	struct miscdevice miscdev;	/* tạo /dev/lcd2004 */
	struct mutex lock;		/* bảo vệ truy cập LCD giữa các tiến trình */
	u8 backlight;			/* LCD_BL nếu bật đèn nền, 0 nếu tắt */
	u8 row, col;			/* vị trí con trỏ hiện tại */

	struct lcd_btn btns[LCD_NUM_BTNS];
	DECLARE_KFIFO(events, char, 16);	/* hàng đợi mã nút đã nhấn */
	spinlock_t fifo_lock;		/* bảo vệ fifo (work ghi, read lấy ra) */
	wait_queue_head_t wq;		/* read()/poll() chờ ở đây */
};

/* Mã sự kiện theo đúng thứ tự trong button-gpios của overlay */
static const char btn_codes[LCD_NUM_BTNS] = {
	LCD_BTN_1, LCD_BTN_2, LCD_BTN_3, LCD_BTN_4
};

/* ===== Lớp 1: truyền I2C ===== */

/* Ghi 1 byte xuống PCF8574, luôn kèm bit đèn nền hiện tại */
static int pcf_write(struct lcd2004 *lcd, u8 data)
{
	return i2c_smbus_write_byte(lcd->client, data | lcd->backlight);
}

/* ===== Lớp 2: HD44780 (chế độ 4-bit) ===== */

/* Gửi 1 nibble (4 bit) kèm xung E để LCD chốt dữ liệu */
static int lcd_write4(struct lcd2004 *lcd, u8 nibble, u8 rs)
{
	u8 data = (nibble << 4) | rs;	/* nibble nằm ở 4 bit cao P4..P7 */
	int ret;

	ret = pcf_write(lcd, data | LCD_EN);	/* E lên 1 */
	if (ret)
		return ret;
	udelay(1);
	ret = pcf_write(lcd, data);		/* E xuống 0: LCD chốt dữ liệu */
	if (ret)
		return ret;
	udelay(50);				/* chờ LCD xử lý xong */
	return 0;
}

/* Gửi 1 byte = nibble cao rồi nibble thấp. rs=0: lệnh, rs=1: ký tự */
static int lcd_send(struct lcd2004 *lcd, u8 byte, u8 rs)
{
	int ret;

	ret = lcd_write4(lcd, byte >> 4, rs);
	if (ret)
		return ret;
	return lcd_write4(lcd, byte & 0x0F, rs);
}

/* Gửi 1 lệnh; xóa màn hình (0x01) và về đầu (0x02) cần chờ lâu hơn */
static int lcd_cmd(struct lcd2004 *lcd, u8 cmd)
{
	int ret = lcd_send(lcd, cmd, 0);

	if (!ret && (cmd == 0x01 || cmd == 0x02))
		usleep_range(2000, 3000);
	return ret;
}

/* Ghi 1 ký tự tại vị trí con trỏ (LCD tự dịch con trỏ sang phải) */
static int lcd_putc(struct lcd2004 *lcd, char c)
{
	int ret = lcd_send(lcd, c, LCD_RS);

	if (!ret)
		lcd->col++;
	return ret;
}

/* Đặt con trỏ tại (row, col): lệnh Set DDRAM Address = 0x80 | địa chỉ */
static int lcd_goto(struct lcd2004 *lcd, u8 row, u8 col)
{
	int ret;

	if (row >= LCD_ROWS || col >= LCD_COLS)
		return -EINVAL;

	ret = lcd_cmd(lcd, 0x80 | (row_addr[row] + col));
	if (ret)
		return ret;
	lcd->row = row;
	lcd->col = col;
	return 0;
}

/* Xuống đầu hàng kế (hàng 3 thì vòng về hàng 0).
 * Phải đặt lại địa chỉ vì DDRAM không nối tiếp theo thứ tự hàng.
 */
static int lcd_newline(struct lcd2004 *lcd)
{
	return lcd_goto(lcd, (lcd->row + 1) % LCD_ROWS, 0);
}

/* Khởi tạo LCD sang chế độ 4-bit theo đúng trình tự datasheet HD44780 */
static int lcd_init(struct lcd2004 *lcd)
{
	static const u8 cmds[] = {
		0x28,	/* 4-bit, 2 dòng logic (LCD2004 dùng chế độ này), font 5x8 */
		0x08,	/* tắt hiển thị */
		0x01,	/* xóa màn hình */
		0x06,	/* con trỏ tự dịch phải khi ghi */
		0x0C,	/* bật hiển thị, không hiện con trỏ */
	};
	int ret, i;

	msleep(50);				/* chờ LCD ổn định sau khi cấp nguồn */

	ret = lcd_write4(lcd, 0x3, 0);		/* 3 lần 0x3: ép LCD về trạng thái biết trước */
	if (ret)
		return ret;
	usleep_range(5000, 6000);
	ret = lcd_write4(lcd, 0x3, 0);
	if (ret)
		return ret;
	udelay(150);
	ret = lcd_write4(lcd, 0x3, 0);
	if (ret)
		return ret;
	ret = lcd_write4(lcd, 0x2, 0);		/* chuyển sang chế độ 4-bit */
	if (ret)
		return ret;

	for (i = 0; i < ARRAY_SIZE(cmds); i++) {
		ret = lcd_cmd(lcd, cmds[i]);
		if (ret)
			return ret;
	}

	lcd->row = 0;
	lcd->col = 0;
	return 0;
}

/* In một chuỗi bắt đầu tại đầu hàng row (dùng cho màn hình chào) */
static int lcd_print_row(struct lcd2004 *lcd, u8 row, const char *s)
{
	int ret = lcd_goto(lcd, row, 0);

	while (!ret && *s)
		ret = lcd_putc(lcd, *s++);
	return ret;
}

/* ===== Lớp 3: giao diện Linux ===== */

/* Lấy struct lcd2004 từ file đang mở.
 * misc_open() đã gán file->private_data = &lcd->miscdev,
 * container_of() lùi từ trường miscdev ra cả struct chứa nó.
 */
static struct lcd2004 *file_to_lcd(struct file *f)
{
	return container_of(f->private_data, struct lcd2004, miscdev);
}

/* write(): chép dữ liệu từ user ra LCD, tự xuống dòng khi đủ 20 cột */
static ssize_t lcd_write(struct file *file, const char __user *ubuf,
			 size_t count, loff_t *ppos)
{
	struct lcd2004 *lcd = file_to_lcd(file);
	char buf[80];			/* chép từng khối 80 byte */
	size_t done = 0, n, i;
	ssize_t ret = count;
	int err;

	mutex_lock(&lcd->lock);		/* giữ khóa suốt cả lần write */

	while (done < count) {
		n = min_t(size_t, count - done, sizeof(buf));
		if (copy_from_user(buf, ubuf + done, n)) {
			ret = -EFAULT;
			goto out;
		}

		for (i = 0; i < n; i++) {
			err = 0;
			if (buf[i] == '\n') {
				err = lcd_newline(lcd);
			} else if (buf[i] >= 0x20 && buf[i] <= 0x7E) {
				/* Hàng đã đủ 20 ký tự: chỉ xuống hàng khi có
				 * ký tự tiếp theo, để 20 ký tự + xuống dòng
				 * (như lệnh echo) không bị nhảy 2 hàng.
				 */
				if (lcd->col >= LCD_COLS)
					err = lcd_newline(lcd);
				if (!err)
					err = lcd_putc(lcd, buf[i]);
			} else {
				continue;	/* ký tự khác: bỏ qua */
			}
			if (err) {
				ret = -EIO;
				goto out;
			}
		}
		done += n;
	}

out:
	mutex_unlock(&lcd->lock);
	return ret;
}

/* ioctl(): xóa màn hình, đặt con trỏ, bật/tắt đèn nền */
static long lcd_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
	struct lcd2004 *lcd = file_to_lcd(file);
	void __user *uarg = (void __user *)arg;
	struct lcd_pos pos;
	int on;
	long ret;

	/* Chép và kiểm tra tham số TRƯỚC khi khóa (copy_from_user có thể ngủ) */
	switch (cmd) {
	case LCD_IOC_CLEAR:
		break;
	case LCD_IOC_SET_CURSOR:
		if (copy_from_user(&pos, uarg, sizeof(pos)))
			return -EFAULT;
		if (pos.row >= LCD_ROWS || pos.col >= LCD_COLS)
			return -EINVAL;
		break;
	case LCD_IOC_BACKLIGHT:
		if (copy_from_user(&on, uarg, sizeof(on)))
			return -EFAULT;
		break;
	default:
		return -ENOTTY;		/* lệnh lạ */
	}

	mutex_lock(&lcd->lock);
	switch (cmd) {
	case LCD_IOC_CLEAR:
		ret = lcd_cmd(lcd, 0x01);	/* 0x01 tự đưa địa chỉ về 0 */
		if (!ret) {
			lcd->row = 0;
			lcd->col = 0;
		}
		break;
	case LCD_IOC_SET_CURSOR:
		ret = lcd_goto(lcd, pos.row, pos.col);
		break;
	default:	/* LCD_IOC_BACKLIGHT */
		lcd->backlight = on ? LCD_BL : 0;
		ret = pcf_write(lcd, 0);	/* ghi ngay để đèn đổi trạng thái */
		break;
	}
	mutex_unlock(&lcd->lock);

	return ret ? -EIO : 0;
}

/* ===== Nút nhấn: ngắt -> chống rung -> hàng đợi sự kiện ===== */

/* Ngắt (cả cạnh xuống và lên): chỉ hẹn work chạy sau DEBOUNCE_MS.
 * Nút còn rung thì mỗi ngắt mới lại dời giờ hẹn -> chỉ đọc khi đã ổn định.
 */
static irqreturn_t btn_isr(int irq, void *data)
{
	struct lcd_btn *btn = data;

	mod_delayed_work(system_wq, &btn->work, msecs_to_jiffies(DEBOUNCE_MS));
	return IRQ_HANDLED;
}

/* Chạy sau khi nút hết rung: đọc mức ổn định, nhấn mới thì đẩy sự kiện */
static void btn_debounce(struct work_struct *w)
{
	struct lcd_btn *btn = container_of(to_delayed_work(w), struct lcd_btn, work);
	struct lcd2004 *lcd = btn->lcd;
	int v;

	/* Work được phép ngủ nên dùng bản _cansleep (an toàn với mọi chip gpio) */
	v = gpiod_get_value_cansleep(btn->gpio);
	if (v < 0)
		return;			/* đọc lỗi: bỏ qua */

	/* btn->pressed chỉ do work của chính nút này đọc/ghi, và các lần chạy
	 * của một work không chồng nhau, nên không cần khóa.
	 */
	if (v && !btn->pressed) {
		btn->pressed = true;
		/* fifo đầy thì kfifo_in trả 0: bỏ sự kiện mới */
		if (kfifo_in_spinlocked(&lcd->events, &btn->code, 1, &lcd->fifo_lock))
			wake_up_interruptible(&lcd->wq);
	} else if (!v) {
		btn->pressed = false;	/* nhả nút: không sinh sự kiện */
	}
}

/* Dừng ngắt và work của n nút đầu tiên.
 * Phải làm trước khi bộ nhớ devm (struct lcd2004, chứa btn và work) bị giải
 * phóng, nếu không work đang chờ/đang chạy sẽ dùng bộ nhớ đã giải phóng.
 * disable_irq trước để không có ngắt mới hẹn thêm work, rồi mới hủy work.
 */
static void lcd_btns_stop(struct lcd2004 *lcd, int n)
{
	int i;

	for (i = 0; i < n; i++) {
		disable_irq(lcd->btns[i].irq);
		cancel_delayed_work_sync(&lcd->btns[i].work);
	}
}

/* read(): trả các mã nút đã nhấn (mỗi byte một sự kiện), chờ nếu chưa có */
static ssize_t lcd_read(struct file *file, char __user *ubuf,
			size_t count, loff_t *ppos)
{
	struct lcd2004 *lcd = file_to_lcd(file);
	char tmp[16];
	unsigned int n;

	if (count == 0)
		return 0;

	/* Lặp: nếu tiến trình khác đã lấy hết sự kiện thì chờ tiếp
	 * (trả 0 nghĩa là EOF nên không được trả 0).
	 */
	while (1) {
		n = kfifo_out_spinlocked(&lcd->events, tmp,
					 min_t(size_t, count, sizeof(tmp)),
					 &lcd->fifo_lock);
		if (n)
			break;
		if (file->f_flags & O_NONBLOCK)
			return -EAGAIN;
		if (wait_event_interruptible(lcd->wq, !kfifo_is_empty(&lcd->events)))
			return -ERESTARTSYS;	/* bị tín hiệu (vd Ctrl+C) cắt ngang */
	}

	if (copy_to_user(ubuf, tmp, n))
		return -EFAULT;
	return n;
}

/* poll()/select(): báo đọc được khi có sự kiện trong fifo */
static __poll_t lcd_poll(struct file *file, poll_table *pt)
{
	struct lcd2004 *lcd = file_to_lcd(file);

	poll_wait(file, &lcd->wq, pt);
	if (!kfifo_is_empty(&lcd->events))
		return EPOLLIN | EPOLLRDNORM;
	return 0;
}

static const struct file_operations lcd_fops = {
	/* Giữ module khi còn tiến trình mở file -> rmmod sẽ báo "in use" */
	.owner = THIS_MODULE,
	.write = lcd_write,
	.read = lcd_read,
	.poll = lcd_poll,
	.unlocked_ioctl = lcd_ioctl,
};

static int lcd_probe(struct i2c_client *client)
{
	struct device *dev = &client->dev;
	struct lcd2004 *lcd;
	struct gpio_descs *gpios;
	struct lcd_btn *btn;
	int ret, i;

	if (!i2c_check_functionality(client->adapter, I2C_FUNC_SMBUS_BYTE))
		return -EOPNOTSUPP;

	/* devm_*: bộ nhớ tự giải phóng khi thiết bị bị gỡ */
	lcd = devm_kzalloc(dev, sizeof(*lcd), GFP_KERNEL);
	if (!lcd)
		return -ENOMEM;

	lcd->client = client;
	lcd->backlight = LCD_BL;
	mutex_init(&lcd->lock);
	i2c_set_clientdata(client, lcd);

	/* Ghi thử 1 byte: bật đèn nền, đồng thời kiểm tra LCD có trả lời không */
	ret = pcf_write(lcd, 0);
	if (ret) {
		dev_err(dev, "không thấy LCD tại 0x%02x (lỗi %d)\n",
			client->addr, ret);
		return ret;
	}

	ret = lcd_init(lcd);
	if (ret) {
		dev_err(dev, "khởi tạo LCD lỗi (%d)\n", ret);
		return ret;
	}

	/* Màn hình chào, xong đưa con trỏ về 0,0 */
	ret = lcd_print_row(lcd, 0, "LCD2004 driver OK");
	if (!ret)
		ret = lcd_print_row(lcd, 1, "Raspberry Pi 5");
	if (!ret)
		ret = lcd_print_row(lcd, 3, "Chay ./demo");
	if (!ret)
		ret = lcd_goto(lcd, 0, 0);
	if (ret) {
		dev_err(dev, "in màn hình chào lỗi (%d)\n", ret);
		return ret;
	}

	/* Lấy 4 chân nút từ Device Tree (button-gpios), chế độ input */
	gpios = devm_gpiod_get_array(dev, "button", GPIOD_IN);
	if (IS_ERR(gpios))
		return dev_err_probe(dev, PTR_ERR(gpios), "không lấy được button-gpios\n");
	if (gpios->ndescs != LCD_NUM_BTNS) {
		dev_err(dev, "cần %d nút, device tree có %u\n",
			LCD_NUM_BTNS, gpios->ndescs);
		return -EINVAL;
	}

	/* Khởi tạo fifo/khóa/hàng chờ trước khi xin ngắt (ngắt có thể đến ngay) */
	INIT_KFIFO(lcd->events);
	spin_lock_init(&lcd->fifo_lock);
	init_waitqueue_head(&lcd->wq);

	for (i = 0; i < LCD_NUM_BTNS; i++) {
		btn = &lcd->btns[i];
		btn->lcd = lcd;
		btn->gpio = gpios->desc[i];
		btn->code = btn_codes[i];
		INIT_DELAYED_WORK(&btn->work, btn_debounce);

		btn->irq = gpiod_to_irq(btn->gpio);
		if (btn->irq < 0) {
			ret = btn->irq;
			dev_err(dev, "nút %d không có ngắt (%d)\n", i, ret);
			goto err_stop;
		}
		/* Ngắt cả hai cạnh để biết lúc nhấn lẫn lúc nhả */
		ret = devm_request_irq(dev, btn->irq, btn_isr,
				       IRQF_TRIGGER_FALLING | IRQF_TRIGGER_RISING,
				       "lcd2004-btn", btn);
		if (ret) {
			dev_err(dev, "xin ngắt nút %d lỗi (%d)\n", i, ret);
			goto err_stop;
		}
	}

	lcd->miscdev.minor = MISC_DYNAMIC_MINOR;
	lcd->miscdev.name = "lcd2004";
	lcd->miscdev.fops = &lcd_fops;
	lcd->miscdev.parent = dev;
	ret = misc_register(&lcd->miscdev);
	if (ret) {
		i = LCD_NUM_BTNS;
		goto err_stop;
	}

	dev_info(dev, "lcd2004: probe ok (địa chỉ 0x%02x)\n", client->addr);
	return 0;

err_stop:
	/* Chỉ dừng các nút đã xin ngắt xong (0..i-1); xem lcd_btns_stop() */
	lcd_btns_stop(lcd, i);
	return ret;
}

static void lcd_remove(struct i2c_client *client)
{
	struct lcd2004 *lcd = i2c_get_clientdata(client);

	/* Dừng ngắt + work TRƯỚC khi gỡ thiết bị và giải phóng bộ nhớ */
	lcd_btns_stop(lcd, LCD_NUM_BTNS);
	misc_deregister(&lcd->miscdev);

	/* Tắt đèn nền khi gỡ driver */
	lcd->backlight = 0;
	pcf_write(lcd, 0);
}

/* Khớp với node Device Tree: compatible = "twt,lcd2004-btn" */
static const struct of_device_id lcd_of_match[] = {
	{ .compatible = "twt,lcd2004-btn" },
	{ }
};
MODULE_DEVICE_TABLE(of, lcd_of_match);

static const struct i2c_device_id lcd_id[] = {
	{ "lcd2004-btn" },
	{ }
};
MODULE_DEVICE_TABLE(i2c, lcd_id);

static struct i2c_driver lcd_driver = {
	.driver = {
		.name = "lcd2004_btn",
		.of_match_table = lcd_of_match,
	},
	.probe = lcd_probe,
	.remove = lcd_remove,
	.id_table = lcd_id,
};
module_i2c_driver(lcd_driver);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Nhom TwT");
MODULE_DESCRIPTION("LCD2004 (PCF8574 I2C) + 4 nut nhan cho Raspberry Pi 5");
