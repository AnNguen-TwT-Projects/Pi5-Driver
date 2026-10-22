# Câu hỏi và trả lời ôn vấn đáp

Tài liệu chia theo 4 mảng của nhóm, cộng một phần chung (mảng 5, so sánh với bài giảng 2.1 đến 2.5). Cả 4 người phải đọc hết và giải thích được toàn bộ. Tên hàm trỏ tới file `driver/lcd2004_btn.c`.

Sơ đồ nhanh của driver:

- Lớp 1, truyền I2C: `pcf_write()`.
- Lớp 2, HD44780: `lcd_write4()`, `lcd_send()`, `lcd_cmd()`, `lcd_putc()`, `lcd_goto()`, `lcd_newline()`, `lcd_init()`.
- Lớp 3, giao diện Linux: `lcd_write()`, `lcd_ioctl()`, `lcd_read()`, `lcd_poll()`, cùng phần nút `btn_isr()`, `btn_debounce()`, `lcd_btns_stop()`.
- Khởi tạo và gỡ: `lcd_probe()`, `lcd_remove()`.

---

## Mảng 1. Lớp I2C và HD44780

**Câu 1. Vì sao cần level shifter?**
Backpack LCD chạy 5V và có điện trở pull-up kéo SDA/SCL lên 5V. GPIO của Pi5 chỉ chịu 3.3V và không có mạch bảo vệ. Pi5 cũng có pull-up lên 3.3V, hai pull-up cùng kéo nên điện áp trên SDA/SCL ước lượng khoảng 3.8V, vượt mức cho phép. Level shifter BSS138 hai chiều tách hai phía: phía Pi (LV, 3.3V) và phía LCD (HV, 5V), nên 5V không bao giờ chạm chân Pi.

**Câu 2. Vì sao gửi `0x3` ba lần khi khởi tạo?**
Lúc cấp nguồn ta không biết chắc LCD đang ở chế độ 8-bit hay 4-bit, hoặc đang nhận dở một byte. Lệnh `0x3` (chọn chế độ 8-bit) gửi ba lần, có chờ giữa các lần, ép LCD về một trạng thái biết trước dù nó đang ở đâu. Sau đó mới gửi `0x2` để chuyển sang 4-bit. Đây là trình tự trong datasheet HD44780, thực hiện trong `lcd_init()`.

**Câu 3. Vì sao dùng chế độ 4-bit chứ không 8-bit?**
Chip PCF8574 chỉ có 8 chân. Ta cần 4 chân điều khiển (RS, RW, E, đèn nền) nên chỉ còn 4 chân cho dữ liệu D4 đến D7. Vì vậy mỗi byte gửi thành hai nibble (nibble cao rồi nibble thấp), do `lcd_send()` làm và gọi `lcd_write4()` hai lần.

**Câu 4. Bit map của PCF8574 là gì và `pcf_write()` làm gì?**
P0=RS, P1=RW (luôn 0 vì ta chỉ ghi), P2=E, P3=đèn nền, P4 đến P7=D4 đến D7. Vì vậy nibble được dịch trái 4 bit (`nibble << 4`) để vào đúng 4 bit cao. `pcf_write()` ghi một byte xuống PCF8574 bằng `i2c_smbus_write_byte()` và luôn gộp thêm bit đèn nền hiện tại (`lcd->backlight`), nên bật hoặc tắt đèn nền không bị ghi đè khi gửi chữ.

**Câu 5. Xung E để làm gì?**
LCD chỉ chốt dữ liệu ở cạnh xuống của chân E. `lcd_write4()` ghi dữ liệu kèm E=1, chờ 1 µs, ghi lại dữ liệu với E=0 (cạnh xuống, LCD chốt), rồi chờ 50 µs cho LCD xử lý xong.

**Câu 6. Vì sao lệnh xóa màn hình (`0x01`) phải chờ lâu hơn?**
Hầu hết lệnh HD44780 xong trong khoảng 40 µs, nhưng xóa màn hình (`0x01`) và về đầu (`0x02`) cần khoảng 1.5 ms. `lcd_cmd()` nhận ra hai lệnh này và gọi `usleep_range(2000, 3000)` sau khi gửi. Nếu không chờ, lệnh kế tiếp bị LCD bỏ qua hoặc ghi sai.

**Câu 7. Địa chỉ đầu mỗi hàng của LCD2004 là gì và vì sao lạ như vậy?**
Mảng `row_addr[]` = `{0x00, 0x40, 0x14, 0x54}`. LCD2004 thực chất là bộ nhớ DDRAM của loại 2 dòng được chia nhỏ, nên thứ tự địa chỉ là hàng 0, hàng 2, hàng 1, hàng 3. Vì vậy hết hàng 0 thì địa chỉ không tự nhảy sang hàng 1. `lcd_goto()` gửi lệnh `0x80 | (row_addr[row] + col)` để đặt con trỏ đúng chỗ.

