#!/usr/bin/env python3
"""Huy Bao Game V17 - process a complete video with FFmpeg/OpenCV.

- Encodes processed frames directly with libx264 (no intermediate mp4v encode).
- Trims preview audio/video to the same duration and uses -shortest.
- Validates top-bar height against the actual input frame height.
- Builds a temporally stabilised watermark mask and inpaints only the ROI crop.

Requires: opencv-python, numpy, and FFmpeg on PATH.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np


def parse_args():
    p = argparse.ArgumentParser(description="Remove selected overlays from a video")
    p.add_argument("input", help="Input video")
    p.add_argument("output", help="Output MP4")
    p.add_argument("--top-height", type=int, default=110,
                   help="Blacken this many pixels at the top (default: 110)")
    p.add_argument("--no-clear-top", action="store_true")
    p.add_argument("--no-inpaint", action="store_true",
                   help="Skip ROI watermark detection and inpainting (useful for testing)")
    p.add_argument("--roi", nargs=4, type=int, metavar=("X1", "Y1", "X2", "Y2"),
                   default=(155, 565, 570, 650),
                   help="Watermark search ROI in input pixels")
    p.add_argument("--threshold", type=int, default=142)
    p.add_argument("--max-saturation", type=int, default=105)
    p.add_argument("--dilate", type=int, default=2)
    p.add_argument("--radius", type=float, default=4.0,
                   help="Inpaint radius (default: 4.0)")
    p.add_argument("--inpaint-method", choices=("telea", "ns"), default="telea",
                   help="Inpainting algorithm: telea (faster) or ns (Navier-Stokes)")
    p.add_argument("--mask-memory", type=float, default=0.78,
                   help="Base EMA memory; lower values adapt faster (0..0.98)")
    p.add_argument("--scene-cut-delta", type=float, default=24.0,
                   help="Mean ROI frame difference that triggers faster mask adaptation")
    p.add_argument("--mask-consensus", type=float, default=0.38,
                   help="EMA threshold for stable watermark pixels (0..1)")
    p.add_argument("--crf", type=int, default=18)
    p.add_argument("--preset", default="medium")
    p.add_argument("--preview-seconds", type=float, default=0,
                   help="Process first N seconds; 0 means full video")
    p.add_argument("--keep-temp", action="store_true")
    return p.parse_args()


def probe_video(path):
    """Read stream dimensions and nominal average frame rate using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate,r_frame_rate",
        "-of", "json", str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        streams = json.loads(result.stdout).get("streams", [])
        if not streams:
            raise RuntimeError("Không tìm thấy video stream trong file.")
        stream = streams[0]
        width, height = int(stream["width"]), int(stream["height"])
        def parse_rate(value):
            if not value or value in ("0/0", "N/A"):
                return 0.0
            num, den = value.split("/", 1)
            return float(num) / float(den) if float(den) else 0.0
        fps = parse_rate(stream.get("avg_frame_rate"))
        if fps <= 0:
            fps = parse_rate(stream.get("r_frame_rate"))
        if width <= 0 or height <= 0 or fps <= 0:
            raise RuntimeError("ffprobe trả về metadata video không hợp lệ.")
        return width, height, fps
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError,
            KeyError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Không đọc được metadata bằng ffprobe: {exc}") from exc


def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        raise SystemExit("Cần cài FFmpeg và thêm ffmpeg vào PATH.")


def candidate_mask(crop, threshold, max_sat, dilate):
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    m = ((hsv[:, :, 2] >= threshold) &
         (hsv[:, :, 1] <= max_sat)).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    if dilate:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                      (2 * dilate + 1, 2 * dilate + 1))
        m = cv2.dilate(m, k, iterations=1)
    return m


def encode_and_mux(src, dst, silent_path, width, height, fps, preview, crf, preset, frames_iter):
    enc_cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}",
        "-r", f"{fps:.8f}", "-i", "pipe:0", "-an",
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", silent_path,
    ]
    count = 0
    with tempfile.TemporaryFile() as enc_err_file:
        enc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE, stderr=enc_err_file)
        try:
            for frame in frames_iter:
                enc.stdin.write(frame.tobytes())
                count += 1
            enc.stdin.close()
            rc = enc.wait()
            enc_err_file.seek(0)
            err = enc_err_file.read().decode("utf-8", "replace")
            if rc:
                raise RuntimeError("FFmpeg encode thất bại: " + err[-2500:])
            if count == 0:
                raise RuntimeError("Không đọc được khung hình nào từ video.")

            mux_cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", silent_path,
                       "-i", str(src), "-map", "0:v:0", "-map", "1:a?",
                       "-c:v", "copy", "-c:a", "aac", "-b:a", "192k"]
            if preview > 0:
                mux_cmd += ["-t", f"{preview:.3f}"]
            mux_cmd += ["-shortest", "-movflags", "+faststart", str(dst)]
            subprocess.run(mux_cmd, check=True)
            return count, silent_path
        except Exception:
            if enc.poll() is None:
                enc.kill()
                enc.wait()
            raise


