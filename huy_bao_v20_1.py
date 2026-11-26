#!/usr/bin/env python3
"""
Huy Bao Game V20.1 - Quality Edition
Temporal video restoration for footage you own or are authorized to edit.

White mask pixels are restored; black pixels are preserved.
The temporal stage aligns neighboring frames with DIS optical flow, validates
source-mask coverage and photometric consistency, then uses a median of valid
samples. Optional LaMa is a fallback for unresolved masked pixels.

Important: AI inpainting synthesizes plausible content; it cannot reveal
original pixels that are hidden in every available frame.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Deque, Optional

import cv2
import numpy as np


def require_binary(name: str) -> str:
    result = shutil.which(name)
    if not result:
        raise RuntimeError(f"'{name}' was not found. Install it and ensure it is in PATH.")
    return result


def probe(path: Path, count_frames: bool = False) -> dict:
    cmd = [require_binary("ffprobe"), "-v", "error"]
    if count_frames:
        cmd += ["-count_frames"]
    cmd += [
        "-select_streams", "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate,r_frame_rate,duration,nb_read_frames,nb_frames",
        "-of", "json", str(path)
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"ffprobe failed: {p.stderr.strip()}")
    data = json.loads(p.stdout)
    streams = data.get("streams", [])
    if not streams:
        raise RuntimeError("No video stream was found.")
    s = streams[0]
    w, h = int(s["width"]), int(s["height"])
    def rate(value):
        a, b = value.split("/")
        return float(a) / max(float(b), 1e-12)
    fps = rate(s.get("avg_frame_rate", "0/1"))
    nominal = rate(s.get("r_frame_rate", "0/1"))
    if w < 1 or h < 1 or fps <= 0:
        raise RuntimeError("Invalid video dimensions or frame rate.")
    count = s.get("nb_read_frames") or s.get("nb_frames")
    return {
        "width": w, "height": h, "fps": fps, "nominal_fps": nominal,
        "duration": float(s.get("duration") or 0),
        "frames": int(count) if count not in (None, "N/A") else None
    }


def read_exact(pipe, size: int) -> Optional[bytes]:
    buf = bytearray()
    while len(buf) < size:
        chunk = pipe.read(size - len(buf))
        if not chunk:
            break
        buf.extend(chunk)
    if not buf:
        return None
    if len(buf) != size:
        raise RuntimeError(
            f"Truncated raw frame: received {len(buf)} of {size} bytes. "
            "The input may be damaged or the decoder stopped unexpectedly."
        )
    return bytes(buf)


def load_static_mask(path: Optional[Path], width: int, height: int) -> np.ndarray:
    if path is None:
        return np.zeros((height, width), np.uint8)
    m = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if m is None:
        raise RuntimeError(f"Cannot read mask: {path}")
    if m.shape != (height, width):
        raise RuntimeError(
            f"Mask is {m.shape[1]}x{m.shape[0]}, video is {width}x{height}."
        )
    return np.where(m >= 128, 255, 0).astype(np.uint8)


def make_color_mask(frame: np.ndarray, lower, upper, dilate: int) -> np.ndarray:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(
        hsv, np.asarray(lower, dtype=np.uint8), np.asarray(upper, dtype=np.uint8)
    )
    if dilate:
        k = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (2*dilate + 1, 2*dilate + 1)
        )
        m = cv2.dilate(m, k, iterations=1)
    return m


def bbox_with_margin(mask: np.ndarray, margin: int):
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return None
    h, w = mask.shape
    x0 = max(0, int(xs.min()) - margin)
    x1 = min(w, int(xs.max()) + 1 + margin)
    y0 = max(0, int(ys.min()) - margin)
    y1 = min(h, int(ys.max()) + 1 + margin)
    return x0, y0, x1, y1


def flow_candidate(target: np.ndarray, neighbor: np.ndarray,
                   neighbor_mask: np.ndarray, dis):
    """Warp neighbor into target coordinates using target->neighbor flow."""
    tg = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)
    ng = cv2.cvtColor(neighbor, cv2.COLOR_BGR2GRAY)
    flow = dis.calc(tg, ng, None)

    h, w = tg.shape
    xx, yy = np.meshgrid(
        np.arange(w, dtype=np.float32),
        np.arange(h, dtype=np.float32)
    )
    mx = xx + flow[..., 0]
    my = yy + flow[..., 1]

    warped = cv2.remap(
        neighbor, mx, my, cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT, borderValue=0
    )
    sampled_mask = cv2.remap(
        neighbor_mask, mx, my, cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT, borderValue=255
    )
    warped_gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(tg, warped_gray)

    valid = (
        (mx >= 1) & (mx < w - 1) &
        (my >= 1) & (my < h - 1) &
        (sampled_mask == 0) &
        (diff <= 42)
    )
    return warped, valid


def create_lama(enabled: bool):
    if not enabled:
        return None
    try:
        import torch
        from simple_lama_inpainting import SimpleLama
        print("[INFO] Loading LaMa. PyTorch CUDA available:",
              bool(torch.cuda.is_available()))
        return SimpleLama()
    except Exception as exc:
        raise RuntimeError(
            "LaMa could not be initialized. Install the optional dependencies "
            "and a PyTorch build compatible with the server. Details: " + str(exc)
        )


def lama_restore_crop(image: np.ndarray, mask: np.ndarray, lama) -> np.ndarray:
    from PIL import Image
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    result = lama(Image.fromarray(rgb), Image.fromarray(mask))
    arr = np.asarray(result.convert("RGB") if hasattr(result, "convert") else result)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def restore_center(entries, center_pos: int, dis, inpaint_method: str,
                   lama, bbox_margin: int):
    target, target_mask = entries[center_pos][1], entries[center_pos][2]
    if not np.any(target_mask):
        return target

    box = bbox_with_margin(target_mask, bbox_margin)
    if box is None:
        return target
    x0, y0, x1, y1 = box

    target_crop = target[y0:y1, x0:x1]
    target_mask_crop = target_mask[y0:y1, x0:x1]
    candidates = []
    validities = []

    for j, (_, neighbor, neighbor_mask) in enumerate(entries):
        if j == center_pos:
            continue
        warped, valid = flow_candidate(
            target_crop,
            neighbor[y0:y1, x0:x1],
            neighbor_mask[y0:y1, x0:x1],
            dis
        )
        candidates.append(warped)
        validities.append(valid)

    output = target.copy()
    restored_crop = target_crop.copy()
    if candidates:
        # Restrict all temporary arrays to the mask bounding box.
        stack = np.stack(candidates, axis=0).astype(np.float32)
        valid_stack = np.stack(validities, axis=0)
        work = stack.copy()
        work[~valid_stack] = np.nan
        with np.errstate(invalid="ignore"):
            median = np.nanmedian(work, axis=0)
        count = np.sum(valid_stack, axis=0)
        masked = target_mask_crop > 0
        temporal_good = masked & (count > 0)
        restored_crop[temporal_good] = np.clip(
            median[temporal_good], 0, 255
        ).astype(np.uint8)
        unresolved = masked & ~temporal_good
    else:
        unresolved = target_mask_crop > 0

    if np.any(unresolved) and lama is not None:
        # Run AI only on the unresolved bounding crop, not the whole frame.
        local_box = bbox_with_margin(unresolved.astype(np.uint8) * 255, 16)
        if local_box is not None:
            ax0, ay0, ax1, ay1 = local_box
            crop_img = restored_crop[ay0:ay1, ax0:ax1]
            crop_mask = (unresolved[ay0:ay1, ax0:ax1].astype(np.uint8) * 255)
            try:
                ai_crop = lama_restore_crop(crop_img, crop_mask, lama)
                use = crop_mask > 0
                region = restored_crop[ay0:ay1, ax0:ax1]
                region[use] = ai_crop[use]
                unresolved[ay0:ay1, ax0:ax1][use] = False
            except Exception as exc:
                print(f"[WARN] LaMa failed; OpenCV fallback will be used: {exc}",
                      file=sys.stderr)

    if np.any(unresolved):
        fm = unresolved.astype(np.uint8) * 255
        flag = cv2.INPAINT_TELEA if inpaint_method == "telea" else cv2.INPAINT_NS
        fallback = cv2.inpaint(restored_crop, fm, 5, flag)
        restored_crop[unresolved] = fallback[unresolved]

    # Pixels outside the mask are copied from the source frame unchanged.
    output[y0:y1, x0:x1] = restored_crop
    return output


def process(args):
    inp = Path(args.input).expanduser().resolve()
    out = Path(args.output).expanduser().resolve()
    mask_path = Path(args.mask).expanduser().resolve() if args.mask else None
    if not inp.is_file():
        raise RuntimeError(f"Input file does not exist: {inp}")
    if inp == out:
        raise RuntimeError("Input and output must be different files.")
    if args.window < 1 or args.window > 8:
        raise RuntimeError("--window must be in range 1..8.")
    if not 0 <= args.crf <= 51:
        raise RuntimeError("--crf must be in range 0..51.")
    if args.progress_every < 1:
        raise RuntimeError("--progress-every must be >= 1.")
    if bool(args.hsv_lower) != bool(args.hsv_upper):
        raise RuntimeError("Specify both --hsv-lower and --hsv-upper, or neither.")
    if mask_path is None and args.hsv_lower is None:
        raise RuntimeError("Provide --mask or both HSV bounds.")
    out.parent.mkdir(parents=True, exist_ok=True)

    meta = probe(inp)
    w, h, fps = meta["width"], meta["height"], meta["fps"]
    static_mask = load_static_mask(mask_path, w, h)
    if args.hsv_lower is not None:
        if any(v < 0 or v > 255 for v in args.hsv_lower + args.hsv_upper):
            raise RuntimeError("HSV values must be between 0 and 255.")
    if abs(meta["fps"] - meta["nominal_fps"]) / max(meta["fps"], 1e-9) > 0.01:
        print("[WARN] Source may be variable-frame-rate. This release outputs CFR "
              "using average FPS; check audio sync after processing.", file=sys.stderr)

    ffmpeg = require_binary("ffmpeg")
    lama = create_lama(args.lama)
    dis_preset = {
        "fast": cv2.DISOPTICAL_FLOW_PRESET_FAST,
        "medium": cv2.DISOPTICAL_FLOW_PRESET_MEDIUM,
        "ultra": cv2.DISOPTICAL_FLOW_PRESET_ULTRA
    }[args.flow_quality]
    dis = cv2.DISOpticalFlow_create(dis_preset)
    dis.setFinestScale(0)
    dis.setGradientDescentIterations(25 if args.flow_quality == "ultra" else 16)

    frame_size = w * h * 3
    window: Deque[tuple] = collections.deque()
    decoder = encoder = None
    dec_err = tempfile.TemporaryFile()
    enc_err = tempfile.TemporaryFile()
    tmp_path = None
    success = False
    total_out = 0
    last_real = None
    start = time.time()

    try:
        dec_cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error",
            "-i", str(inp), "-map", "0:v:0", "-an", "-sn", "-dn",
            "-vf", f"fps={fps:.12f}", "-f", "rawvideo",
            "-pix_fmt", "bgr24", "pipe:1"
        ]
        decoder = subprocess.Popen(
            dec_cmd, stdout=subprocess.PIPE, stderr=dec_err, bufsize=frame_size * 2
        )

        fd, tmp_name = tempfile.mkstemp(
            prefix=out.stem + "_v20_1_", suffix=".mp4", dir=str(out.parent)
        )
        os.close(fd)
        tmp_path = Path(tmp_name)

        audio_codec = ["-c:a", "copy"] if args.audio == "copy" else [
            "-c:a", "aac", "-b:a", args.audio_bitrate
        ]
        enc_cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
            "-r", f"{fps:.12f}", "-i", "pipe:0",
            "-i", str(inp), "-map", "0:v:0", "-map", "1:a?",
            "-c:v", "libx264", "-preset", args.preset,
            "-crf", str(args.crf), "-pix_fmt", "yuv420p",
            *audio_codec, "-movflags", "+faststart", str(tmp_path)
        ]
        encoder = subprocess.Popen(
            enc_cmd, stdin=subprocess.PIPE, stderr=enc_err, bufsize=frame_size * 2
        )

        def make_entry(index, frame):
            dynamic = np.zeros((h, w), np.uint8)
            if args.hsv_lower is not None:
                dynamic = make_color_mask(
                    frame, args.hsv_lower, args.hsv_upper, args.hsv_dilate
                )
            combined = cv2.bitwise_or(static_mask, dynamic)
            return (index, frame, combined)

        def emit_center():
            nonlocal total_out
            entries = list(window)
            center_index = args.window
            result = restore_center(
                entries, center_index, dis, args.inpaint, lama, args.bbox_margin
            )
            encoder.stdin.write(result.tobytes())
            total_out += 1
            if total_out % args.progress_every == 0:
                elapsed = max(time.time() - start, 1e-6)
                speed = total_out / elapsed
                if meta["duration"]:
                    pct = min(100.0, total_out / (meta["duration"] * fps) * 100)
                    print(f"[PROGRESS] {total_out} frames | {pct:.1f}% | "
                          f"{speed:.2f} fps")
                else:
                    print(f"[PROGRESS] {total_out} frames | {speed:.2f} fps")

        frame_index = 0
        first_frame = None
        while True:
            raw = read_exact(decoder.stdout, frame_size)
            if raw is None:
                break
            frame = np.frombuffer(raw, np.uint8).reshape(h, w, 3).copy()
            if first_frame is None:
                first_frame = frame
                first_entry = make_entry(0, first_frame)
                for _ in range(args.window):
                    window.append(first_entry)
            entry = make_entry(frame_index, frame)
            window.append(entry)
            last_real = entry
            frame_index += 1

            if len(window) == 2 * args.window + 1:
                emit_center()
                window.popleft()

        if frame_index == 0:
            raise RuntimeError("Decoder returned zero video frames.")

        # Pad the tail with references to the last real frame. Frame IDs let
        # us emit only real centers, exactly once, in their original order.
        for _ in range(args.window):
            window.append(last_real)
            if len(window) == 2 * args.window + 1:
                center_id = window[args.window][0]
                if center_id >= total_out:
                    emit_center()
                window.popleft()

        # Short clips may not have filled the window before EOF. Drain any
        # remaining real centers, padding only at the right edge.
        while any(item[0] >= total_out for item in list(window)[args.window:args.window+1]):
            while len(window) < 2 * args.window + 1:
                window.append(last_real)
            center_id = window[args.window][0]
            if center_id >= total_out:
                emit_center()
            window.popleft()
            if not window:
                break

        encoder.stdin.close()
        decoder.stdout.close()
        dec_rc = decoder.wait()
        enc_rc = encoder.wait()
        if dec_rc != 0:
            raise RuntimeError(f"FFmpeg decoder exited with code {dec_rc}.")
        if enc_rc != 0:
            raise RuntimeError(f"FFmpeg encoder exited with code {enc_rc}.")
        if total_out != frame_index:
            raise RuntimeError(
                f"Frame-count validation failed: read {frame_index}, wrote {total_out}."
            )
        if not tmp_path.exists() or tmp_path.stat().st_size < 1024:
            raise RuntimeError("Output MP4 is missing or unexpectedly small.")

        result_meta = probe(tmp_path, count_frames=True)
        if result_meta["frames"] is not None and result_meta["frames"] != total_out:
            raise RuntimeError(
                f"Output contains {result_meta['frames']} frames; expected {total_out}."
            )
        os.replace(tmp_path, out)
        success = True
        print(f"[DONE] {total_out} frames processed in {(time.time()-start)/60:.1f} min.")
        print(f"[DONE] Saved: {out}")

    finally:
        for proc in (decoder, encoder):
            if proc is not None and proc.poll() is None:
                try:
                    if proc.stdin and not proc.stdin.closed:
                        proc.stdin.close()
                except Exception:
                    pass
                proc.kill()
                proc.wait()
        for f in (dec_err, enc_err):
            try:
                f.seek(0)
                msg = f.read().decode("utf-8", errors="replace").strip()
                if msg:
                    print("[FFMPEG]", msg[-5000:], file=sys.stderr)
            except Exception:
                pass
            f.close()
        if tmp_path and tmp_path.exists() and not success:
            try:
                tmp_path.unlink()
            except OSError:
                pass


def main():
    p = argparse.ArgumentParser(
        description="Huy Bao Game V20.1 - quality-first temporal video restoration"
    )
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--mask", help="Grayscale PNG; white=restore, black=preserve")
    p.add_argument("--window", type=int, default=4)
    p.add_argument("--flow-quality", choices=["fast", "medium", "ultra"], default="ultra")
    p.add_argument("--inpaint", choices=["telea", "ns"], default="telea")
    p.add_argument("--lama", action="store_true")
    p.add_argument("--hsv-lower", nargs=3, type=int, metavar=("H", "S", "V"))
    p.add_argument("--hsv-upper", nargs=3, type=int, metavar=("H", "S", "V"))
    p.add_argument("--hsv-dilate", type=int, default=2)
    p.add_argument("--bbox-margin", type=int, default=48)
    p.add_argument("--preset", default="slow",
                   choices=["ultrafast", "superfast", "veryfast", "faster",
                            "fast", "medium", "slow", "slower", "veryslow"])
    p.add_argument("--crf", type=int, default=16)
    p.add_argument("--audio", choices=["aac", "copy"], default="aac")
    p.add_argument("--audio-bitrate", default="192k")
    p.add_argument("--progress-every", type=int, default=30)
    args = p.parse_args()
    if args.hsv_dilate < 0 or args.bbox_margin < 0:
        p.error("--hsv-dilate and --bbox-margin must be non-negative.")
    try:
        process(args)
    except KeyboardInterrupt:
        print("[STOP] Interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