**Câu 8. Khi sang hàng mới, driver làm gì?**
`lcd_newline()` gọi `lcd_goto()` với hàng kế (hàng 3 thì vòng về hàng 0) và cột 0. Phải đặt lại địa chỉ rõ ràng vì địa chỉ DDRAM không nối tiếp theo thứ tự hàng (xem câu 7).

---

## Mảng 2. Bốn nút nhấn: GPIO, ngắt, chống dội, kfifo, poll

**Câu 1. Chân nút được lấy từ đâu, và vì sao "1" nghĩa là đang nhấn?**
`lcd_probe()` gọi `devm_gpiod_get_array(dev, "button", GPIOD_IN)`, lấy cả 4 chân từ thuộc tính `button-gpios` trong Device Tree, theo thứ tự nút 1, 2, 3, 4. Trong overlay mỗi chân có cờ `GPIO_ACTIVE_LOW` (số 1) vì nút nối xuống GND. Nhờ cờ này, thư viện gpiod tự đảo mức: nhấn (mức điện 0) được đọc là 1. Nếu số chân khác 4, `lcd_probe()` trả `-EINVAL`.

**Câu 2. Vì sao chống dội bằng `delayed_work` chứ không `msleep` trong ngắt?**
Hàm ngắt `btn_isr()` chạy trong ngữ cảnh ngắt, không được ngủ, nên không thể gọi `msleep`. `btn_isr()` chỉ gọi `mod_delayed_work()` để hẹn `btn_debounce()` chạy sau 30 ms (`DEBOUNCE_MS`). Nếu nút còn rung, mỗi ngắt mới lại dời giờ hẹn ra xa, nên work chỉ chạy khi nút đã yên 30 ms. Work chạy trong ngữ cảnh tiến trình nên được phép ngủ.

**Câu 3. Vì sao xin ngắt cả cạnh xuống lẫn cạnh lên?**
Để biết cả lúc nhấn lẫn lúc nhả. Khi nhả, `btn_debounce()` đặt `pressed = false` để lần nhấn sau được tính. Nhờ biến `pressed`, giữ nút 2 giây vẫn chỉ sinh đúng một sự kiện (lúc nhấn), không sinh thêm khi nhả.

**Câu 4. `btn_debounce()` quyết định sinh sự kiện như thế nào?**
Nó đọc mức ổn định của chân. Nếu đang nhấn và `pressed` còn false thì đặt `pressed = true`, đẩy mã nút (`btn->code`) vào kfifo rồi `wake_up_interruptible()` để đánh thức `read()`. Nếu đang nhả thì chỉ đặt `pressed = false`. Biến `pressed` chỉ do work của chính nút đó đọc và ghi, và hai lần chạy của một work không chồng nhau, nên không cần khóa.

**Câu 5. Vì sao trong work dùng `gpiod_get_value_cansleep()`?**
Work chạy trong ngữ cảnh tiến trình, được phép ngủ. Bản `_cansleep` an toàn với mọi loại chip GPIO, kể cả loại phải đọc qua I2C hoặc SPI (có thể ngủ). Bản không `_cansleep` chỉ dùng được với chip GPIO truy cập nhanh và sẽ báo cảnh báo nếu chip có thể ngủ. Với Pi5 cả hai đều chạy được, nhưng bản `_cansleep` là lựa chọn đúng cho code trong work.

**Câu 6. Vì sao kfifo dùng spinlock còn LCD dùng mutex?**
kfifo chỉ bị truy cập rất ngắn (copy vài byte vào hoặc ra), không có chỗ nào ngủ trong đoạn đó, nên spinlock (`fifo_lock`, qua `kfifo_in_spinlocked()` và `kfifo_out_spinlocked()`) là hợp lý. LCD thì khác: một lần gửi ký tự qua I2C (`pcf_write()`) có thể ngủ và kéo dài hàng trăm µs đến ms. Không được ngủ khi đang giữ spinlock, nên LCD dùng `mutex` (`lcd->lock`), cho phép tiến trình khác ngủ chờ đến lượt.

**Câu 7. `lcd_read()` hoạt động thế nào?**
Nó thử lấy tối đa 16 byte từ kfifo. Nếu kfifo rỗng: mở `O_NONBLOCK` thì trả `-EAGAIN`; ngược lại ngủ bằng `wait_event_interruptible()` trên hàng chờ `lcd->wq` đến khi có sự kiện. Bị tín hiệu cắt ngang (ví dụ Ctrl+C) thì trả `-ERESTARTSYS`. Lấy được dữ liệu thì `copy_to_user()` ra và trả số byte.

