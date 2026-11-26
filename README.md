Huy Bao Game V20.1 — Quality Edition
For footage you own or are authorized to edit.

Main improvements over V20
Correct symmetric temporal buffering with repeated edge frames; each real frame is emitted once.
Temporal median and intermediate arrays are restricted to the mask bounding box plus margin.
Source masks are warped with optical flow, so pixels covered in the neighboring frame are rejected.
Optional per-frame HSV mask can be combined with a hand-painted mask.
Optional LaMa runs only on the unresolved mask crop.
AAC audio output is the default for MP4 compatibility; --audio copy is available.
Output is written to a temporary file, probed, and frame-count checked before atomic replacement.
Truncated raw frames are treated as errors, never padded with synthetic black pixels.
Requirements (Ubuntu 22.04/24.04)
sudo apt update
sudo apt install -y ffmpeg python3 python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
For optional LaMa:

Install PyTorch matching the server's CUDA runtime from https://pytorch.org/get-started/locally/
pip install -r requirements-ai.txt
Check python -c "import torch; print(torch.cuda.is_available())"
OpenCV DIS optical flow is CPU-based in common pip builds. A CUDA GPU does not automatically accelerate DIS. The LaMa package may use CUDA when its PyTorch installation and model implementation support it; confirm using server monitoring.

Mask
Create a PNG exactly matching the video's width and height:

white = restore
black = preserve
Run with a hand-painted mask
python huy_bao_v20_1.py \
  --input input.mp4 --output restored.mp4 --mask mask.png \
  --window 4 --flow-quality ultra --lama --preset slow --crf 16
Run with HSV detection added to a mask
HSV bounds below are examples only; tune them to the color of the overlay:

python huy_bao_v20_1.py \
  --input input.mp4 --output restored.mp4 --mask mask.png \
  --hsv-lower 20 100 150 --hsv-upper 40 255 255 \
  --hsv-dilate 2 --window 4 --flow-quality ultra --lama
HSV-only mode (no PNG mask):

python huy_bao_v20_1.py \
  --input input.mp4 --output restored.mp4 \
  --hsv-lower 20 100 150 --hsv-upper 40 255 255
Quality controls
--window 4: up to four neighboring frames on each side.
--flow-quality ultra: slower, more detailed DIS preset.
--bbox-margin 48: context around the mask bounding box.
--crf 16 --preset slow: high-quality H.264 encoding.
--audio aac: re-encode audio to broadly compatible AAC. Use --audio copy when stream-copy compatibility is known to be good.
Limitations
V20.1 converts input to constant frame rate using the probed average FPS. A warning is printed when average and nominal rates differ significantly. For strict VFR timestamp preservation, a timestamp-aware pipeline is still needed.
Optical-flow alignment can fail on scene cuts, occlusions, or very fast motion.
LaMa synthesizes plausible content. It cannot guarantee the exact hidden background.
The current release checks video frame count and output probe, but users should still inspect audio synchronization and difficult motion scenes after processing.
No claim is made that this has been benchmarked on Anthropic's private compute.
