# Build các chương trình user-space.
#   make                              -> build trực tiếp trên Pi5
#   make CC=aarch64-linux-gnu-gcc     -> cross-compile
CC ?= gcc
CFLAGS = -Wall -Wextra -O2 -I../include

# Ba chương trình: lcd_test, button_test, demo
all: lcd_test button_test demo

lcd_test: lcd_test.c
	$(CC) $(CFLAGS) -o $@ $<

button_test: button_test.c
	$(CC) $(CFLAGS) -o $@ $<

demo: demo.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f lcd_test button_test demo
