# Driver built-in: biên dịch driver chung với kernel

Đây là mức "Tốt" của đề (mốc HW-8). Bản ở `README.md` là mức "Đáp ứng": driver là module `.ko`, nạp bằng `insmod`. Ở đây driver được biên dịch **vào bên trong** file kernel, nên boot xong driver đã chạy sẵn, không có file `.ko`, không cần `insmod`.

| | Module `.ko` (README) | Built-in (tài liệu này) |
|---|---|---|
| Driver nằm ở đâu | File `lcd2004_btn.ko` riêng | Bên trong file kernel `kernel_lcd.img` |
| Nạp driver | `sudo insmod` sau mỗi lần boot | Kernel tự chạy driver lúc boot |
| `lsmod` | Thấy `lcd2004_btn` | **Không thấy** (không phải module) |
| `rmmod` | Được | Không được |
| Sửa code driver | `make` lại module (vài giây) | Build lại kernel |

Code driver **không đổi một dòng nào**. Macro `module_i2c_driver()` tự biết đang build kiểu nào: build module thì thành `module_init`/`module_exit`, build built-in thì thành hàm kernel gọi lúc khởi động. Những gì thay đổi chỉ là chỗ đặt file và 2 file khai báo của kernel (`Kconfig`, `Makefile`), script ở bước 3 làm tự động.

Mọi lệnh chạy **trên Pi5**. Kernel gốc của Pi được giữ nguyên, lúc nào cũng quay về được (bước 6).

---

## 0. Điều kiện trước khi làm

- Bản `.ko` đã chạy đúng hết HW-1 đến HW-7 (`docs/HARDWARE.md` mục 5). Overlay `lcd2004-btn` vẫn phải bật như README mục 3: built-in chỉ đưa driver vào kernel, kernel vẫn cần overlay để biết LCD nằm ở đâu.
- Thẻ nhớ còn trống **ít nhất 10 GB** (mã nguồn kernel và file build khá nặng):

  ```bash
  df -h ~
  ```

- Ghi lại phiên bản kernel đang chạy, để lát nữa so sánh:

  ```bash
  uname -r
  ```

## 1. Cài gói để build kernel

```bash
sudo apt update
sudo apt install -y git bc bison flex libssl-dev make libncurses-dev tmux
```

## 2. Lấy script về Pi

Script nằm ở nhánh `feature/builtin-kernel` (chưa gộp vào `main`):

```bash
cd ~/Pi5-Driver-Project
git fetch
git checkout feature/builtin-kernel
```

## 3. Build kernel có driver built-in

### 3.1. Thử nhanh trước (không build)

```bash
cd ~/Pi5-Driver-Project
bash tools/build-builtin.sh --check
```

Lần đầu script tải mã nguồn kernel Raspberry Pi vào `~/rpi-linux` (khoảng vài trăm MB, cần mạng), đúng nhánh với kernel đang chạy (ví dụ đang chạy `6.12.x` thì lấy nhánh `rpi-6.12.y`). Sau đó chép driver vào `drivers/auxdisplay/`, khai báo trong `Kconfig` và `Makefile` của kernel, rồi bật `CONFIG_LCD2004_BTN=y`.

Kết quả đúng: cuối cùng in ra

```
    OK: CONFIG_LCD2004_BTN=y, phiên bản kernel mới: 6.12.xxx-v8-16k-lcd
Xong phần kiểm tra (--check), chưa build.
```

### 3.2. Build và cài

Build mất thời gian, nên chạy trong `tmux`: nếu SSH bị rớt hoặc lỡ đóng cửa sổ terminal, quá trình build vẫn tiếp tục.

**Gõ từng lệnh một, đợi lệnh trước xong rồi mới gõ lệnh sau. Không dán cả hai lệnh cùng lúc:** lệnh dán sau `tmux` sẽ không chạy trong tmux mà nằm chờ ở terminal bên ngoài.

1. Mở tmux:

   ```bash
   tmux
   ```

   Kết quả đúng: terminal xóa trắng, có thanh màu xanh lá ở dưới cùng, và dấu nhắc lệnh trống đang **chờ gõ lệnh**. Build chưa chạy ở bước này.

2. Gõ trong cửa sổ tmux đó:

   ```bash
   cd ~/Pi5-Driver-Project
   time bash tools/build-builtin.sh
   ```

   Kết quả đúng: màn hình chạy chữ liên tục (`==> 1.` ... rồi rất nhiều dòng `CC ...`). Còn chữ chạy là còn đang build.

Trong lúc build:
- Bước 6 của script có `sudo`, có thể hỏi `[sudo] password for ...:`. Phải gõ mật khẩu Pi rồi Enter, không thì script dừng đợi mãi. Màn hình đứng im lâu không có chữ mới thì xem dòng cuối có phải đang hỏi mật khẩu không.
- Ra ngoài mà vẫn để build chạy: nhấn `Ctrl+B`, thả ra, nhấn `D`. Vào xem lại (kể cả sau khi SSH rớt): `tmux attach`.
- Cuộn xem chữ cũ: `Ctrl+B`, thả ra, nhấn `[`, dùng mũi tên hoặc PageUp, nhấn `q` để thoát.
- Lệnh `time` in ra dòng `real ...` khi xong, là tổng thời gian build. Nên ghi lại để trả lời khi thầy hỏi "build mất bao lâu".

Script làm lần lượt:

