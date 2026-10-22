// SPDX-License-Identifier: GPL-2.0
/*
 * demo - Chữ chạy trên LCD2004, điều khiển bằng 4 nút (input điều khiển output).
 *
 * 4 trạng thái:
 *   XIN_CHAO : "Xin Chao" chạy mãi ở hàng 1. Nút bất kỳ -> DSTV
 *   DSTV     : danh sách thành viên đứng yên. Nút số k -> SCROLL(k)
 *   SCROLL(n): hàng 1 chạy "<Ho ten> - <MSSV>" đúng 1 lượt. Hết lượt -> INFO(n)
 *   INFO(n)  : hiện họ tên + MSSV đứng yên. Nút số k -> SCROLL(k); 10 giây -> DSTV
 *
 * Nút 1 đến 4 ứng với thành viên 1 đến 4.
 * Chạy chữ làm hoàn toàn ở user-space: ioctl (CLEAR, SET_CURSOR) + write + poll + read.
 * Thoát bằng Ctrl+C.
 */
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <signal.h>
#include <fcntl.h>
#include <unistd.h>
#include <poll.h>
#include <sys/ioctl.h>

#include "lcd2004_ioctl.h"

#define TICK_MS    200	/* một nhịp chạy chữ */
#define INFO_TICKS 50	/* 10 giây = 50 nhịp */
#define NUM_MEMBERS 4

struct member {
	const char *name;	/* họ tên (không dấu) */
	const char *mssv;
};

/* TODO: nhóm điền họ tên THẬT (không dấu, LCD không hiện được chữ có dấu) và MSSV.
 * Đang là tên mẫu. Sửa xong chạy lại `make`.
 */
static const struct member members[NUM_MEMBERS] = {
	{ "Ho Ten 1", "00000001" },
	{ "Ho Ten 2", "00000002" },
	{ "Ho Ten 3", "00000003" },
	{ "Ho Ten 4", "00000004" },
};

enum state { XIN_CHAO, DSTV, SCROLL, INFO };

/* Trạng thái của demo */
struct demo {
	int fd;			/* /dev/lcd2004 */
	enum state state;
	int who;		/* thành viên đang xem: 0..3 (SCROLL, INFO) */
	int pos;		/* cột của ký tự đầu tiên khi chạy chữ (có thể âm) */
	int ticks;		/* số nhịp đã trôi qua ở INFO */
	char text[64];		/* chuỗi đang chạy */
};

static volatile sig_atomic_t stop;	/* =1 khi nhận Ctrl+C */

static void on_sigint(int sig)
{
	(void)sig;
	stop = 1;
}

/* ===== Vẽ lên LCD ===== */

/* Ghi text vào đúng 1 hàng. Đệm dấu cách đến đủ 20 ký tự (cắt nếu dài hơn)
 * nên không cần xóa màn hình khi cập nhật -> LCD không bị nháy.
 * Trả 0 nếu thành công, -1 nếu lỗi (errno đã được đặt).
 */
static int show_row(int fd, int row, const char *text)
{
	struct lcd_pos pos = { row, 0 };
	char buf[32];

	snprintf(buf, sizeof(buf), "%-20.20s", text);
	if (ioctl(fd, LCD_IOC_SET_CURSOR, &pos) != 0)
		return -1;
	if (write(fd, buf, LCD_COLS) != LCD_COLS)
		return -1;
	return 0;
}

/* Tạo 1 khung chữ chạy: ô cột c (0..19) hiện text[c - pos] nếu nằm trong chuỗi,
 * ngược lại là dấu cách. pos là cột của ký tự đầu, có thể âm (chữ đang chui vào từ trái).
 */
static void scroll_frame(const char *text, int pos, char *out)
{
	int len = strlen(text);
	int c, idx;

	for (c = 0; c < LCD_COLS; c++) {
		idx = c - pos;
		out[c] = (idx >= 0 && idx < len) ? text[idx] : ' ';
	}
	out[LCD_COLS] = '\0';
}

/* Vẽ khung chữ chạy hiện tại lên hàng 1 */
static int draw_scroll(struct demo *d)
{
	char frame[LCD_COLS + 1];

	scroll_frame(d->text, d->pos, frame);
	return show_row(d->fd, 1, frame);
}

/* ===== Vào từng trạng thái (xóa màn hình rồi vẽ phần đứng yên) ===== */

static int enter_xin_chao(struct demo *d)
{
	d->state = XIN_CHAO;
	snprintf(d->text, sizeof(d->text), "Xin Chao");
	d->pos = 1 - (int)strlen(d->text);	/* chỉ ký tự cuối lộ ra ở cột 0 */
	if (ioctl(d->fd, LCD_IOC_CLEAR) != 0)
		return -1;
	return draw_scroll(d);
}

static int enter_dstv(struct demo *d)
{
	d->state = DSTV;
	if (ioctl(d->fd, LCD_IOC_CLEAR) != 0)
		return -1;
	if (show_row(d->fd, 0, "Danh Sach Thanh Vien") != 0)
		return -1;
	return show_row(d->fd, 2, "  1    2    3    4");
}

