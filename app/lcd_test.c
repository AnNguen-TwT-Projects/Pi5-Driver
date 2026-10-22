// SPDX-License-Identifier: GPL-2.0
/*
 * lcd_test - Kiểm tra /dev/lcd2004: write + ioctl (CLEAR, SET_CURSOR, BACKLIGHT)
 * Mỗi mục in PASS hoặc FAIL; thoát 0 nếu tất cả đạt.
 */
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>

#include "lcd2004_ioctl.h"

static int fails;	/* đếm số mục FAIL */

/* In kết quả một mục kiểm tra */
static void check(const char *name, int ok)
{
	printf("%-28s %s\n", name, ok ? "PASS" : "FAIL");
	if (!ok)
		fails++;
}

/* Đặt con trỏ rồi ghi chuỗi s; trả 1 nếu cả hai thành công */
static int put_at(int fd, int row, int col, const char *s)
{
	struct lcd_pos pos = { row, col };

	if (ioctl(fd, LCD_IOC_SET_CURSOR, &pos) != 0)
		return 0;
	return write(fd, s, strlen(s)) == (ssize_t)strlen(s);
}

int main(void)
{
	int fd = open("/dev/lcd2004", O_RDWR);
	int ok, i, v;
	char text[16];
	struct lcd_pos pos;

	if (fd < 0) {
		perror("open /dev/lcd2004");
		return 1;
	}

	/* 1. Xóa màn hình, ghi 4 hàng */
	ok = (ioctl(fd, LCD_IOC_CLEAR) == 0);
	for (i = 0; i < 4; i++) {
		snprintf(text, sizeof(text), "Hang %d", i);
		ok &= put_at(fd, i, 0, text);
	}
	check("1. CLEAR + ghi 4 hang", ok);
	sleep(2);

	/* 2. Ghi chữ X ở hàng 1, cột 5 */
	check("2. SET_CURSOR {1,5} + 'X'", put_at(fd, 1, 5, "X"));

	/* 3. Tắt đèn nền 1 giây rồi bật lại (arg là con trỏ tới int) */
	v = 0;
	ok = (ioctl(fd, LCD_IOC_BACKLIGHT, &v) == 0);
	sleep(1);
	v = 1;
	ok &= (ioctl(fd, LCD_IOC_BACKLIGHT, &v) == 0);
	check("3. BACKLIGHT tat/bat", ok);

	/* 4. Vị trí sai phải trả -1 và errno = EINVAL */
	pos.row = 4;
	pos.col = 0;
	errno = 0;
	ok = (ioctl(fd, LCD_IOC_SET_CURSOR, &pos) == -1 && errno == EINVAL);
	pos.row = 0;
	pos.col = 20;
	errno = 0;
	ok &= (ioctl(fd, LCD_IOC_SET_CURSOR, &pos) == -1 && errno == EINVAL);
	check("4. vi tri sai -> EINVAL", ok);

	/* 5. Lệnh lạ phải trả -1 và errno = ENOTTY */
	errno = 0;
	check("5. lenh la -> ENOTTY",
	      ioctl(fd, _IO('L', 99)) == -1 && errno == ENOTTY);

	/* 6. CLEAR phải trả 0 */
	check("6. CLEAR tra 0", ioctl(fd, LCD_IOC_CLEAR) == 0);

	close(fd);

	if (fails == 0)
		printf("ALL PASS\n");
	else
		printf("%d muc FAIL\n", fails);
	return fails ? 1 : 0;
}
