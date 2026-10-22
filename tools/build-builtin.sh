#!/usr/bin/env bash
# Build kernel cho Pi5 có driver lcd2004_btn biên dịch chung với kernel (built-in).
# Chạy TRÊN PI5, từ thư mục gốc repo. Hướng dẫn đầy đủ: docs/BUILTIN.md
#
#   bash tools/build-builtin.sh           -> thêm driver vào kernel, build, cài
#   bash tools/build-builtin.sh --check   -> chỉ thêm driver + cấu hình, không build (thử nhanh)
#
# Script KHÔNG sửa /boot/firmware/config.txt. Bật kernel mới làm bằng tay (docs/BUILTIN.md
# bước 4) để lúc nào cũng quay về kernel gốc được.
#
# Biến tùy chọn:
#   KERNEL_DIR  nơi để mã nguồn kernel, mặc định ~/rpi-linux
#   RPI_BRANCH  nhánh kernel, mặc định lấy theo `uname -r` (ví dụ 6.12.x -> rpi-6.12.y)
#   JOBS        số luồng biên dịch, mặc định bằng số nhân CPU (giảm xuống 2 nếu bị "Killed" do hết RAM)

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
KERNEL_DIR="${KERNEL_DIR:-$HOME/rpi-linux}"
RPI_BRANCH="${RPI_BRANCH:-rpi-$(uname -r | cut -d. -f1-2).y}"
LOCALVER="-v8-16k-lcd"          # khác "-v8-16k" của kernel gốc, để không ghi đè module của kernel gốc
KERNEL_IMG="kernel_lcd.img"     # tên file kernel mới trong /boot/firmware, kernel gốc giữ nguyên
JOBS="${JOBS:-$(nproc)}"

# LOCALVERSION= (rỗng) để kernel không tự thêm dấu "+" vào tên phiên bản
MAKE=(make -C "$KERNEL_DIR" LOCALVERSION=)
AUX="$KERNEL_DIR/drivers/auxdisplay"

echo "==> 1. Lấy mã nguồn kernel ($RPI_BRANCH) vào $KERNEL_DIR"
if [[ ! -d "$KERNEL_DIR/.git" ]]; then
    git clone --depth=1 --branch "$RPI_BRANCH" https://github.com/raspberrypi/linux "$KERNEL_DIR"
else
    echo "    Đã có, bỏ qua bước tải"
fi

echo "==> 2. Chép driver vào drivers/auxdisplay/ (thư mục chứa các driver LCD ký tự)"
cp "$REPO/driver/lcd2004_btn.c" "$REPO/include/lcd2004_ioctl.h" "$AUX/"

echo "==> 3. Khai báo driver trong Kconfig và Makefile của kernel (chỉ thêm một lần)"
if ! grep -q "^config LCD2004_BTN" "$AUX/Kconfig"; then
    # Chèn mục config ngay trước dòng "endif # AUXDISPLAY" để nằm trong menu Auxiliary Display
    entry=$(mktemp)
    cat > "$entry" <<'EOF'
config LCD2004_BTN
	tristate "LCD2004 (PCF8574 I2C) + 4 buttons for Raspberry Pi 5"
	depends on I2C && GPIOLIB && OF
	help
	  HD44780 20x4 character LCD behind a PCF8574 I2C backpack, plus
	  4 push buttons. Creates /dev/lcd2004 (write, ioctl, read, poll).
	  Needs the lcd2004-btn Device Tree overlay.

	  Say Y to build it into the kernel, M to build it as a module.

EOF
    awk -v f="$entry" '/^endif # AUXDISPLAY/ { while ((getline l < f) > 0) print l } { print }' \
        "$AUX/Kconfig" > "$AUX/Kconfig.new"
    mv "$AUX/Kconfig.new" "$AUX/Kconfig"
    rm -f "$entry"
fi
grep -q "CONFIG_LCD2004_BTN" "$AUX/Makefile" || \
    echo 'obj-$(CONFIG_LCD2004_BTN)	+= lcd2004_btn.o' >> "$AUX/Makefile"

echo "==> 4. Cấu hình kernel cho Pi5, bật driver ở dạng built-in (=y)"
"${MAKE[@]}" bcm2712_defconfig
"$KERNEL_DIR/scripts/config" --file "$KERNEL_DIR/.config" \
    --set-str LOCALVERSION "$LOCALVER" --enable LCD2004_BTN
"${MAKE[@]}" olddefconfig
# syncconfig ghi lại include/config/auto.conf, nơi kernel đọc LOCALVERSION để đặt tên phiên bản
"${MAKE[@]}" syncconfig
if ! grep -q "^CONFIG_LCD2004_BTN=y" "$KERNEL_DIR/.config"; then
    echo "LỖI: CONFIG_LCD2004_BTN chưa được bật =y trong .config"
    exit 1
fi
RELEASE=$("${MAKE[@]}" -s kernelrelease)
echo "    OK: CONFIG_LCD2004_BTN=y, phiên bản kernel mới: $RELEASE"

if [[ "${1:-}" == "--check" ]]; then
    echo "Xong phần kiểm tra (--check), chưa build."
    exit 0
fi

echo "==> 5. Build kernel và module (lâu nhất, để Pi chạy, đừng tắt máy)"
"${MAKE[@]}" -j"$JOBS" Image.gz modules

echo "==> 6. Cài module vào /lib/modules/$RELEASE và chép kernel vào /boot/firmware/$KERNEL_IMG"
sudo "${MAKE[@]}" modules_install
sudo cp "$KERNEL_DIR/arch/arm64/boot/Image.gz" "/boot/firmware/$KERNEL_IMG"

echo "==> 7. Kiểm tra driver nằm trong danh sách built-in"
grep lcd2004 "/lib/modules/$RELEASE/modules.builtin"

echo
echo "Xong. Kernel gốc vẫn còn nguyên. Bật kernel mới theo docs/BUILTIN.md bước 4:"
echo "  thêm dòng  kernel=$KERNEL_IMG  vào cuối /boot/firmware/config.txt rồi reboot."
