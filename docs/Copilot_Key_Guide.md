# Hướng Dẫn Kỹ Thuật: Mapping Phím Copilot, Cơ Chế Hoạt Động & Bài Học Tránh Lỗi

> **Tình trạng:** ✅ **Đã kích hoạt thành công 100% Native!**  
> Phím Copilot trên bàn phím Lenovo Legion Pro 7 Gen 10 hiện đã hoạt động hoàn hảo để mở ứng dụng với độ trễ 0.001s và 0% CPU overhead.

---

## 1. Cơ Chế Hoạt Động Cốt Lõi

1. **Tín hiệu phần cứng từ vi điều khiển ITE (8258):**
   - Khi bạn nhấn phím Copilot, chip bàn phím phát ra tổ hợp gồm `LeftMeta (125)` + `LeftShift (42)` + **`KEY_F23 (Keycode 193)`**.
   - Tín hiệu độc nhất chỉ xuất hiện khi bấm phím này chính là **Keycode `193`** (`KEY_F23`).
2. **Daemon lắng nghe sự kiện (`legion-profile-osd`):**
   - Daemon chạy dưới quyền người dùng (`systemctl --user`), dùng `select.poll()` để ngủ trong hàng đợi ngắt của kernel (0% CPU).
   - Ngay khi nhận được `Keycode 193` nhấn xuống ➔ Daemon đọc lệnh từ file cấu hình `~/.config/legion/config.json` và khởi chạy ứng dụng tương ứng ngay lập tức!

---

## 2. Cách Đổi Sang Ứng Dụng Hoặc Lệnh Khác (Rất Dễ Dàng)

Toàn bộ hành động của phím Copilot hiện được điều khiển độc lập qua file:
📂 **`~/.config/legion/config.json`**

Daemon tự động nạp lại cấu hình này mỗi lần bạn nhấn phím, **không cần restart service hay gõ lệnh gì thêm**!

### Ví dụ cấu hình:

* **Mở Alacritty (Mặc định hiện tại):**
  ```json
  {
    "copilot_command": "/usr/bin/alacritty"
  }
  ```
* **Mở Konsole (KDE Terminal):**
  ```json
  {
    "copilot_command": "konsole"
  }
  ```
* **Mở KRunner (Thanh tìm kiếm & chạy lệnh thông minh của KDE):**
  ```json
  {
    "copilot_command": "krunner"
  }
  ```
* **Chụp ảnh màn hình vùng chọn (KDE Spectacle):**
  ```json
  {
    "copilot_command": "spectacle -r"
  }
  ```
* **Chạy một script cá nhân bất kỳ:**
  ```json
  {
    "copilot_command": "/home/quangtm/bin/my_ai_agent.sh"
  }
  ```

---

## 3. Nếu Muốn Map Thành Một Phím Khác (Key-to-Key Remapping) Thì Sao?

Cần phân biệt rõ 2 loại ánh xạ:
1. **Phím ➔ Lệnh / Ứng dụng (Key-to-Command):**
   - Đây là những gì toolkit hiện tại của chúng ta đang làm: 100% Native, chạy qua daemon Python, không cần can thiệp tầng sâu, cực kỳ an toàn và ổn định.
2. **Phím ➔ Phím khác (Key-to-Key, ví dụ: Copilot ➔ Right Control hoặc phím Menu):**
   - Trong Wayland, các ứng dụng không được phép tự tạo phím giả (synthetic keystroke injection) vào các cửa sổ khác vì lý do bảo mật chống keylogger.
   - Để biến phím Copilot thành phím Right Control, tín hiệu giả lập phải được bơm ngược lại vào Linux kernel qua driver **`/dev/uinput`**.
   - Nếu sau này bạn muốn đổi Copilot thành Right Control, giải pháp tốt nhất là sử dụng **`keyd`** với layer chord như tác giả ThinkPad trên Reddit đã chia sẻ:
     ```ini
     # /etc/keyd/default.conf
     [ids]
     *
     [main]
     f23+leftshift+leftmeta = rightcontrol
     ```

---

## 4. Bài Học Kỹ Thuật: Làm Sao Để Không Mắc Lại Sai Lầm Cũ?

Trong quá trình triển khai, chúng ta đã gặp 2 "cái bẫy" lớn:

### ⚠️ Cái bẫy 1: XKB và Giao diện GUI Shortcuts của Desktop
- **Sai lầm:** Cố gắng nhấn phím Copilot trong giao diện cài đặt phím tắt của KDE.
- **Nguyên nhân:** XKB nuốt tổ hợp Shift+Meta+F23 thành `XF86Assistant` và nhịp ngắt vi điều khiển quá nhanh khiến widget GUI bị kẹt ở `...`.
- **Kinh nghiệm:** Với các phím OEM đặc thù (Copilot, phím macro game, v.v.), luôn kiểm tra bằng `test-hotkey` để xem kernel nhận diện được Keycode thực sự hay không. Nếu kernel nhận được, hãy hook trực tiếp từ tầng evdev thay vì dựa vào GUI của desktop.

