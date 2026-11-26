# Huy Bao Game V20.1 — Quality Edition

[![License: AGPL v3](https://img.shields.io/badge/License-AGPLv3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

Công cụ phục hồi và làm sạch vùng phủ (overlay/watermark) trên video theo hướng **tái tạo theo thời gian (temporal restoration)** kết hợp **DIS Optical Flow**, **mặt nạ tĩnh/động HSV** và **AI Inpainting (LaMa)** dự phòng.

> **Lưu ý sử dụng & giới hạn kỹ thuật:** Chỉ sử dụng công cụ này cho các video do bạn sở hữu hoặc có quyền chỉnh sửa hợp pháp. Các thuật toán nội suy (OpenCV / LaMa) chỉ tái tạo nội dung hợp lý về mặt thị giác chứ không thể khôi phục nguyên bản dữ liệu đã bị che khuất hoàn toàn ở mọi khung hình.

## Tính năng nổi bật

* **Tái tạo nền hai chiều theo thời gian (`--window`):** Sử dụng cửa sổ đối xứng gồm các khung hình quá khứ và tương lai xung quanh khung hình trung tâm để mượn điểm ảnh nền sạch.
* **Căn chỉnh chuyển động DIS Optical Flow (`--flow-quality`):** Căn chỉnh khung hình lân cận về tọa độ khung hình mục tiêu, tự động loại bỏ các điểm mẫu nằm trong vùng mask của khung hình hàng xóm hoặc sai lệch độ sáng lớn.
* **Tối ưu vùng tính toán (`--bbox-margin`):** Khoanh vùng hộp chữ nhật quanh mask kèm biên đệm an toàn để giảm đáng kể RAM và thời gian xử lý.
* **Linh hoạt chế độ Mask:**
  * Dùng mặt nạ ảnh PNG tĩnh (`--mask`: trắng = vùng cần khôi phục, đen = giữ nguyên).
  * Dùng mặt nạ lọc màu tự động theo không gian màu HSV (`--hsv-lower`, `--hsv-upper`, `--hsv-dilate`).
  * Kết hợp đồng thời cả hai loại mặt nạ.
* **Dự phòng thông minh hai tầng:** Các điểm ảnh chưa thể khôi phục từ dữ liệu thời gian sẽ được xử lý qua **LaMa AI** (`--lama`, tùy chọn) hoặc **OpenCV Inpainting** (`telea` / `ns`).
* **Quy trình xuất file an toàn:** Ghi ra tệp tạm, kiểm tra lại metadata và tổng số khung hình bằng `ffprobe` trước khi ghi đè nguyên tử (`os.replace`) lên tệp đích.

## Yêu cầu hệ thống & Cài đặt

### 1. Cài đặt cơ bản (Ubuntu 22.04 / 24.04)

```bash
sudo apt update
sudo apt install -y ffmpeg python3 python3-venv python3-pip

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Nội dung tệp `requirements.txt`:

```text
opencv-python>=4.8
numpy>=1.24
```

### 2. Cài đặt tùy chọn cho LaMa AI (`--lama`)

Cài đặt **PyTorch** phù hợp với phiên bản CUDA trên máy chủ từ [pytorch.org](https://pytorch.org/get-started/locally/), sau đó cài đặt gói phụ thuộc AI:

```bash
pip install -r requirements-ai.txt
```

Nội dung tệp `requirements-ai.txt`:

```text
simple-lama-inpainting
Pillow>=10
```

Kiểm tra nhanh GPU CUDA:

```bash
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```

> **Ghi chú phần cứng:** DIS Optical Flow trong bản `opencv-python` tiêu chuẩn chạy trên CPU. GPU CUDA sẽ hỗ trợ tăng tốc cho mô hình **LaMa** khi bật cờ `--lama`.

## Hướng dẫn sử dụng

### Chuẩn bị ảnh Mask (nếu dùng `--mask`)

Tạo một ảnh `.png` thang độ xám (grayscale) có **cùng kích thước chiều rộng và chiều cao** với video đầu vào:

* **Màu trắng (`255`):** Vùng cần loại bỏ và tái tạo nền.
* **Màu đen (`0`):** Vùng giữ nguyên gốc.

### 1. Chạy với ảnh Mask vẽ tay + LaMa AI

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

### 2. Kết hợp ảnh Mask tĩnh và lọc màu HSV tự động

*(Các thông số HSV dưới đây chỉ mang tính ví dụ, cần điều chỉnh theo màu sắc thực tế của overlay)*:

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

### 3. Chỉ dùng lọc màu HSV (không cần file PNG)

```bash
python huy_bao_v20_1.py \
  --input input.mp4 \
  --output restored.mp4 \
  --hsv-lower 20 100 150 \
  --hsv-upper 40 255 255
```

## Bảng tham số dòng lệnh

| Tham số | Mặc định | Mô tả |
| :--- | :--- | :--- |
| `--input` | *(Bắt buộc)* | Đường dẫn video đầu vào. |
| `--output` | *(Bắt buộc)* | Đường dẫn video MP4 đầu ra. |
| `--mask` | `None` | Ảnh PNG đen/trắng chỉ định vùng cần khôi phục. |
| `--window` | `4` | Số khung hình lân cận mỗi bên (`1..8`). Giá trị lớn tốn nhiều RAM và thời gian hơn. |
| `--flow-quality` | `ultra` | Chất lượng DIS Optical Flow: `fast`, `medium`, `ultra`. |
| `--inpaint` | `telea` | Thuật toán nội suy OpenCV dự phòng: `telea` hoặc `ns`. |
| `--lama` | `False` | Bật mô hình AI LaMa cho các điểm ảnh chưa thể tái tạo theo thời gian. |
| `--hsv-lower` | `None` | Ngưỡng dưới `H S V` (`0..255`) để tạo mask tự động theo màu. |
| `--hsv-upper` | `None` | Ngưỡng trên `H S V` (`0..255`) để tạo mask tự động theo màu. |
| `--hsv-dilate` | `2` | Độ giãn nở (pixel) làm dày vùng mask HSV. |
| `--bbox-margin` | `48` | Khoảng đệm mở rộng (pixel) quanh vùng bao của mask. |
| `--preset` | `slow` | Preset mã hóa `libx264` (`ultrafast` đến `veryslow`). |
| `--crf` | `16` | Chất lượng nén H.264 (`0..51`, số càng nhỏ chất lượng càng cao). |
| `--audio` | `aac` | Xử lý âm thanh: `aac` (mã hóa lại tương thích cao) hoặc `copy` (giữ nguyên luồng). |
| `--audio-bitrate` | `192k` | Bitrate âm thanh khi dùng `--audio aac`. |
| `--progress-every` | `30` | In tiến độ xử lý sau mỗi N khung hình. |

## Những hạn chế cần lưu ý

1. **Video biến thiên tốc độ khung hình (VFR):** Phiên bản hiện tại xuất đầu ra theo tốc độ khung hình cố định (CFR) dựa trên FPS trung bình. Nếu video gốc là VFR nặng, hãy kiểm tra lại độ khớp tiếng sau khi xuất.
2. **Cảnh chuyển đột ngột hoặc chuyển động quá nhanh:** Optical flow có thể giảm độ chính xác khi chuyển cảnh gắt hoặc vật thể che khuất liên tục; khi đó hệ thống sẽ tự chuyển sang bước nội suy LaMa / OpenCV.
3. **Frame lỗi ở đầu vào:** Để đảm bảo toàn vẹn dữ liệu, các khung hình bị thiếu byte trong luồng giải mã sẽ được báo lỗi dừng ngay thay vì tự động bù pixel đen.

## Bản quyền & Giấy phép (Copyright & License)

Copyright © 2026 **Huy Bao Game** (`ghuy021112-cpu`). All rights reserved.

Dự án này được phát hành theo giấy phép **GNU Affero General Public License v3.0 (AGPL-3.0)**.

* Bạn được tự do sử dụng, nghiên cứu, sửa đổi và phân phối lại mã nguồn với điều kiện giữ nguyên thông báo bản quyền của tác giả.
* Mọi bản sửa đổi, phái sinh hoặc triển khai cung cấp dịch vụ qua mạng đều **bắt buộc phải công khai mã nguồn** dưới cùng giấy phép **AGPL-3.0**.
* Xem toàn văn giấy phép tại tệp `LICENSE` trong kho lưu trữ hoặc tại [gnu.org/licenses/agpl-3.0](https://www.gnu.org/licenses/agpl-3.0).
