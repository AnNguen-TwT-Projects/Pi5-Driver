# Build driver ngoài cây kernel (out-of-tree), chạy trên Pi5:
#   make          -> tạo lcd2004_btn.ko
#   make clean    -> xóa file build

obj-m += lcd2004_btn.o

# Cho phép #include "lcd2004_ioctl.h" từ thư mục include/ của repo
ccflags-y := -I$(src)/../include

KDIR ?= /lib/modules/$(shell uname -r)/build

all:
	$(MAKE) -C $(KDIR) M=$(CURDIR) modules

clean:
	$(MAKE) -C $(KDIR) M=$(CURDIR) clean