def main():
    a = parse_args()
    src, dst = Path(a.input), Path(a.output)
    if not src.is_file():
        raise SystemExit(f"Không tìm thấy video: {src}")
    if src.resolve() == dst.resolve():
        raise SystemExit("File đầu ra phải khác file đầu vào.")
    if not (0 <= a.threshold <= 255 and 0 <= a.max_saturation <= 255 and
            0 <= a.dilate <= 12 and 0.1 <= a.radius <= 20 and
            0 <= a.crf <= 51 and a.preview_seconds >= 0 and
            0 <= a.mask_memory < 0.99 and 0 <= a.mask_consensus <= 1 and
            0 <= a.scene_cut_delta <= 255):
        raise SystemExit("Thông số nằm ngoài phạm vi hợp lệ.")
    check_ffmpeg()

    width, height, fps = probe_video(src)
    if not 0 <= a.top_height <= height:
        raise SystemExit(f"--top-height phải nằm trong 0..{height} cho video này.")

    x1, y1, x2, y2 = a.roi
    if x1 < 0 or y1 < 0 or x2 > width or y2 > height or x2 <= x1 or y2 <= y1:
        raise SystemExit(f"ROI {a.roi} không hợp lệ với video {width}x{height}.")

    dst.parent.mkdir(parents=True, exist_ok=True)
    dec_cmd = ["ffmpeg", "-loglevel", "error", "-i", str(src)]
    if a.preview_seconds > 0:
        dec_cmd += ["-t", f"{a.preview_seconds:.3f}"]
    dec_cmd += ["-map", "0:v:0", "-vsync", "0", "-f", "rawvideo",
                "-pix_fmt", "bgr24", "pipe:1"]
    # File-backed stderr cannot fill a pipe and stall raw-frame decoding.
    dec_err_file = tempfile.TemporaryFile()
    dec = subprocess.Popen(dec_cmd, stdout=subprocess.PIPE, stderr=dec_err_file)

    roi_shape = (y2 - y1, x2 - x1)
    ema = np.zeros(roi_shape, dtype=np.float32)
    previous_gray = None

    def read_exact(pipe, size):
        """Read exactly one raw frame, unless EOF is reached."""
        chunks = bytearray()
        while len(chunks) < size:
            part = pipe.read(size - len(chunks))
            if not part:
                break
            chunks.extend(part)
        return bytes(chunks)

    def processed_frames():
        nonlocal previous_gray, ema
        frame_bytes = width * height * 3
        idx = 0
        while True:
            raw = read_exact(dec.stdout, frame_bytes)
            if not raw:
                break
            if len(raw) != frame_bytes:
                missing = frame_bytes - len(raw)
                # A short read at EOF can leave only the final raw frame incomplete.
                # Pad its missing tail with black pixels so one trailing fragment
                # does not abort the entire export; decoder errors are checked later.
                print(
                    f"CẢNH BÁO: Frame cuối bị thiếu {missing} bytes "
                    f"(nhận {len(raw)}/{frame_bytes}); đã bù byte 0.",
                    file=sys.stderr,
                )
                raw += b"\x00" * missing
            frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3)).copy()
            if not a.no_clear_top and a.top_height:
                frame[:a.top_height, :] = 0

            if not a.no_inpaint:
                crop = frame[y1:y2, x1:x2]
                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                memory = a.mask_memory
                if previous_gray is not None:
                    scene_delta = float(cv2.absdiff(gray, previous_gray).mean())
                    if scene_delta >= a.scene_cut_delta:
                        # React faster after abrupt scene/brightness changes.
                        memory = min(memory, 0.70)
                        ema *= 0.25
                previous_gray = gray
                current = candidate_mask(crop, a.threshold, a.max_saturation, a.dilate)
                ema[:] = memory * ema + (1.0 - memory) * (current > 0)
                stable = (ema >= a.mask_consensus).astype(np.uint8) * 255
                if np.any(stable):
                    method = cv2.INPAINT_TELEA if a.inpaint_method == "telea" else cv2.INPAINT_NS
                    frame[y1:y2, x1:x2] = cv2.inpaint(
                        crop, stable, a.radius, method)
            idx += 1
            if idx % 300 == 0:
                print(f"Đã xử lý {idx} khung hình ({idx / fps:.1f}s)")
            yield frame

    fd, silent_path = tempfile.mkstemp(suffix="_silent.mp4", dir=str(dst.parent))
    os.close(fd)
    try:
        count, _ = encode_and_mux(
            src, dst, silent_path, width, height, fps, a.preview_seconds,
            a.crf, a.preset, processed_frames())
        # Drain any remaining stdout/stderr and wait without risking a full
        # stderr pipe blocking the decoder. processed_frames() has consumed
        # stdout through EOF on the successful path.
        dec.wait()
        dec_err_file.seek(0)
        dec_err = dec_err_file.read().decode("utf-8", "replace")
        if dec.returncode:
            raise RuntimeError("FFmpeg decode thất bại: " + dec_err[-2500:])
    finally:
        if dec.poll() is None:
            dec.kill()
            dec.wait()
        if dec.stdout:
            dec.stdout.close()
        if dec.stderr:
            dec.stderr.close()
        dec_err_file.close()
        if silent_path and not a.keep_temp and os.path.exists(silent_path):
            os.remove(silent_path)

    print(f"Hoàn tất: {dst}")
    print(f"{count} khung hình | {width}x{height} | {fps:.3f} FPS")
    print("V18: metadata lấy bằng ffprobe; stderr dùng file tạm để tránh nghẽn pipe; hỗ trợ --inpaint-method telea|ns và --no-inpaint. Nên kiểm tra preview trước khi xử lý toàn bộ.")
    print("Lưu ý: nền đã bị che không thể khôi phục hoàn toàn như dữ liệu gốc.")


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, BrokenPipeError, RuntimeError) as exc:
        print(f"Lỗi xử lý video: {exc}", file=sys.stderr)
        raise SystemExit(1)