**Câu 8. Vì sao `lcd_read()` không trả 0, kể cả khi vừa được đánh thức?**
Trả 0 có nghĩa là EOF (hết dữ liệu), và chương trình sẽ hiểu là thiết bị đóng. Có thể có hai tiến trình cùng chờ; một tiến trình lấy hết sự kiện trước. Khi tiến trình kia thức dậy mà kfifo rỗng, `lcd_read()` lặp lại bước chờ trong vòng `while (1)` thay vì trả 0.

**Câu 9. `lcd_poll()` làm gì?**
Gọi `poll_wait(file, &lcd->wq, pt)` để đăng ký hàng chờ cho `poll()`/`select()` của user-space, rồi trả `EPOLLIN | EPOLLRDNORM` nếu kfifo không rỗng, ngược lại trả 0. Nhờ vậy ứng dụng chờ được nhiều nguồn (ví dụ nút và bàn phím) cùng lúc.

**Câu 10. Điều gì xảy ra nếu nhấn quá nhanh làm đầy kfifo?**
kfifo chứa tối đa 16 mã. `kfifo_in_spinlocked()` trả 0 khi đầy, và `btn_debounce()` bỏ sự kiện mới (không đánh thức ai). Với người nhấn bằng tay điều này gần như không xảy ra.

---

## Mảng 3. Giao diện `/dev`, `ioctl`, app test

**Câu 1. Vì sao dùng misc device?**
Misc device đơn giản hơn char device đầy đủ: chỉ cần điền `struct miscdevice` và gọi `misc_register()`, kernel tự cấp số minor và tự tạo `/dev/lcd2004`. `lcd_probe()` đăng ký misc device sau cùng, khi mọi thứ đã sẵn sàng (LCD, kfifo, ngắt), để không có tiến trình nào mở được file quá sớm.

**Câu 2. `file_to_lcd()` làm gì và vì sao dùng `container_of`?**
Các hàm `lcd_write()`, `lcd_ioctl()`, `lcd_read()`, `lcd_poll()` chỉ nhận `struct file *`. Khi mở file, `misc_open()` gán `file->private_data` bằng con trỏ tới trường `miscdev` bên trong `struct lcd2004`. `container_of()` tính ngược từ địa chỉ của trường `miscdev` ra địa chỉ của cả `struct lcd2004` chứa nó. Nhờ vậy không cần biến toàn cục.

**Câu 3. Hàm `lcd_write()` xử lý ký tự thế nào?**
Chép từ user từng khối 80 byte bằng `copy_from_user()` vào bộ đệm trên stack. Với từng ký tự: `\n` gọi `lcd_newline()`; ký tự in được (0x20 đến 0x7E) gọi `lcd_putc()`; ký tự khác bị bỏ qua. Mutex `lcd->lock` được giữ suốt cả lần `write()`, nên hai tiến trình cùng ghi không bị trộn ký tự. Lỗi I2C trả `-EIO`, lỗi chép trả `-EFAULT`.

**Câu 4. Vì sao xuống hàng "lười" (chỉ xuống hàng khi có ký tự kế tiếp)?**
Khi ghi đúng 20 ký tự rồi `\n` (ví dụ lệnh `echo` thêm `\n` sau 20 chữ), nếu xuống hàng ngay lúc đủ 20 cột thì `\n` làm xuống hàng lần nữa, chữ nhảy mất 2 hàng. `lcd_write()` để cột chạy đến 20 mà chưa xuống hàng. Chỉ khi có ký tự in được kế tiếp mà `lcd->col >= LCD_COLS` mới gọi `lcd_newline()`. Nhờ vậy `\n` sau 20 ký tự chỉ xuống đúng 1 hàng.

**Câu 5. `ioctl` mã hóa lệnh thế nào?**
Dùng các macro `_IO`, `_IOW` trong `include/lcd2004_ioctl.h` với "magic" là `'L'`. Mã lệnh gồm: hướng truyền dữ liệu, kích thước tham số, magic, số thứ tự. `LCD_IOC_CLEAR` không có tham số (`_IO`). `LCD_IOC_SET_CURSOR` ghi một `struct lcd_pos` vào kernel (`_IOW`). `LCD_IOC_BACKLIGHT` ghi một `int` (`_IOW`). Header này dùng chung cho driver và app để hai bên luôn khớp. Riêng `LCD_IOC_CLEAR`: driver gửi `lcd_cmd(lcd, 0x01)` (lệnh này tự đưa địa chỉ DDRAM về 0) rồi đặt `lcd->row = 0`, `lcd->col = 0` cho khớp, không cần `lcd_goto()`. `lcd_test` thử cả ba lệnh, cộng hai trường hợp lỗi: vị trí sai phải ra `EINVAL`, lệnh lạ phải ra `ENOTTY`.

