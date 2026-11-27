# Huy Bao Game — Bộ Công Cụ Xóa Overlay & Phục Hồi Video

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-green.svg)](https://www.python.org/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-Required-orange.svg)](https://ffmpeg.org/)

Bộ công cụ dòng lệnh (CLI) xử lý và phục hồi các vùng bị che phủ (logo, watermark, thanh thông báo tĩnh) trên video bằng **FFmpeg**, **OpenCV** và **AI (LaMa)**.

> **Tuyên bố trách nhiệm & Giới hạn kỹ thuật:**
> * Chỉ sử dụng công cụ này cho các video thuộc quyền sở hữu của bạn hoặc video bạn được cấp phép chỉnh sửa hợp pháp.
> * Các thuật toán nội suy (`OpenCV Inpaint` và `LaMa AI`) chỉ tái tạo hoặc tổng hợp nội dung hợp lý về mặt thị giác, không thể khôi phục nguyên bản dữ liệu gốc nếu pixel đó bị che khuất trong mọi khung hình.

---

## 1. Kiến trúc & Chọn phiên bản phù hợp

Dự án cung cấp hai phiên bản tối ưu cho hai cấu hình phần cứng khác nhau:

| Tiêu chí | V18 (`Huy_Bao_Game_v18.py`) | V20.1 Quality Edition (`huy_bao_v20_1.py`) |
| :--- | :--- | :--- |
| **Môi trường phần cứng** | Máy tính cá nhân (PC / Laptop CPU) | Máy trạm hiệu năng cao / Siêu máy tính (CPU đa nhân + GPU CUDA) |
| **Cách xác định vùng xóa** | Tô đen dải trên (`--top-height`) + lọc màu HSV tự động theo vùng `ROI` | Ảnh mặt nạ `--mask` PNG chuẩn từng pixel, lọc màu HSV hoặc kết hợp cả hai |
| **Thuật toán phục hồi** | Bộ lọc EMA thích nghi chuyển cảnh + `OpenCV Inpaint` (`telea` / `ns`) | Cửa sổ thời gian 2 chiều + `DIS Optical Flow` (tối ưu Bounding Box) + dự phòng `LaMa AI` |
| **Tốc độ & Tài nguyên** | Rất nhanh, nhẹ, phù hợp chạy hàng loạt | Chậm hơn, ưu tiên giữ chi tiết nền thật từ các khung hình lân cận |

---

## 2. Cấu trúc kho lưu trữ

```text
├── Huy_Bao_Game_v18.py          # Phiên bản tiêu chuẩn chạy nhanh trên PC/Laptop
├── huy_bao_v20_1.py             # Phiên bản chất lượng cao (Temporal Optical Flow + LaMa AI)
├── requirements_v20.1.txt       # Thư viện cơ bản (opencv-python, numpy)
├── requirements-ai_v20.1.txt    # Thư viện AI tùy chọn cho V20.1 (simple-lama-inpainting, Pillow)
├── LICENSE                      # Toàn văn giấy phép AGPL-3.0
└── README.md                    # Tài liệu hướng dẫn sử dụng
```

---

## 3. Cài đặt môi trường

### Bước 1: Cài đặt FFmpeg
Đảm bảo cả hai lệnh `ffmpeg` và `ffprobe` đã được cài đặt và thêm vào `PATH` của hệ thống:

```bash
# Trên Ubuntu / Debian
sudo apt update && sudo apt install -y ffmpeg python3 python3-venv python3-pip
```

### Bước 2: Cài đặt thư viện Python cơ bản (Dùng cho cả V18 và V20.1)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements_v20.1.txt
```

### Bước 3: Cài đặt tùy chọn AI LaMa (Chỉ dành cho V20.1 khi dùng cờ `--lama`)
Cài đặt **PyTorch** tương thích với phiên bản CUDA của máy chủ từ [pytorch.org](https://pytorch.org/get-started/locally/), sau đó chạy:

```bash
pip install -r requirements-ai_v20.1.txt
```

Kiểm tra nhận diện GPU CUDA:

```bash
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```

---

## 4. Hướng dẫn sử dụng chi tiết

### A. Phiên bản V18 (`Huy_Bao_Game_v18.py` — Máy tính thường)

**1. Chạy thử nhanh (Preview 15 giây đầu):**
Luôn nên chạy thử đoạn ngắn để kiểm tra tọa độ `ROI` và chất lượng xử lý trước khi xuất toàn bộ video:

```bash
python Huy_Bao_Game_v18.py input.mp4 preview.mp4 --preview-seconds 15
```

**2. Chạy toàn bộ video với tham số mặc định:**

```bash
python Huy_Bao_Game_v18.py input.mp4 output.mp4
```

**3. Tùy chỉnh vùng ROI, ngưỡng màu HSV và thuật toán Inpaint:**

```bash
python Huy_Bao_Game_v18.py input.mp4 output.mp4 \
  --top-height 110 \
  --roi 155 565 570 650 \
  --threshold 142 \
  --max-saturation 105 \
  --inpaint-method ns \
  --crf 18 \
  --preset medium
```

**4. Chỉ tô đen dải trên, bỏ qua bước Inpaint:**

```bash
python Huy_Bao_Game_v18.py input.mp4 output.mp4 --no-inpaint
```

#### Bảng tham số chính của V18

| Tham số | Mặc định | Ý nghĩa |
| :--- | :--- | :--- |
| `input` / `output` | *(Bắt buộc)* | Đường dẫn video đầu vào và tệp MP4 đầu ra. |
| `--top-height` | `110` | Chiều cao (pixel) tô đen ở mép trên khung hình. |
| `--no-clear-top` | `False` | Tắt tính năng tô đen dải trên. |
| `--no-inpaint` | `False` | Tắt bước dò mask và inpaint trên vùng `ROI`. |
| `--roi X1 Y1 X2 Y2` | `155 565 570 650` | Tọa độ vùng quét watermark (pixel). |
| `--threshold` | `142` | Ngưỡng độ sáng `V` tối thiểu trong hệ HSV (`0..255`). |
| `--max-saturation` | `105` | Ngưỡng độ bão hòa `S` tối đa trong hệ HSV (`0..255`). |
| `--dilate` / `--radius` | `2` / `4.0` | Độ giãn nở mask và bán kính nội suy. |
| `--inpaint-method` | `telea` | Thuật toán nội suy: `telea` (nhanh) hoặc `ns` (Navier-Stokes). |
| `--scene-cut-delta` | `24.0` | Ngưỡng thay đổi độ sáng ROI để reset nhanh bộ nhớ mask EMA. |
| `--crf` / `--preset` | `18` / `medium` | Chất lượng và tốc độ nén H.264 (`libx264`). |
| `--preview-seconds` | `0` | Chỉ xuất `N` giây đầu (`0` = xuất toàn bộ video). |

---

### B. Phiên bản V20.1 Quality Edition (`huy_bao_v20_1.py` — Máy trạm / Siêu máy tính)

#### Chuẩn bị ảnh Mask (`--mask`)
Tạo một ảnh `.png` thang độ xám có **đúng kích thước chiều rộng $\times$ chiều cao** của video gốc:
* **Màu trắng (`255`):** Vùng cần loại bỏ và phục hồi.
* **Màu đen (`0`):** Vùng giữ nguyên gốc.

**1. Chạy với ảnh Mask vẽ tay + DIS Optical Flow Ultra + LaMa AI:**

```bash
python huy_bao_v20_1.py \
  --input input.mp4 \
  --output restored.mp4 \
  --mask mask.png \
  --window 4 \
  --flow-quality ultra \
  --lama \
  --preset slow \
  --crf 16
```

**2. Kết hợp ảnh Mask tĩnh và bộ lọc màu HSV động:**

```bash
python huy_bao_v20_1.py \
  --input input.mp4 \
  --output restored.mp4 \
  --mask mask.png \
  --hsv-lower 20 100 150 \
  --hsv-upper 40 255 255 \
  --hsv-dilate 2 \
  --window 4 \
  --flow-quality ultra \
  --lama
```

**3. Chạy hoàn toàn tự động bằng màu HSV (không cần ảnh PNG mask):**

```bash
python huy_bao_v20_1.py \
  --input input.mp4 \
  --output restored.mp4 \
  --hsv-lower 20 100 150 \
  --hsv-upper 40 255 255 \
  --window 3 \
  --flow-quality medium
```

#### Bảng tham số chính của V20.1

| Tham số | Mặc định | Ý nghĩa |
| :--- | :--- | :--- |
| `--input` / `--output` | *(Bắt buộc)* | Đường dẫn video đầu vào và tệp MP4 đầu ra. |
| `--mask` | `None` | Ảnh PNG đen/trắng cùng kích thước video (`trắng = phục hồi`). |
| `--hsv-lower` / `--hsv-upper` | `None` | Dải màu `H S V` (`0..255`) để tạo mask tự động theo từng frame. |
| `--hsv-dilate` | `2` | Độ giãn nở của mask HSV. |
| `--window` | `4` | Số khung hình lân cận mỗi bên trong cửa sổ thời gian (`1..8`). |
| `--flow-quality` | `ultra` | Chất lượng DIS Optical Flow: `fast`, `medium`, `ultra`. |
| `--bbox-margin` | `48` | Lề ngữ cảnh (pixel) mở rộng quanh vùng Bounding Box của mask. |
| `--inpaint` | `telea` | Thuật toán OpenCV dự phòng: `telea` hoặc `ns`. |
| `--lama` | `False` | Bật mô hình AI LaMa cho các điểm ảnh chưa khôi phục được từ thời gian. |
| `--audio` / `--audio-bitrate` | `aac` / `192k` | Mã hóa âm thanh (`aac` tương thích rộng hoặc `copy` giữ nguyên gốc). |
| `--crf` / `--preset` | `16` / `slow` | Chất lượng và tốc độ nén `libx264`. |
| `--progress-every` | `30` | In tiến độ xử lý sau mỗi `N` khung hình. |

---

## 5. Lưu ý vận hành

* **Phần cứng chạy V20.1:** `OpenCV DIS Optical Flow` trong các bản cài đặt pip tiêu chuẩn chạy trên CPU; GPU CUDA chủ yếu tăng tốc cho bước suy luận của mô hình `LaMa` (nếu cài bản PyTorch hỗ trợ CUDA).
* **Video biến thiên tốc độ khung hình (VFR):** V20.1 xuất video tốc độ khung hình cố định (CFR) dựa trên FPS trung bình và sẽ hiển thị cảnh báo nếu phát hiện nguồn có dấu hiệu VFR; hãy kiểm tra lại đồng bộ âm thanh sau khi xuất.

---

## 6. Bản quyền & Giấy phép (Copyright & License)

Copyright © 2026 **Huy Bao Game** (`ghuy021112-cpu`). All rights reserved.

Dự án này được phát hành theo giấy phép **GNU Affero General Public License v3.0 (AGPL-3.0)**:
* Bạn được tự do sử dụng, nghiên cứu, sửa đổi và phân phối lại mã nguồn với điều kiện giữ nguyên thông báo bản quyền gốc.
* Mọi bản sửa đổi, phái sinh hoặc triển khai cung cấp dịch vụ qua mạng đều **bắt buộc phải công khai toàn bộ mã nguồn** dưới cùng giấy phép **AGPL-3.0**.
* Xem toàn văn giấy phép tại tệp `LICENSE` trong kho lưu trữ hoặc tại [gnu.org/licenses/agpl-3.0](https://www.gnu.org/licenses/agpl-3.0).