/* n là chỉ số thành viên 0..3 */
static int enter_scroll(struct demo *d, int n)
{
	char title[32];

	d->state = SCROLL;
	d->who = n;
	snprintf(d->text, sizeof(d->text), "%s - %s", members[n].name, members[n].mssv);
	d->pos = 1 - (int)strlen(d->text);
	snprintf(title, sizeof(title), "Thanh vien %d", n + 1);
	if (ioctl(d->fd, LCD_IOC_CLEAR) != 0)
		return -1;
	if (show_row(d->fd, 0, title) != 0)
		return -1;
	return draw_scroll(d);
}

static int enter_info(struct demo *d, int n)
{
	char title[32];

	d->state = INFO;
	d->who = n;
	d->ticks = 0;
	snprintf(title, sizeof(title), "Thanh vien %d", n + 1);
	if (ioctl(d->fd, LCD_IOC_CLEAR) != 0)
		return -1;
	if (show_row(d->fd, 0, title) != 0)
		return -1;
	if (show_row(d->fd, 1, members[n].name) != 0)
		return -1;
	return show_row(d->fd, 2, members[n].mssv);
}

/* ===== Sự kiện ===== */

/* Có một nút được nhấn. Trả 0 nếu ổn, -1 nếu vẽ lỗi */
static int on_key(struct demo *d, char key)
{
	int k;

	switch (key) {		/* nút -> số thành viên 0..3 */
	case LCD_BTN_1:
		k = 0;
		break;
	case LCD_BTN_2:
		k = 1;
		break;
	case LCD_BTN_3:
		k = 2;
		break;
	case LCD_BTN_4:
		k = 3;
		break;
	default:
		return 0;	/* mã lạ: bỏ qua */
	}

	if (d->state == XIN_CHAO)
		return enter_dstv(d);	/* nút bất kỳ -> danh sách */
	return enter_scroll(d, k);	/* DSTV, SCROLL, INFO: xem (lại) thành viên k */
}

/* Hết một nhịp (TICK_MS) mà không có nút. Trả 0 nếu ổn, -1 nếu vẽ lỗi */
static int on_tick(struct demo *d)
{
	switch (d->state) {
	case XIN_CHAO:
	case SCROLL:
		d->pos++;
		/* Một lượt: pos chạy từ 1 - len đến 19, tổng len + 19 nhịp */
		if (d->pos > LCD_COLS - 1) {
			if (d->state == XIN_CHAO) {
				d->pos = 1 - (int)strlen(d->text);	/* lượt mới */
				return draw_scroll(d);
			}
			return enter_info(d, d->who);	/* chạy xong -> hiện đứng yên */
		}
		return draw_scroll(d);
	case INFO:
		if (++d->ticks >= INFO_TICKS)
			return enter_dstv(d);	/* 10 giây không bấm -> danh sách */
		return 0;
	default:			/* DSTV: không có việc theo thời gian */
		return 0;
	}
}

int main(void)
{
	struct sigaction sa = { 0 };
	struct demo d = { 0 };
	struct pollfd pfd;
	char buf[8];
	ssize_t n, i;
	int r, err = 0;

	/* Không đặt SA_RESTART để poll()/read() bị ngắt khi Ctrl+C */
	sa.sa_handler = on_sigint;
	sigaction(SIGINT, &sa, NULL);

	d.fd = open("/dev/lcd2004", O_RDWR);
	if (d.fd < 0) {
		perror("open /dev/lcd2004");
		return 1;
	}

	if (enter_xin_chao(&d) != 0) {
		perror("ve LCD");
		close(d.fd);
		return 1;
	}
	printf("Demo dang chay (Ctrl+C de thoat)...\n");

	pfd.fd = d.fd;
	pfd.events = POLLIN;
	while (!stop && !err) {
		/* DSTV: chờ nút mãi (-1). Các trạng thái khác: chờ tối đa 1 nhịp.
		 * Một poll() vừa chờ nút vừa tạo nhịp chạy chữ, không cần thread.
		 */
		r = poll(&pfd, 1, d.state == DSTV ? -1 : TICK_MS);
		if (r < 0) {
			if (errno == EINTR)
				continue;	/* Ctrl+C: vòng lặp tự thoát */
			perror("poll");
			err = 1;
		} else if (r == 0) {
			if (on_tick(&d) != 0) {
				perror("ve LCD");
				err = 1;
			}
		} else {
			n = read(d.fd, buf, sizeof(buf));
			if (n < 0) {
				if (errno == EINTR || errno == EAGAIN)
					continue;
				perror("read");
				err = 1;
				break;
			}
			for (i = 0; i < n && !err; i++) {
				if (on_key(&d, buf[i]) != 0) {
					perror("ve LCD");
					err = 1;
				}
			}
		}
	}

	/* Dọn màn hình khi thoát (bỏ qua lỗi) */
	(void)ioctl(d.fd, LCD_IOC_CLEAR);
	(void)show_row(d.fd, 0, "Demo da thoat");
	close(d.fd);
	return err;
}