**Câu 6. Vì sao trong `lcd_ioctl()` phải `copy_from_user` trước khi lấy mutex?**
`copy_from_user()` có thể ngủ (ví dụ trang bộ nhớ của user đang bị swap). Nếu giữ mutex mà ngủ lâu thì mọi tiến trình khác ghi LCD bị chặn theo. Nên `lcd_ioctl()` chép tham số và kiểm tra (`row >= 4`, `col >= 20` thì `-EINVAL`) trước, rồi mới `mutex_lock()` để làm việc với LCD. Lệnh lạ trả `-ENOTTY` ngay mà không cần khóa.

**Câu 7. Vì sao `LCD_IOC_BACKLIGHT` nhận con trỏ tới `int` chứ không nhận giá trị?**
Vì khai báo bằng `_IOW(..., int)` nghĩa là "user ghi một `int` vào kernel", `arg` là địa chỉ của số đó trong user-space. Driver đọc nó bằng `copy_from_user()`. Do đó app phải viết `int v = 0; ioctl(fd, LCD_IOC_BACKLIGHT, &v);`. Driver đổi `lcd->backlight` rồi `pcf_write(lcd, 0)` để đèn đổi trạng thái ngay.

**Câu 8. Điều gì xảy ra nếu `rmmod` khi đang mở file?**
Trong `lcd_fops` có `.owner = THIS_MODULE`. Khi một tiến trình `open()` file, kernel tăng bộ đếm tham chiếu của module. Lúc đó `rmmod` bị từ chối với thông báo `Module lcd2004_btn is in use`. Sau khi đóng file (hoặc thoát chương trình), `rmmod` mới chạy được. Khi đó `lcd_remove()` dừng ngắt, hủy work, gỡ misc device, tắt đèn nền.

**Câu 9. Vì sao `demo` dùng `poll()` có timeout bằng đúng một nhịp chạy chữ?**
`demo` cần làm hai việc cùng lúc: chờ nút nhấn và dịch chữ mỗi 200 ms (`TICK_MS`). Một lệnh `poll()` trên `/dev/lcd2004` với timeout 200 ms làm được cả hai: có nút thì `poll()` trả về sớm và `read()` lấy mã nút; hết giờ thì đó là một nhịp, `on_tick()` dịch chữ. Không cần thread. Riêng trạng thái danh sách thành viên (`DSTV`) không có gì chạy theo thời gian nên timeout là `-1` (chờ mãi đến khi có nút), đỡ tốn CPU. Phía driver, việc này dựa vào `lcd_poll()` và hàng chờ `lcd->wq`.

**Câu 10. Chữ chạy được làm thế nào, và vì sao làm ở user-space chứ không trong driver?**
Hàm `scroll_frame(text, pos, out)` tạo một khung đúng 20 ký tự: ô cột `c` hiện `text[c - pos]` nếu chỉ số nằm trong chuỗi, ngược lại là dấu cách; `pos` là cột của ký tự đầu và có thể âm (chữ đang chui vào từ mép trái). Mỗi nhịp `pos` tăng 1 rồi `show_row()` ghi lại cả hàng 20 ký tự (đã đệm dấu cách). Vì ghi đè đủ cả hàng nên không cần `LCD_IOC_CLEAR` mỗi nhịp, tránh nháy màn hình (lệnh xóa cần khoảng 2 ms và làm cả màn hình trống tạm thời). Chạy chữ là chuyện hiển thị của từng ứng dụng, driver chỉ cung cấp cơ chế (`write`, `ioctl`), nên để ở user-space: driver nhỏ gọn, ít lỗi, và đổi hiệu ứng không cần build lại driver.

---

## Mảng 4. Device Tree overlay, Makefile, build

**Câu 1. Driver biết LCD ở đâu nhờ cái gì?**
Nhờ Device Tree overlay `dts/lcd2004-btn-overlay.dts`. Nó khai báo một node con trên bus I2C1 với `reg = <0x27>` (địa chỉ) và `compatible = "twt,lcd2004-btn"`. Driver có bảng `lcd_of_match[]` chứa đúng chuỗi này. Khi hai chuỗi khớp, kernel gọi `lcd_probe()`.

**Câu 2. Overlay còn khai báo gì ngoài LCD?**
Thuộc tính `button-gpios` liệt kê 4 chân GPIO17, 27, 22, 23 (cờ 1 = active-low), và một nhóm pinctrl bật pull-up nội cho 4 chân đó (`brcm,pull = <2>`). Nhờ pull-up nội, khi nhả nút chân ở mức 1, khi nhấn nút kéo xuống GND thành mức 0.

**Câu 3. Địa chỉ I2C khác `0x27` thì làm sao?**
Backpack có thể ở `0x27` hoặc `0x3F`. Dùng `i2cdetect -y 1` để xem. Overlay có tham số `addr`, nên chỉ cần sửa `config.txt` thành `dtoverlay=lcd2004-btn,addr=0x3f` rồi khởi động lại, không phải sửa code.

