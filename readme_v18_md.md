# Huy Bao Game V18 — Standard Desktop Edition

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

Phiên bản **V18** được thiết kế tối ưu cho **máy tính cá nhân (PC / Laptop)** với tiêu chí gọn nhẹ, tốc độ xử lý nhanh, ít tốn tài nguyên và ổn định khi chạy hàng loạt qua pipe `FFmpeg` + `OpenCV`.

> **Lưu ý sử dụng & giới hạn kỹ thuật:** Chỉ sử dụng công cụ này cho các video do bạn sở hữu hoặc có quyền chỉnh sửa hợp pháp. Thuật toán `inpaint` chỉ nội suy xấp xỉ từ vùng lân cận chứ không thể khôi phục nguyên bản pixel đã bị che khuất.

---

## Tính năng nổi bật

* **Xử lý trực tiếp qua Pipe (`rawvideo`):** Giải mã và mã hóa trực tiếp bằng `FFmpeg` (`libx264`, `yuv420p`, `+faststart`), không tạo tệp video trung gian mất chất lượng.
* **Tô đen dải trên tùy chỉnh (`--top-height`):** Tự động kiểm tra chiều cao hợp lệ theo khung hình thực tế; có thể tắt bằng `--no-clear-top`.
* **Mặt nạ watermark ổn định theo thời gian (EMA + Scene-Cut):** Lọc vùng sáng/ít bão hòa trong không gian màu HSV trên vùng `ROI`, kết hợp bộ nhớ trung bình trượt (EMA) tự thích nghi nhanh khi chuyển cảnh (`--scene-cut-delta`).
* **Linh hoạt thuật toán nội suy:** Hỗ trợ `telea` (nhanh) và `ns` (Navier-Stokes) qua `--inpaint-method`, hoặc bỏ qua hoàn toàn bằng `--no-inpaint`.
* **An toàn luồng dữ liệu & file tạm:** Sử dụng `TemporaryFile()` cho `stderr` của FFmpeg để tránh nghẽn pipe, tự động bù byte `0` nếu khung hình cuối bị thiếu dữ liệu nhẹ và dọn dẹp tệp tạm an toàn.

---

## Yêu cầu hệ thống & Cài đặt

1. **Cài đặt FFmpeg** và đảm bảo lệnh `ffmpeg` cùng `ffprobe` có trong `PATH` của hệ thống.
2. **Cài đặt thư viện Python:**

```bash
pip install opencv-python numpy
```

---

## Hướng dẫn sử dụng

### 1. Chạy thử nhanh (Preview 15 giây đầu)

Nên chạy thử đoạn ngắn để kiểm tra vị trí `ROI` và độ nét trước khi xuất toàn bộ video:

```bash
python huy_bao_v18.py input.mp4 preview.mp4 --preview-seconds 15
```

### 2. Xử lý toàn bộ video (mặc định)

```bash
python huy_bao_v18.py input.mp4 output.mp4
```

### 3. Tùy chỉnh vùng ROI, ngưỡng màu và thuật toán Inpaint

```bash
python huy_bao_v18.py input.mp4 output.mp4 \
  --top-height 110 \
  --roi 155 565 570 650 \
  --threshold 142 \
  --max-saturation 105 \
  --inpaint-method ns \
  --crf 18 \
  --preset medium
```

### 4. Chỉ tô đen dải trên, bỏ qua bước Inpaint

```bash
python huy_bao_v18.py input.mp4 output.mp4 --no-inpaint
```

---

## Bảng tham số dòng lệnh

| Tham số | Mặc định | Mô tả |
| :--- | :--- | :--- |
| `input` | *(Bắt buộc)* | Đường dẫn tệp video đầu vào. |
| `output` | *(Bắt buộc)* | Đường dẫn tệp video MP4 đầu ra. |
| `--top-height` | `110` | Số pixel tô đen ở mép trên khung hình. |
| `--no-clear-top` | `False` | Bỏ qua bước tô đen dải trên. |
| `--no-inpaint` | `False` | Bỏ qua bước dò mask và inpaint trên ROI. |
| `--roi X1 Y1 X2 Y2` | `155 565 570 650` | Tọa độ vùng tìm kiếm watermark (theo pixel). |
| `--threshold` | `142` | Ngưỡng độ sáng `V` trong không gian HSV (`0..255`). |
| `--max-saturation` | `105` | Ngưỡng độ bão hòa `S` tối đa (`0..255`). |
| `--dilate` | `2` | Độ giãn nở mask (`0..12`). |
| `--radius` | `4.0` | Bán kính nội suy inpaint (`0.1..20`). |
| `--inpaint-method` | `telea` | Thuật toán inpaint: `telea` hoặc `ns`. |
| `--mask-memory` | `0.78` | Hệ số nhớ EMA cơ bản (`0..0.98`). |
| `--scene-cut-delta` | `24.0` | Ngưỡng biến thiên độ sáng ROI kích hoạt thích nghi nhanh. |
| `--mask-consensus` | `0.38` | Ngưỡng ổn định của mask EMA (`0..1`). |
| `--crf` | `18` | Chất lượng nén `libx264` (`0..51`). |
| `--preset` | `medium` | Tốc độ nén `libx264` (`ultrafast` đến `veryslow`). |
| `--preview-seconds` | `0` | Chỉ xử lý `N` giây đầu (`0` = toàn bộ video). |
| `--keep-temp` | `False` | Giữ lại tệp video không tiếng tạm thời sau khi chạy. |

---

## Bản quyền & Giấy phép (Copyright & License)

Copyright © 2026 **Huy Bao Game** (`ghuy021112-cpu`). All rights reserved.

Dự án này được phát hành theo giấy phép **GNU Affero General Public License v3.0 (AGPL-3.0)**.

* Bạn được tự do sử dụng, nghiên cứu, sửa đổi và phân phối lại mã nguồn với điều kiện giữ nguyên thông báo bản quyền của tác giả.
* Mọi bản sửa đổi, phái sinh hoặc triển khai cung cấp dịch vụ qua mạng đều **bắt buộc phải công khai mã nguồn** dưới cùng giấy phép **AGPL-3.0**.
* Xem toàn văn giấy phép tại tệp `LICENSE` trong kho lưu trữ hoặc tại [gnu.org/licenses/agpl-3.0](https://www.gnu.org/licenses/agpl-3.0).