### ⚠️ Cái bẫy 2: Symlink trong `/dev/input/` và `tmpfiles.d`
- **Sai lầm:** Dùng `tmpfiles.d` với cờ `z` nhắm vào đường dẫn `/dev/input/by-path/...` để cấp quyền.
- **Nguyên nhân:** Theo đặc tả của Linux (`man tmpfiles.d`): **`Plain 'z' does not follow symlinks`**. Đường dẫn `/dev/input/by-path/...` thực chất là một symlink trỏ tới `/dev/input/event4`. Vì cờ `z` không đi xuyên qua symlink, nên file thiết bị thực sự `/dev/input/event4` không hề được cấp quyền!
- **Kinh nghiệm cốt lõi (Nguyên tắc chuẩn trong Linux):**
  1. Với các file tĩnh trong **`/sys/`** (như `conservation_mode`, `platform_profile`): Dùng **`/etc/tmpfiles.d/*.conf`** là chuẩn nhất vì đây là đường dẫn thật trên RAM.
  2. Với các thiết bị động trong **`/dev/input/`**: Luôn dùng **`/etc/udev/rules.d/*.rules`**! Udev hoạt động ở cấp độ nhân kernel khi thiết bị vừa được cắm vào, nó gán quyền trực tiếp vào node phần cứng trước khi bất kỳ symlink nào được tạo ra.

---

## 5. Cấu Hình Udev Vĩnh Viễn Cho Bàn Phím Legion

Để quyền đọc bàn phím ITE được duy trì tự động mỗi khi khởi động lại máy (không cần phải gõ lại lệnh `chmod`):

Đã tạo sẵn file udev rule:
📂 **`/DATA1/quang_dev/legion-linux-toolkit/udev/99-lenovo-keyboard.rules`**
```udev
KERNEL=="event*", SUBSYSTEM=="input", ATTRS{name}=="ITE Tech. Inc. ITE Device(8258) Keyboard", MODE="0666"
```

👉 **Chỉ cần copy vào `/etc/udev/rules.d/` một lần duy nhất:**
```bash
sudo cp /DATA1/quang_dev/legion-linux-toolkit/udev/99-lenovo-keyboard.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=input
```
Kể từ giờ, mỗi khi bạn bật máy, Linux kernel sẽ tự động cấp quyền `0666` cho bàn phím và phím Copilot luôn sẵn sàng hoạt động!

---

## 6. Cơ Chế Báo Lỗi Trực Quan (OSD Error Feedback)

Hệ thống đã được bổ sung cơ chế kiểm định lỗi đa tầng và cảnh báo trực tiếp bằng thông báo OSD trên màn hình (`notify-send` mức độ `critical`):

1. **Lỗi cú pháp JSON trong `config.json`:** Hiện cảnh báo ⚠️ **"Config Warning: Invalid JSON syntax"** và tự động fallback về Alacritty.
2. **Cấu hình rỗng hoặc null:** Hiện cảnh báo ⚠️ **"Config Warning: copilot_command is empty"** và fallback về Alacritty.
3. **Cú pháp lệnh shell không hợp lệ (e.g. thiếu dấu ngoặc kép):** Hiện lỗi ❌ **"Config Error: Invalid command syntax"**.
4. **Ứng dụng không tồn tại trên máy (Binary Not Found):** Hiện thông báo ❌ **"App Not Found: Command not found in PATH"** kèm tên lệnh lỗi để bạn dễ dàng sửa lại config.
5. **Lỗi khởi chạy tiến trình (Launch Error):** Hiện thông báo ❌ **"Launch Error: Failed to execute process"**.

---

## 7. Tính Năng Kép: Bấm Nhanh (Tap) vs Nhấn Giữ (Hold Candidate Menu)

Phím Copilot hiện hỗ trợ **2 chế độ kích hoạt thông minh**:

1. **Bấm nhả nhanh (Tap < 0.3s):** Khởi chạy ngay ứng dụng mặc định (`copilot_tap`, ví dụ: Alacritty).
2. **Nhấn giữ lâu (Hold >= 0.3s):** Tự động bật **Popup Menu ứng viên (KDE kdialog)** liệt kê danh sách các ứng dụng để bạn chọn nhanh!

### Cấu hình trong `~/.config/legion/config.json`:

```json
{
  "copilot_tap": "/usr/bin/alacritty",
  "copilot_candidates": [
    { "key": "1", "name": "Alacritty Terminal", "exec": "/usr/bin/alacritty" },
    { "key": "2", "name": "Konsole Terminal", "exec": "konsole" },
    { "key": "3", "name": "KRunner Spotlight Search", "exec": "krunner" },
    { "key": "4", "name": "Chụp ảnh màn hình (Spectacle)", "exec": "spectacle -r" },
    { "key": "5", "name": "Antigravity IDE", "exec": "antigravity-ide" }
  ]
}
```

- Khi giữ phím Copilot, một hộp thoại menu KDE xuất hiện: Bạn chỉ cần gõ phím số `1`, `2`, `3`... hoặc dùng phím mũi tên rồi nhấn `Enter`.
- Bấm `Esc` hoặc click ra ngoài để đóng menu mà không chạy app nào.