**Câu 4. Makefile của driver hoạt động thế nào?**
`obj-m += lcd2004_btn.o` báo cho hệ build của kernel rằng đây là module cần build ra `lcd2004_btn.ko`. Lệnh `make` gọi `make -C $(KDIR) M=$(CURDIR) modules`, nghĩa là dùng Makefile của kernel (ở `KDIR`) để build mã nguồn ở thư mục hiện tại (out-of-tree). Mặc định `KDIR=/lib/modules/$(uname -r)/build`, cho phép chỉ định `KDIR` khác khi build chéo. Dòng `ccflags-y := -I$(src)/../include` giúp `#include "lcd2004_ioctl.h"` tìm thấy file trong thư mục `include/`.

**Câu 5. Vì sao `lcd_probe()` dùng các hàm `devm_*`?**
Tài nguyên `devm_*` (bộ nhớ `devm_kzalloc`, mảng GPIO, ngắt `devm_request_irq`) được kernel tự giải phóng khi thiết bị bị gỡ hoặc `probe` lỗi, nên đỡ phải viết nhiều đường dọn dẹp. Lưu ý: chúng bị giải phóng SAU khi `lcd_remove()` kết thúc, nên những thứ devm không tự lo được (work đang chờ chạy) phải dừng thủ công, xem câu 6.

**Câu 6. Vì sao phải dừng ngắt và `cancel_delayed_work_sync()` trước khi bộ nhớ devm bị giải phóng?**
Struct `lcd2004` (chứa `btns[]` và `work`) nằm trong bộ nhớ devm. Nếu work còn đang chờ hoặc đang chạy mà bộ nhớ đó bị giải phóng, `btn_debounce()` sẽ dùng bộ nhớ đã giải phóng và gây oops. `lcd_btns_stop()` làm hai việc cho mỗi nút: `disable_irq()` trước để không còn ngắt mới hẹn thêm work, rồi `cancel_delayed_work_sync()` để hủy work đang chờ và chờ work đang chạy xong. Hàm này được gọi ở `lcd_remove()` và cả ở đường lỗi `err_stop` của `lcd_probe()` (khi xin ngắt nút thứ i lỗi hoặc `misc_register()` lỗi; ở đó chỉ dừng các nút đã xin ngắt xong).

**Câu 7. Thứ tự các bước trong `lcd_probe()` và vì sao?**
`pcf_write` thử LCD, `lcd_init`, in màn hình chào, lấy mảng GPIO, khởi tạo kfifo/spinlock/hàng chờ, xin ngắt từng nút, cuối cùng `misc_register`. Kfifo, khóa và hàng chờ phải sẵn sàng trước khi xin ngắt (ngắt có thể đến ngay). Misc device đăng ký sau cùng để user-space không mở file trước khi mọi thứ xong. Lỗi sớm (LCD không trả lời, init lỗi) thì `probe` trả lỗi, chưa tạo gì.

**Câu 8. `.ko` khác built-in thế nào?**
Module `.ko` là file riêng, nạp vào kernel đang chạy bằng `insmod` và gỡ bằng `rmmod`, không cần build lại kernel. Built-in là mã được biên dịch thẳng vào ảnh kernel (`CONFIG_LCD2004_BTN=y`), có mặt ngay từ lúc boot và không gỡ được. Built-in khó sửa hơn (build lại cả kernel, lần đầu khoảng 70 phút trên Pi5 4GB) nhưng không cần `insmod`. Nhóm làm cả hai: bản `.ko` (mức Đáp ứng, đạt HW-1 đến HW-7) và bản built-in (mức Tốt, đạt HW-8), xem `docs/BUILTIN.md` và các câu 10 đến 18 bên dưới.

**Câu 9. Có thể nạp file `.ko` build trên laptop (WSL) lên Pi không?**
Không. Khi build chéo bằng `KBUILD_MODPOST_WARN=1` mà không có `Module.symvers` của đúng kernel Pi, `.ko` thiếu thông tin phiên bản và liên kết các hàm kernel. Bản đó chỉ để kiểm tra lỗi biên dịch. Muốn `insmod` phải build lại trên Pi5 bằng `linux-headers-rpi-2712` khớp `uname -r`.

**Câu 10. Đưa driver vào cây mã nguồn kernel bằng cách nào?**
Script `tools/build-builtin.sh` (chạy trên Pi5) làm ba việc. Chép `lcd2004_btn.c` và `lcd2004_ioctl.h` vào `drivers/auxdisplay/`, thư mục chứa các driver LCD ký tự của kernel (ví dụ `hd44780`). Chèn mục `config LCD2004_BTN` vào `drivers/auxdisplay/Kconfig`, ngay trước dòng `endif # AUXDISPLAY` để nằm trong menu Auxiliary Display. Thêm dòng `obj-$(CONFIG_LCD2004_BTN) += lcd2004_btn.o` vào `drivers/auxdisplay/Makefile`. Script kiểm tra bằng `grep -q` trước khi thêm, nên chạy lại nhiều lần không bị thêm trùng.

