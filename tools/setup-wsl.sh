#!/usr/bin/env bash
# Cài môi trường cross-compile cho Pi5 (arm64) trong WSL Ubuntu.
#
# Cách chạy (trong Ubuntu WSL):
#   bash tools/setup-wsl.sh            -> chỉ cài gói
#   bash tools/setup-wsl.sh --kernel   -> cài gói + tải mã nguồn kernel Pi và chuẩn bị để build module
#
# Biến tùy chọn:
#   RPI_BRANCH  nhánh kernel, mặc định rpi-6.12.y (phải khớp `uname -r` trên Pi5)
#   KERNEL_DIR  nơi để mã nguồn kernel, mặc định ~/rpi-linux

set -euo pipefail

RPI_BRANCH="${RPI_BRANCH:-rpi-6.12.y}"
KERNEL_DIR="${KERNEL_DIR:-$HOME/rpi-linux}"

# Các gói cần:
#   build-essential, bc, bison, flex, libssl-dev, libelf-dev, libncurses-dev, cpio, kmod: build kernel/module
#   gcc-aarch64-linux-gnu: trình biên dịch chéo ra mã arm64 cho Pi5
#   device-tree-compiler: lệnh dtc để biên dịch overlay .dts -> .dtbo
#   git, rsync: lấy mã nguồn và chép file
PACKAGES=(
    build-essential bc bison flex libssl-dev libelf-dev libncurses-dev cpio kmod
    gcc-aarch64-linux-gnu
    device-tree-compiler
    git rsync
)

echo "==> Cài gói: ${PACKAGES[*]}"
sudo apt-get update
sudo apt-get install -y "${PACKAGES[@]}"

echo "==> Kiểm tra công cụ"
aarch64-linux-gnu-gcc --version | head -n 1
dtc --version
make --version | head -n 1

if [[ "${1:-}" == "--kernel" ]]; then
    # Để mã nguồn trong ổ Linux (~), không để trong /mnt/d vì build ở đó rất chậm
    if [[ ! -d "$KERNEL_DIR/.git" ]]; then
        echo "==> Tải kernel Pi nhánh $RPI_BRANCH vào $KERNEL_DIR"
        git clone --depth=1 --branch "$RPI_BRANCH" https://github.com/raspberrypi/linux "$KERNEL_DIR"
    else
        echo "==> Đã có $KERNEL_DIR, bỏ qua bước tải"
    fi

    echo "==> Cấu hình cho Pi5 (bcm2712) và chuẩn bị build module"
    make -C "$KERNEL_DIR" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- bcm2712_defconfig
    make -C "$KERNEL_DIR" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j"$(nproc)" modules_prepare

    echo
    echo "Xong. Build thử driver từ thư mục driver/:"
    echo "  make KDIR=$KERNEL_DIR ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- KBUILD_MODPOST_WARN=1"
fi

echo "==> Hoàn tất"
