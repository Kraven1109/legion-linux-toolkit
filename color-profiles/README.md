# Color Profiles & HDR/Dolby Vision Guide - Lenovo Legion Pro 7 16IAX10H

- **Ngày sao lưu:** 2026-09-15
- **Dòng máy:** Lenovo Legion Pro 7 16IAX10H (Type 83F5, Name: `QLEGION`)
- **Tấm nền màn hình:** Samsung Display OLED (Hardware ID: `MONITOR\SDC420B`)
- **Chứng nhận hiển thị:** VESA DisplayHDR 1000 True Black / Dolby Vision

---

## 1. Danh sách file trong bộ backup

### Các Profile màu (.icm)
| Tên File | Không gian màu & Mục đích sử dụng |
| :--- | :--- |
| `TPLCD_420B_Default.icm` | Profile màu mặc định từ hãng |
| `TPLCD_420B_sRGB.icm` | Chuẩn sRGB (dùng hàng ngày, duyệt web, văn phòng, chống rực màu) |
| `TPLCD_420B_AdobeRGB.icm` | Chuẩn Adobe RGB (đồ họa in ấn) |
| `TPLCD_420B_DCIP3.icm` | Chuẩn DCI-P3 (chuẩn rạp chiếu phim kỹ thuật số) |
| `TPLCD_420B_DisplayP3.icm` | Chuẩn Display P3 (gamma sRGB + dải màu P3) |
| `TPLCD_420B_REC709.icm` | Chuẩn Rec.709 (sản xuất video/truyền hình) |
| `TPLCD_420B_Native.icm` | Dải màu tối đa nguyên bản của tấm nền OLED |

### Báo cáo cân chỉnh nhà máy (*_Quality.txt)
- Các file báo cáo từ công cụ `Display Factory Calibration Tool 2.26.10`. Chứa toàn bộ thông số tọa độ điểm trắng (Whitepoint D65), Gamma 2.2, Target Luminosity, RGB Normalized Target curve được đo trực tiếp tại xưởng trên panel này.

### Cấu hình Dolby Vision (.dv)
- `PQCOnfig_SDC420B.dv`: Chứa thông số đường cong SMPTE ST 2084 Perceptual Quantizer (PQ), độ sáng đỉnh và dữ liệu Dynamic Tone-Mapping độc quyền được cấp phép cho Lenovo.

---

## 2. Hướng dẫn sử dụng trên Windows 10 / 11

### Khôi phục Color Profiles:
1. Copy toàn bộ file `.icm`, `.txt` và `.dv` vào thư mục:
   ```cmd
   C:\Windows\System32\spool\drivers\color\
   ```
2. Mở app **X-Rite Color Assistant** từ khay hệ thống để chuyển đổi nhanh qua lại giữa các profile màu.

### Kích hoạt Dolby Vision:
1. Đảm bảo file `PQCOnfig_SDC420B.dv` đã nằm trong `C:\Windows\System32\spool\drivers\color\`.
2. Bật HDR trong **Windows Settings** > **System** > **Display** > **Use HDR** = **On** (hoặc nhấn `Win + Alt + B`).
3. Cài ứng dụng **Dolby Access** / **Dolby Vision Extensions** từ Microsoft Store (nếu vừa cài lại Windows sạch).
4. Mở video Dolby Vision trên app Netflix, Microsoft Edge hoặc app Movies & TV: Hệ thống sẽ tự động kích hoạt logo Dolby Vision và thực hiện Dynamic Tone-Mapping.

---

## 3. Hướng dẫn thiết lập trên CachyOS / Linux (KDE Plasma 6 + Wayland)

### Bước 1: Nạp Profile màu ICC vào Linux
Mở Terminal trên CachyOS và chạy:
```bash
# Tạo thư mục quản lý màu người dùng
mkdir -p ~/.local/share/color/icc

# Copy các file profile từ thư mục backup sang
cp ~/OneDrive/CloudSync/Software/16iax10h-color-profiles/TPLCD_420B_*.icm ~/.local/share/color/icc/
```

### Bước 2: Áp dụng Color Profile trong KDE Plasma 6 Wayland
1. Mở **System Settings** > **Display & Monitor** > **Display Configuration**.
2. Chọn màn hình laptop (`Built-in Display` / `SDC420B`).
3. Tại mục **Color Profile**, chọn **Add / Import Profile** và trỏ đến `~/.local/share/color/icc/`:
   - **Khuyên dùng hàng ngày (SDR):** Chọn `TPLCD_420B_sRGB.icm` để giới hạn (clamp) dải màu OLED về chuẩn sRGB, tránh tình trạng màu đỏ/xanh bị quá rực (neon/oversaturated) khi lướt web, làm việc.
   - **Khi làm đồ họa:** Đổi sang `TPLCD_420B_DisplayP3.icm` hoặc `TPLCD_420B_Native.icm` để hiển thị trọn vẹn 100% dải màu DCI-P3.

### Bước 3: Bật HDR trên Wayland
1. Trong giao diện **Display Configuration**, gạt bật công tắc **HDR** sang **On**.
2. KWin Wayland sẽ tự động đọc chip EDID của panel `SDC420B` để áp dụng độ tương phản vô cực (True Black 0 nits).
3. Kéo thanh trượt **SDR content brightness** ở mức **150 – 200 nits** để giao diện desktop không bị chói mắt.

### Bước 4: Xem phim Dolby Vision & HDR trên CachyOS với `mpv`
*Lưu ý: File `.dv` là định dạng độc quyền đóng của Dolby chỉ dùng trên Windows. Tuy nhiên, trên Linux bạn vẫn có thể xem trọn vẹn phim Dolby Vision nhờ trình phát `mpv` và backend `libplacebo`:*

1. Cài đặt `mpv`:
   ```bash
   sudo pacman -S --needed mpv
   ```

2. Tạo file cấu hình `~/.config/mpv/mpv.conf`:
   ```ini
   # Bộ dựng hình Next-Gen hỗ trợ Wayland HDR & Vulkan
   vo=gpu-next
   gpu-api=vulkan
   target-colorspace-hint=yes

   # Tự động đọc và Dynamic Tone-Mapping metadata Dolby Vision RPU
   tone-mapping=bt.2390
   target-peak=auto
   target-contrast=auto
   ```

3. Mở phim Dolby Vision bằng `mpv`:
   ```bash
   mpv ten_phim_dolby_vision.mkv
   ```
   `mpv` sẽ tự động giải mã metadata Dolby Vision theo từng khung hình và tone-map trực tiếp ra màn hình OLED với độ sâu màu và tương phản chuẩn xác.