**Câu 11. `tristate` và `obj-$(CONFIG_LCD2004_BTN)` nghĩa là gì?**
`tristate` là tùy chọn có ba giá trị: `y` (built-in), `m` (module) và `n` (không build). `depends on I2C && GPIOLIB && OF` nghĩa là chỉ chọn được khi kernel có I2C, GPIO và Device Tree. Trong Makefile, `$(CONFIG_LCD2004_BTN)` được thay bằng giá trị đã chọn: `=y` thành `obj-y`, file được liên kết vào ảnh kernel; `=m` thành `obj-m`, ra file `.ko`; `=n` thì bị bỏ qua.

**Câu 12. Code driver có phải sửa để thành built-in không?**
Không sửa dòng nào. Macro `module_i2c_driver()` sinh ra `module_init()` và `module_exit()`. Khi build module, hai hàm này chạy lúc `insmod` và `rmmod`. Khi build built-in, `module_init()` thành một initcall (mức `device_initcall`) mà kernel tự gọi lúc boot để đăng ký `i2c_driver`, còn `module_exit()` bị bỏ vì driver built-in không bao giờ bị gỡ.

**Câu 13. Các bước cấu hình và build kernel?**
`make bcm2712_defconfig` lấy cấu hình mặc định của Pi5. `scripts/config --set-str LOCALVERSION "-v8-16k-lcd" --enable LCD2004_BTN` đặt tên phiên bản và bật driver `=y`. `make olddefconfig` điền giá trị mặc định cho các tùy chọn còn lại. Script kiểm tra `.config` có `CONFIG_LCD2004_BTN=y` rồi mới build `Image.gz modules`, sau đó `modules_install` và chép `arch/arm64/boot/Image.gz` thành `/boot/firmware/kernel_lcd.img`. Mã nguồn lấy từ `raspberrypi/linux`, nhánh khớp `uname -r` (Pi của nhóm là `rpi-6.18.y`). Nhóm build ngay trên Pi5, không build chéo trên laptop.

**Câu 14. Vì sao đặt `LOCALVERSION=-v8-16k-lcd` và tên file `kernel_lcd.img`?**
Để kernel mới không đè lên kernel gốc. Tên phiên bản khác (`6.18.57-v8-16k-lcd` so với `...-v8-16k` của kernel gốc) nên `modules_install` cài vào một thư mục `/lib/modules/` riêng. Tên file kernel khác nên file kernel gốc trong `/boot/firmware` vẫn còn nguyên, lúc nào cũng quay về được.

**Câu 15. Driver đã built-in rồi, sao vẫn phải cài modules?**
Built-in chỉ áp dụng cho driver của nhóm, nhiều driver khác của kernel vẫn là module. Trên Pi5, bộ điều khiển I2C là module (`CONFIG_I2C_DESIGNWARE_PLATFORM=m`). Không cài modules thì không có bus I2C, và `lcd_probe()` không bao giờ chạy. Điều này cũng cho thấy: driver đăng ký ngay lúc boot, nhưng `lcd_probe()` chỉ được gọi khi bus I2C xuất hiện và kernel tạo thiết bị từ node Device Tree.

**Câu 16. Bật kernel mới và quay về kernel gốc thế nào?**
Thêm dòng `kernel=kernel_lcd.img` vào cuối `/boot/firmware/config.txt` rồi khởi động lại, firmware sẽ nạp file kernel đó thay cho kernel mặc định. Script cố ý không tự sửa `config.txt`. Muốn quay lại thì xóa dòng đó. Nếu Pi không boot được, cắm thẻ nhớ vào laptop, sửa `config.txt` trong ổ `bootfs`.

**Câu 17. Đã built-in rồi còn cần Device Tree overlay không?**
Vẫn cần. Built-in chỉ đưa code driver vào kernel. Overlay mới cho kernel biết LCD nằm ở bus nào, địa chỉ nào, nút ở chân nào. Không có overlay thì không có node khớp `compatible`, `lcd_probe()` không chạy.

**Câu 18. Làm sao chứng minh driver đang chạy dạng built-in (mốc HW-8)?**
Không chạy `insmod` mà LCD vẫn tự hiện màn hình chào. `uname -r` có đuôi `-v8-16k-lcd`. `lsmod | grep lcd2004` không in gì (không phải module). `modules.builtin` có dòng `kernel/drivers/auxdisplay/lcd2004_btn.ko`. Có `/dev/lcd2004`, `dmesg` có `probe ok`, và `lcd_test`, `button_test`, `demo` chạy như bản `.ko` mà không cần build lại.

---

## Mảng 5. So sánh với tài liệu hướng dẫn bài 2.1 đến 2.5 (phần chung, cả nhóm cùng đọc)

