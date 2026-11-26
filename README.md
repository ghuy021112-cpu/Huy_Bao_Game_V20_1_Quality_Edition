# Huy Bao Game — Video Overlay Removal & Restoration Suite

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

Bộ công cụ xử lý và phục hồi vùng phủ (overlay/watermark) trên video bằng `FFmpeg`, `OpenCV` và `AI (LaMa)`. Chỉ sử dụng cho video bạn sở hữu hoặc có quyền chỉnh sửa hợp pháp.

---

## Chọn phiên bản phù hợp

| Phiên bản | Môi trường | Cơ chế chính | Ưu điểm |
| :--- | :--- | :--- | :--- |
| **V18** (`huy_bao_v18.py`) | Máy tính thường (PC / Laptop) | Tô đen dải trên + lọc màu HSV + EMA + `OpenCV Inpaint` | Nhanh, nhẹ, chạy hàng loạt tốt |
| **V20.1 Quality Edition** (`huy_bao_v20_1.py`) | Máy trạm / Siêu máy tính | Cửa sổ thời gian 2 chiều + `DIS Optical Flow` (tối ưu Bounding Box) + `LaMa AI` | Tái tạo nền thật từ các frame lân cận, kiểm chứng frame đầu ra |

---

## Cài đặt nhanh

```bash
# 1. Cài FFmpeg (Ubuntu/Debian)
sudo apt update && sudo apt install -y ffmpeg python3-venv

# 2. Cài thư viện cơ bản (dùng cho cả V18 và V20.1)
python3 -m venv .venv && source .venv/bin/activate
pip install opencv-python numpy

# 3. Tùy chọn AI LaMa (chỉ cần cho V20.1 khi bật --lama)
# Cài PyTorch theo CUDA từ https://pytorch.org/get-started/locally/ rồi chạy:
pip install simple-lama-inpainting "Pillow>=10"
```

---

## Lệnh chạy mẫu

### 1. Bản V18 (Máy tính thường — nhanh, tự động theo ROI)

```bash
# Chạy thử 15 giây đầu
python huy_bao_v18.py input.mp4 preview.mp4 --preview-seconds 15

# Chạy toàn bộ video
python huy_bao_v18.py input.mp4 output.mp4 --roi 155 565 570 650 --inpaint-method telea
```

### 2. Bản V20.1 Quality Edition (Siêu máy tính / Máy trạm — chất lượng cao)

```bash
# Dùng ảnh mask.png (trắng = vùng xóa, đen = giữ nguyên) + LaMa AI
python huy_bao_v20_1.py \
  --input input.mp4 --output restored.mp4 \
  --mask mask.png --window 4 --flow-quality ultra --lama

# Dùng lọc màu HSV tự động (không cần ảnh mask)
python huy_bao_v20_1.py \
  --input input.mp4 --output restored.mp4 \
  --hsv-lower 20 100 150 --hsv-upper 40 255 255 --window 4 --lama
```

---

## Lưu ý kỹ thuật

* **V18** dùng `telea` (nhanh) hoặc `ns` (mượt biên hơn), phù hợp nền ít nhiễu và cần tốc độ.
* **V20.1** tối ưu tính toán trên vùng Bounding Box quanh mask, dùng `DIS Optical Flow` trên CPU và `LaMa` trên GPU CUDA (nếu có); chỉ tổng hợp nội dung hợp lý chứ không khôi phục nguyên bản pixel bị che ở mọi frame.

---

## Bản quyền & Giấy phép

Copyright © 2026 **Huy Bao Game** (`ghuy021112-cpu`). All rights reserved.

Phát hành theo giấy phép **GNU Affero General Public License v3.0 (AGPL-3.0)**. Mọi bản sửa đổi hoặc triển khai dịch vụ qua mạng đều phải công khai mã nguồn theo cùng giấy phép. Xem chi tiết tại tệp `LICENSE` hoặc [gnu.org/licenses/agpl-3.0](https://www.gnu.org/licenses/agpl-3.0).