| Bước | Làm gì |
|---|---|
| 1 | Tải mã nguồn kernel (đã có thì bỏ qua) |
| 2, 3 | Chép driver vào `drivers/auxdisplay/`, thêm mục `config LCD2004_BTN` vào `Kconfig` và dòng `obj-$(CONFIG_LCD2004_BTN) += lcd2004_btn.o` vào `Makefile` |
| 4 | Cấu hình cho Pi5 (`bcm2712_defconfig`), bật driver `=y`, đặt tên phiên bản `-v8-16k-lcd` |
| 5 | Build kernel (`Image.gz`) và các module. **Lâu nhất** |
| 6 | Cài module vào `/lib/modules/<phiên bản mới>/`, chép kernel thành `/boot/firmware/kernel_lcd.img` |
| 7 | Kiểm tra driver có trong danh sách built-in |

Kết quả đúng: cuối cùng in ra dòng `kernel/drivers/auxdisplay/lcd2004_btn.ko` và chữ `Xong.`

Vì sao phải cài cả module dù driver của nhóm là built-in: kernel mới đi kèm bộ module riêng của nó. Trên Pi5, driver của bộ điều khiển I2C là module (`CONFIG_I2C_DESIGNWARE_PLATFORM=m`). Thiếu module thì không có bus I2C, LCD không chạy, mất cả Wi-Fi. Tên phiên bản mới có đuôi `-lcd` nên module mới nằm ở thư mục riêng, không ghi đè module của kernel gốc.

## 4. Bật kernel mới

Script không tự sửa `config.txt`. Làm bằng tay để biết rõ cách quay lại.

1. Sao lưu rồi mở file:

   ```bash
   sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.bak
   sudo nano /boot/firmware/config.txt
   ```

2. Thêm dòng sau vào **cuối file** (sau dòng `[all]` cuối cùng, giống README bước 3.3):

   ```
   kernel=kernel_lcd.img
   ```

3. Lưu (Ctrl+O, Enter), thoát (Ctrl+X), khởi động lại:

   ```bash
   sudo reboot
   ```

## 5. Kiểm tra (mốc HW-8)

Sau khi boot, **không chạy `insmod`**.

| Lệnh | Kết quả đúng | Chứng minh điều gì |
|---|---|---|
| (nhìn LCD) | Màn hình chào 3 dòng tự hiện | Driver chạy lúc boot |
| `uname -r` | Có đuôi `-v8-16k-lcd` | Đang chạy kernel nhóm tự build |
| `lsmod \| grep lcd2004` | **Không in gì** | Driver không phải module |
| `grep lcd2004 /lib/modules/$(uname -r)/modules.builtin` | `kernel/drivers/auxdisplay/lcd2004_btn.ko` | Driver được biên dịch chung với kernel |
| `ls -l /dev/lcd2004` | Có file thiết bị | `misc_register()` đã chạy |
| `sudo dmesg \| grep lcd2004` | Có `probe ok` | `lcd_probe()` đã chạy |

Sau đó chạy lại `lcd_test`, `button_test`, `demo` như README mục 5. Các chương trình này không cần build lại, vì giao diện `/dev/lcd2004` giữ nguyên.

Khi đang chạy kernel built-in:
- **Không** `insmod` file `driver/lcd2004_btn.ko`. Driver đã có trong kernel nên sẽ báo lỗi.
- **Không** `rmmod` được. Muốn tắt driver thì quay về kernel gốc (bước 6).
- Sửa code driver thì phải chạy lại `bash tools/build-builtin.sh` rồi reboot. Lần sau nhanh hơn nhiều vì chỉ build lại phần thay đổi.

## 6. Quay về kernel gốc

1. Mở `config.txt`, xóa dòng `kernel=kernel_lcd.img` (hoặc thêm `#` ở đầu dòng), lưu, rồi `sudo reboot`.
2. Kiểm tra: `uname -r` trở lại như số đã ghi ở bước 0. Driver lại dùng bản `.ko` với `insmod` như README.

**Nếu Pi không boot được với kernel mới:** tắt nguồn, rút thẻ nhớ cắm vào laptop. Windows sẽ thấy một ổ tên `bootfs`, mở file `config.txt` trong đó bằng Notepad, xóa dòng `kernel=kernel_lcd.img`, lưu, cắm thẻ lại vào Pi. Pi sẽ boot bằng kernel gốc.

Muốn dọn hẳn (giải phóng dung lượng), sau khi đã quay về kernel gốc:

```bash
sudo rm /boot/firmware/kernel_lcd.img
sudo rm -rf /lib/modules/*-v8-16k-lcd
rm -rf ~/rpi-linux
```

## 7. Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| Bước 1 báo không tìm thấy nhánh (`Remote branch ... not found`) | Chỉ định nhánh bằng tay: `RPI_BRANCH=rpi-6.12.y bash tools/build-builtin.sh` |
| Báo `LỖI: CONFIG_LCD2004_BTN chưa được bật` | Kiểm tra mục config đã được thêm: `grep -n LCD2004 ~/rpi-linux/drivers/auxdisplay/Kconfig` |
| Đang build thì báo `Killed` (hết RAM) | Chạy lại với ít luồng hơn: `JOBS=2 bash tools/build-builtin.sh` (phần đã build xong không phải build lại) |
| Báo hết dung lượng (`No space left on device`) | Xóa bớt file, hoặc dùng thẻ nhớ lớn hơn. Cần khoảng 10 GB trống |
| Reboot xong `uname -r` vẫn là kernel cũ | Dòng `kernel=` viết sai tên file, hoặc nằm dưới `[cm4]`/`[cm5]`. Xem lại bước 4 |
| Boot được nhưng không có mạng, không có `/dev/i2c-1` | Module của kernel mới chưa được cài. Kiểm tra `ls /lib/modules/$(uname -r)`. Quay về kernel gốc (bước 6) rồi chạy lại script |
| LCD không sáng, `dmesg` không có `probe ok` | Overlay chưa bật: `cat /sys/bus/i2c/devices/1-0027/name` phải ra `lcd2004-btn` (README bước 3.4) |