Tài liệu hướng dẫn bài 2.1 đến 2.5 (driver LED, nút nhấn và LCD1602 trên Pi4, sửa lại cho Pi5) dạy cách viết driver "kiểu cũ". Driver của nhóm làm theo cách mới hơn. Thầy có thể hỏi "sao em không làm như bài giảng?", nên phải trả lời được. Phần này dựa trên file tài liệu chữ, không dựa trên video.

| Nội dung | Tài liệu bài 2.1 đến 2.5 | Project nhóm |
|---|---|---|
| Lấy GPIO | `gpio_request(17, ...)`, số chân viết cứng trong code | `devm_gpiod_get_array()`, chân khai báo trong Device Tree overlay |
| Gắn với LCD qua I2C | Driver tự tạo client: `i2c_get_adapter(1)` rồi `i2c_new_client_device()` | `i2c_driver` có `of_match_table`, kernel tự gọi `lcd_probe()` khi thấy node khớp |
| Tạo `/dev` | `alloc_chrdev_region` + `cdev_add` + `class_create` + `device_create` (4 bước) | `misc_register()` (1 bước) |
| Dữ liệu của driver | Biến toàn cục | Struct `lcd2004`, lấy lại bằng `container_of()` |
| Ngắt nút | `request_irq()` và xử lý ngay trong hàm ngắt, chống dội bằng `jiffies` | `btn_isr()` chỉ hẹn `delayed_work`, `btn_debounce()` đọc lại mức chân |
| Dọn tài nguyên | Chuỗi nhãn `goto err_*` viết tay | `devm_*` và `lcd_btns_stop()` |
| Màn hình | LCD1602, 2 dòng | LCD2004, 4 dòng |
| Ngoại vi | 1 nút và 1 LED | 4 nút, không có LED |
| Cách báo sự kiện nút | `read()` trả chuỗi `COUNT:.. LED:..` | `read()` trả mã nút, có `poll()`, chờ được không tốn CPU |

**Câu 1. Vì sao nhóm không dùng `gpio_request(17)` như bài giảng?**
`gpio_request()` nhận số GPIO toàn cục của kernel, còn "17" trong bài giảng là số BCM. Trên Pi5 các chân header nằm ở chip RP1, số toàn cục của chip này bằng một số "base" cộng với số BCM, và base thay đổi theo bản kernel. Nên số 17 viết cứng có thể trỏ nhầm sang chip khác. Muốn biết số thật phải tra bằng `gpioinfo`. Cách `gpiod` lấy chân từ Device Tree (`button-gpios`) không phụ thuộc số đó, và đổi chân chỉ cần sửa overlay, không build lại driver. Ngoài ra API `gpio_*` kiểu số nguyên là API cũ, kernel khuyên dùng `gpiod_*`.

**Câu 2. Vì sao dùng `i2c_driver` và Device Tree chứ không tự `i2c_new_client_device()`?**
Cách của bài giảng viết cứng bus 1 và địa chỉ `0x27` vào code, đổi địa chỉ phải build lại. Với `i2c_driver`, địa chỉ nằm trong overlay (`reg = <0x27>`, có tham số `addr`), kernel khớp chuỗi `compatible` rồi gọi `lcd_probe()`, và tự gọi `lcd_remove()` khi gỡ. Đây cũng là cách các driver I2C trong kernel thật vẫn làm.

**Câu 3. Vì sao dùng misc device thay vì `cdev` + `class_create`?**
Bốn bước của bài giảng làm đúng một việc: tạo ra `/dev/<tên>`. `misc_register()` làm gọn trong một bước và tự cấp minor. Thêm một lợi ích: từ kernel 6.4 hàm `class_create()` đổi chữ ký (bỏ tham số `THIS_MODULE`), nên code bài giảng phải thêm `#if LINUX_VERSION_CODE`. Dùng misc thì không dính chuyện này.

**Câu 4. Vì sao không làm việc nặng và không chống dội trực tiếp trong hàm ngắt?**
Bài giảng làm hết trong ngắt: đảo LED, tăng biến đếm, `pr_info`. Với LED thì chạy được, nhưng hàm ngắt không được ngủ và phải ngắn. Ở project của nhóm, ngắt chỉ hẹn `delayed_work`, phần đọc chân GPIO và đẩy vào kfifo làm trong work (xem Mảng 2, câu 2). Chống dội cũng khác: bài giảng so `jiffies`, nên bỏ qua mọi ngắt trong 200 ms sau lần đầu, còn nhóm chờ nút yên 30 ms rồi mới đọc mức thật, nên biết đúng lúc nhấn và lúc nhả.

