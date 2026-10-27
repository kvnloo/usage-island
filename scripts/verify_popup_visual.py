#!/usr/bin/env python3
"""Compare a rendered popup panel against the panel-only reference spec.

This intentionally ignores the macOS menu bar and wallpaper/background in the
reference screenshot. The spec's panel crop is the only coordinate system.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

import numpy as np


def read_png(path: Path) -> np.ndarray:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG")

    pos = 8
    width = height = bit_depth = color_type = None
    idat: list[bytes] = []
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        pos += 4
        chunk_type = data[pos:pos + 4]
        pos += 4
        chunk = data[pos:pos + length]
        pos += length + 4  # skip CRC
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _comp, _filter, interlace = struct.unpack(">IIBBBBB", chunk)
            if bit_depth != 8 or interlace != 0:
                raise ValueError(f"{path} must be non-interlaced 8-bit PNG")
        elif chunk_type == b"IDAT":
            idat.append(chunk)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None or color_type is None:
        raise ValueError(f"{path} is missing PNG metadata")
    channels_by_type = {0: 1, 2: 3, 4: 2, 6: 4}
    if color_type not in channels_by_type:
        raise ValueError(f"{path} uses unsupported PNG color type {color_type}")
    channels = channels_by_type[color_type]

    raw = zlib.decompress(b"".join(idat))
    stride = width * channels
    rows = []
    i = 0
    prev = np.zeros(stride, dtype=np.uint8)
    for _y in range(height):
        filter_type = raw[i]
        i += 1
        cur = np.frombuffer(raw[i:i + stride], dtype=np.uint8).copy()
        i += stride
        row = cur.astype(np.int16)
        if filter_type == 1:
            for x in range(stride):
                left = row[x - channels] if x >= channels else 0
                row[x] = (row[x] + left) & 255
        elif filter_type == 2:
            row = (row + prev.astype(np.int16)) & 255
        elif filter_type == 3:
            for x in range(stride):
                left = row[x - channels] if x >= channels else 0
                up = int(prev[x])
                row[x] = (row[x] + ((left + up) // 2)) & 255
        elif filter_type == 4:
            for x in range(stride):
                a = row[x - channels] if x >= channels else 0
                b = int(prev[x])
                c = int(prev[x - channels]) if x >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                row[x] = (row[x] + pr) & 255
        elif filter_type != 0:
            raise ValueError(f"{path} uses unsupported PNG filter {filter_type}")
        out = row.astype(np.uint8)
        rows.append(out.reshape(width, channels))
        prev = out

    image = np.stack(rows)
    if channels == 1:
        image = np.repeat(image, 3, axis=2)
    elif channels == 2:
        image = np.repeat(image[:, :, :1], 3, axis=2)
    else:
        image = image[:, :, :3]
    return image.astype(np.float32)


def crop(image: np.ndarray, rect: dict | list[int]) -> np.ndarray:
    if isinstance(rect, dict):
        x, y, w, h = rect["x"], rect["y"], rect["width"], rect["height"]
    else:
        x, y, w, h = rect
    return image[int(y):int(y + h), int(x):int(x + w)]


def resize_nearest(image: np.ndarray, width: int, height: int) -> np.ndarray:
    if image.shape[1] == width and image.shape[0] == height:
        return image
    ys = np.minimum((np.arange(height) * image.shape[0] / height).astype(int), image.shape[0] - 1)
    xs = np.minimum((np.arange(width) * image.shape[1] / width).astype(int), image.shape[1] - 1)
    return image[ys[:, None], xs[None, :]]


def scaled_bbox(bbox: list[int], sx: float, sy: float) -> list[int]:
    x, y, w, h = bbox
    x2 = int(round((x + w) * sx))
    y2 = int(round((y + h) * sy))
    x1 = int(round(x * sx))
    y1 = int(round(y * sy))
    return [x1, y1, max(1, x2 - x1), max(1, y2 - y1)]


def panel_from_candidate(image: np.ndarray, crop_arg: str | None) -> np.ndarray:
    if not crop_arg:
        return image
    parts = [int(p) for p in crop_arg.replace(",", " ").split()]
    if len(parts) != 4:
        raise ValueError("--candidate-crop expects 'x,y,width,height'")
    return crop(image, parts)


def component_score(ref: np.ndarray, candidate: np.ndarray) -> tuple[float, float, float]:
    if ref.size == 0 or candidate.size == 0:
        return 999.0, 999.0, 999.0
    ref_scaled = resize_nearest(ref, candidate.shape[1], candidate.shape[0])
    diff = np.abs(ref_scaled - candidate)
    mae = float(diff.mean())
    p95 = float(np.percentile(diff, 95))
    mean_delta = float(np.abs(ref_scaled.mean(axis=(0, 1)) - candidate.mean(axis=(0, 1))).mean())
    return mae, p95, mean_delta


def best_component_score(
    reference_panel: np.ndarray,
    candidate_panel: np.ndarray,
    bbox: list[int],
    sx: float,
    sy: float,
    search_y: int = 0,
) -> tuple[float, float, float, int]:
    ref_part = crop(reference_panel, bbox)
    base = scaled_bbox(bbox, sx, sy)
    best: tuple[float, float, float, int] | None = None
    for dy in range(-search_y, search_y + 1):
        shifted = [base[0], base[1] + dy, base[2], base[3]]
        if shifted[1] < 0 or shifted[1] + shifted[3] > candidate_panel.shape[0]:
            continue
        cand_part = crop(candidate_panel, shifted)
        mae, p95, mean_delta = component_score(ref_part, cand_part)
        score = (mae, p95, mean_delta, dy)
        if best is None or score[:3] < best[:3]:
            best = score
    if best is None:
        return 999.0, 999.0, 999.0, 0
    return best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", default="docs/popup-panel-spec.json")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--candidate-crop", help="x,y,width,height crop for full screenshots")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    spec = json.loads(spec_path.read_text())
    root = spec_path.parent.parent

    reference_image = read_png(root / spec["reference"]["image"])
    reference_panel = crop(reference_image, spec["reference"]["panel_crop"])
    candidate_panel = panel_from_candidate(read_png(Path(args.candidate)), args.candidate_crop)

    sx = candidate_panel.shape[1] / reference_panel.shape[1]
    sy = candidate_panel.shape[0] / reference_panel.shape[0]
    print(f"reference_panel={reference_panel.shape[1]}x{reference_panel.shape[0]}")
    print(f"candidate_panel={candidate_panel.shape[1]}x{candidate_panel.shape[0]} scale=({sx:.4f},{sy:.4f})")
    print("component,kind,mae,p95,mean_delta,shift_y,tolerance,status")

    failures = 0
    for component in spec["components"]:
        search_y = int(component.get("search_y_px", 0))
        if component["kind"] == "divider" and "search_y_px" not in component:
            search_y = int(spec.get("verification", {}).get("divider_search_y_px", 6))
        mae, p95, mean_delta, shift_y = best_component_score(
            reference_panel,
            candidate_panel,
            component["bbox"],
            sx,
            sy,
            search_y)
        tolerance = float(component.get("tolerance_mae", 30))
        ok = mae <= tolerance
        failures += 0 if ok else 1
        status = "ok" if ok else "fail"
        print(
            f"{component['id']},{component['kind']},"
            f"{mae:.2f},{p95:.2f},{mean_delta:.2f},{shift_y},{tolerance:.2f},{status}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
