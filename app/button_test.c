// SPDX-License-Identifier: GPL-2.0
/*
 * button_test - Đọc sự kiện 4 nút từ /dev/lcd2004 và in ra kèm giờ.
 * Thoát khi nhấn Ctrl+C.
 */
#include <stdio.h>
#include <signal.h>
#include <errno.h>
#include <time.h>
#include <fcntl.h>
#include <unistd.h>

#include "lcd2004_ioctl.h"

static volatile sig_atomic_t stop;	/* =1 khi nhận Ctrl+C */

static void on_sigint(int sig)
{
	(void)sig;
	stop = 1;
}

/* In giờ hiện tại dạng [hh:mm:ss.mmm] */
static void print_time(void)
{
	struct timespec ts;
	struct tm tm;

	clock_gettime(CLOCK_REALTIME, &ts);
	localtime_r(&ts.tv_sec, &tm);
	printf("[%02d:%02d:%02d.%03ld] ", tm.tm_hour, tm.tm_min, tm.tm_sec,
	       ts.tv_nsec / 1000000);
}

int main(void)
{
	struct sigaction sa = { 0 };
	char buf[8];
	ssize_t n, i;
	int fd;

	/* Không đặt SA_RESTART để read() bị ngắt và trả -1 với errno = EINTR */
	sa.sa_handler = on_sigint;
	sigaction(SIGINT, &sa, NULL);

	fd = open("/dev/lcd2004", O_RDONLY);
	if (fd < 0) {
		perror("open /dev/lcd2004");
		return 1;
	}

	printf("Nhan cac nut (Ctrl+C de thoat)...\n");
	while (!stop) {
		n = read(fd, buf, sizeof(buf));
		if (n < 0) {
			if (errno == EINTR)
				break;		/* Ctrl+C */
			perror("read");
			break;
		}
		for (i = 0; i < n; i++) {
			print_time();
			switch (buf[i]) {
			case LCD_BTN_1:
				printf("NUT 1\n");
				break;
			case LCD_BTN_2:
				printf("NUT 2\n");
				break;
			case LCD_BTN_3:
				printf("NUT 3\n");
				break;
			case LCD_BTN_4:
				printf("NUT 4\n");
				break;
			default:
				printf("?? 0x%02x\n", (unsigned char)buf[i]);
			}
		}
		fflush(stdout);
	}

	close(fd);
	return 0;
}
