# Lenovo Legion (16IAX10H) Battery Conservation Mode on CachyOS

Reference guide for controlling Lenovo Battery Conservation Mode (cap battery charge at 75–80% to protect battery health) without requiring root password prompts.

---

## 1. Quick CLI Tool (`lbat`)

A dedicated CLI script is installed at `~/.local/bin/lbat`. It works in any terminal (Bash, Zsh, Fish) and requires **no sudo password**.

### Commands:
```bash
lbat           # View battery level (%) and current conservation status
lbat on         # Enable conservation mode (cap charging at ~80% for desktop/plugged use)
lbat off        # Disable conservation mode (charge to 100% before going mobile)
lbat toggle     # Quickly toggle between 80% cap and 100% full charge
lbat help       # Show command options
```

*Alias shortcuts:*
* `lbat on`, `bat save`, `bat 80` $\rightarrow$ Turn on 80% cap.
* `lbat off`, `bat full`, `bat 100` $\rightarrow$ Turn on 100% full charge.

---

## 2. Under the Hood & Non-Root Permission

### Kernel Sysfs Node:
Lenovo IdeaPad / Legion laptops expose battery conservation through the ACPI interface:
```text
/sys/bus/platform/devices/VPC2004:00/conservation_mode
```
* Value `1`: Battery stops charging at ~75–80%.
* Value `0`: Battery charges all the way to 100%.

### Sudo-less Setup (`/etc/tmpfiles.d/lenovo_conservation.conf`):
To allow non-root users to toggle this node without prompting for `sudo`, a systemd tmpfiles rule is set up:
```text
z /sys/bus/platform/devices/VPC2004:00/conservation_mode 0666 root root -
```
This rule is automatically applied on every boot by `systemd-tmpfiles`.


> **Giải thích cú pháp `tmpfiles.d`:**
> * `z` *(Action)*: Điều chỉnh quyền (permission) nếu node đã tồn tại, không tự ý tạo mới nếu file chưa có.
> * `Path`: Đường dẫn sysfs đến node pin của Lenovo.
> * `0666` *(Mode)*: Cấp quyền đọc/ghi (`rw-rw-rw-`), cho phép user thường ghi dữ liệu mà không cần sudo.
> * `root root` *(User / Group)*: Giữ quyền sở hữu thuộc về root.
> * `-` *(Age / Cleanup)*: Bỏ qua quy tắc dọn dẹp file theo thời gian.
>
> **Vì sao cần dùng cơ chế này?**
> Thư mục `/sys` là filesystem ảo trong RAM, được kernel tạo mới mỗi lần bật máy với quyền mặc định `0644` (chỉ root được ghi). Nhờ quy tắc `tmpfiles.d`, systemd sẽ tự động gán lại quyền `0666` ngay khi vừa boot xong, giúp các script hoặc phím tắt người dùng chạy tức thì mà không bao giờ bị hỏi mật khẩu sudo.


---

## 3. Keyboard Shortcut in KDE Plasma (Optional)

To bind `lbat toggle` to a keyboard shortcut (e.g. `Meta + F1` or `Meta + B`):
1. Open **System Settings** $\rightarrow$ **Shortcuts** $\rightarrow$ **Custom Commands**.
2. Click **Add New** $\rightarrow$ **Command**.
3. Name: `Toggle Battery Conservation`.
4. Command: `/home/quangtm/.local/bin/lbat toggle`.
5. Trigger: Assign your preferred hotkey.
*(A desktop notification will automatically pop up showing the new mode).*