**Câu 5. Vì sao không dùng `ioremap` để đọc thanh ghi GPIO trên Pi5?**
Trên Pi5 GPIO, I2C, SPI nằm trong chip RP1, nối với SoC bằng PCIe, địa chỉ thanh ghi không phải địa chỉ cũ của Pi4. Truy cập sai địa chỉ có thể làm kernel lỗi. Nhóm chỉ dùng API chuẩn của kernel (`gpiod_*`, `i2c_smbus_*`), nên không cần biết địa chỉ thanh ghi.

**Câu 6. Backpack LCD tài liệu nói là "an toàn" nối thẳng vào Pi, nhóm có đồng ý không?**
Chỉ đúng một phần. Tài liệu có ghi: nếu module I2C có sẵn điện trở kéo lên 5V thì phải tháo chúng hoặc dùng level shifter. Hầu hết backpack PCF8574 có kéo lên 5V, nên nhóm dùng BSS138 (xem Mảng 1, câu 1) thay vì tin rằng nối thẳng là an toàn.

**Câu 7. Tài liệu có những chỗ nào chưa đúng hoặc chưa chặt?**
Nên biết để không bị hỏi vặn, và nhớ là đây là nhận xét về tài liệu, không phải về driver của nhóm.
1. Hàm ngắt khai báo `irq_handler_t f(int, void *, struct pt_regs *)` có 3 tham số rồi ép kiểu khi gọi `request_irq`, và `return (irq_handler_t) IRQ_HANDLED`. Kiểu đúng là `irqreturn_t f(int irq, void *dev_id)` và `return IRQ_HANDLED`. Ép kiểu chỉ che lỗi của trình biên dịch. Hàm `btn_isr()` của nhóm dùng đúng kiểu.
2. `i2c_new_client_device()` khi lỗi trả về `ERR_PTR(...)` chứ không phải `NULL`. Đoạn `if (!lcd_client)` trong tài liệu không bắt được lỗi, phải dùng `IS_ERR()`.
3. `gpio_set_debounce()` có thể không được chip RP1 hỗ trợ, tài liệu cũng tự ghi ở mục 8. Nhóm không dựa vào hàm này.
4. `lcd_write()` trong tài liệu không có khóa, hai tiến trình ghi cùng lúc có thể trộn ký tự. Driver của nhóm giữ `lcd->lock` suốt một lần `write()`.
5. `lcd_write()` trong tài liệu chỉ lấy tối đa 32 byte nhưng vẫn `return len`, báo là đã ghi hết. Nếu ghi dài hơn 32 byte thì phần sau bị mất mà chương trình không biết.
6. Số GPIO viết cứng (xem câu 1).

**Câu 8. Driver nhóm có gì mà bài giảng không có?**
Có `poll()` để chờ nút mà không tốn CPU, có `ioctl` (xóa màn hình, đặt con trỏ, bật tắt đèn nền), có kfifo để không mất sự kiện khi ứng dụng chưa kịp đọc, và hỗ trợ 4 hàng của LCD2004 (địa chỉ DDRAM lạ, xem Mảng 1, câu 7). Ngược lại, project của nhóm không có LED (GPIO27) như bài giảng, thay vào đó là 4 nút và LCD2004.

---

## Giới hạn đã biết

Khi bị hỏi, trả lời trung thực các điểm sau.

1. **Gỡ thiết bị qua sysfs (unbind) khi đang mở `/dev/lcd2004`**: có thể dùng bộ nhớ đã giải phóng. `rmmod` thì đã được chặn nhờ `.owner = THIS_MODULE`, nhưng `unbind` không đi qua bộ đếm module nên không bị chặn. Đây là rủi ro còn lại, ít gặp khi dùng bình thường.
2. **Lỗi I2C giữa chừng** (ví dụ rút dây lúc đang ghi): `lcd_write()` trả `-EIO`, nhưng `lcd->row` và `lcd->col` có thể lệch so với vị trí con trỏ thật của LCD. Lần ghi sau nên gọi `LCD_IOC_SET_CURSOR` hoặc `LCD_IOC_CLEAR` để đồng bộ lại.
3. **kfifo đầy (16 sự kiện)**: sự kiện nút mới bị bỏ.
4. **`copy_to_user()` lỗi trong `lcd_read()`**: các byte đã lấy ra khỏi kfifo bị mất.
5. **`probe` lỗi sau `lcd_init()`**: đèn nền vẫn sáng vì driver không tắt lại ở đường lỗi.
6. **Chỉ hỗ trợ ASCII 0x20 đến 0x7E**: ký tự khác, kể cả chữ có dấu, bị bỏ qua.
7. **Bản built-in khó sửa**: sửa code driver phải build lại kernel và khởi động lại, không `rmmod` được. Muốn tắt driver phải quay về kernel gốc (xóa dòng `kernel=` trong `config.txt`).
8. **Tên thành viên trong `demo` đang là tên mẫu**: cần điền tên và MSSV thật vào bảng `members[]` ở đầu `app/demo.c`.
