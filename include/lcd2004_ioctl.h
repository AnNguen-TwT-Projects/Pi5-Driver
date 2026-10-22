/* SPDX-License-Identifier: GPL-2.0 WITH Linux-syscall-note */
/*
 * lcd2004_ioctl.h - Định nghĩa dùng chung giữa driver (kernel) và app (user-space)
 */
#ifndef LCD2004_IOCTL_H
#define LCD2004_IOCTL_H

#include <linux/ioctl.h>
#include <linux/types.h>

#define LCD_ROWS 4
#define LCD_COLS 20

/* Vị trí con trỏ: hàng 0..3, cột 0..19 */
struct lcd_pos {
	__u8 row;
	__u8 col;
};

#define LCD_IOC_MAGIC      'L'
#define LCD_IOC_CLEAR      _IO(LCD_IOC_MAGIC, 0)			/* xóa màn hình */
#define LCD_IOC_SET_CURSOR _IOW(LCD_IOC_MAGIC, 1, struct lcd_pos)	/* đặt con trỏ */
/* arg trỏ tới int: 0 tắt, khác 0 bật */
#define LCD_IOC_BACKLIGHT  _IOW(LCD_IOC_MAGIC, 2, int)

/* Nút nhấn: mỗi byte đọc được từ /dev/lcd2004 là một trong các mã này */
#define LCD_NUM_BTNS   4
#define LCD_BTN_1      '1'	/* Nút 1, GPIO17 */
#define LCD_BTN_2      '2'	/* Nút 2, GPIO27 */
#define LCD_BTN_3      '3'	/* Nút 3, GPIO22 */
#define LCD_BTN_4      '4'	/* Nút 4, GPIO23 */

#endif /* LCD2004_IOCTL_H */
