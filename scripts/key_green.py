"""Chroma-key a green-screen headline into a clean transparent RGBA PNG.

Use this for headline artwork generated on a flat solid green background.

Key rules that prevent the two defects seen in production:
  * No gray speckles on the cream faces -> every bright, non-green pixel is
    forced FULLY opaque; only genuinely green pixels may be semi-transparent.
  * No checkerboard / trapped wedges -> hard separation with a narrow AA ramp
    and a solid green background from the generator.
  * No "AI generated" watermark / debris -> small connected components are
    dropped; only large letter strokes survive.
"""
import argparse
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def key_green(src: Path, out: Path, diag: Path | None,
              green_lo: int, green_hi: int, bright: int, min_component: int):
    a = np.array(Image.open(src).convert("RGB")).astype(np.float32)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    greenness = g - np.maximum(r, b)   # green bg -> large positive; cream/amber -> <=0

    # Hard separation: crisp AA ramp only in the narrow green band.
    alpha = np.where(greenness <= green_lo, 1.0,
                     np.where(greenness >= green_hi, 0.0,
                              (green_hi - greenness) / (green_hi - green_lo)))

    # Force bright, non-green pixels (the cream faces) FULLY opaque.
    cream = (a.mean(2) > bright) & (greenness < green_lo)
    alpha[cream] = 1.0

    # Blur softens only the silhouette; then re-lock faces so no partial alpha.
    soft = Image.fromarray((alpha * 255).astype("uint8")).filter(ImageFilter.GaussianBlur(0.6))
    alpha = np.array(soft).astype(np.float32) / 255
    alpha[(a.mean(2) > bright) & (greenness < green_lo - 10)] = 1.0

    # Despill: clamp green on edge pixels only; never darken the faces.
    a2 = a.copy()
    edge = (greenness > 10) & (alpha > 0)
    a2[:, :, 1][edge] = np.maximum(r, b)[edge]

    # Remove isolated debris (watermark / stray specks); keep large strokes.
    fg = alpha >= 0.5
    h, w = fg.shape
    seen = np.zeros_like(fg, bool)
    keep = np.zeros_like(fg, bool)
    for y in range(h):
        for x in range(w):
            if fg[y, x] and not seen[y, x]:
                q = deque([(y, x)]); seen[y, x] = True; comp = []
                while q:
                    cy, cx = q.popleft(); comp.append((cy, cx))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w and fg[ny, nx] and not seen[ny, nx]:
                                seen[ny, nx] = True; q.append((ny, nx))
                if len(comp) >= min_component:
                    for cy, cx in comp:
                        keep[cy, cx] = True
    alpha = alpha * keep

    out_arr = np.zeros((h, w, 4), dtype=np.uint8)
    out_arr[:, :, :3] = np.clip(a2, 0, 255).astype(np.uint8)
    out_arr[:, :, 3] = (alpha * 255).astype(np.uint8)
    img = Image.fromarray(out_arr, "RGBA")
    bb = img.getchannel("A").point(lambda v: 255 if v >= 24 else 0).getbbox()
    img = img.crop(bb)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)

    if diag is not None:
        bg = Image.new("RGBA", img.size, (255, 0, 255, 255))
        bg.alpha_composite(img)
        diag.parent.mkdir(parents=True, exist_ok=True)
        bg.convert("RGB").save(diag)

    import json
    al = np.array(img.getchannel("A"))
    print(json.dumps({"output": str(out), "size": img.size,
                      "opaque_frac": round(float((al == 255).mean()), 3),
                      "extrema": img.getchannel("A").getextrema()}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, type=Path, help="green-screen headline image")
    p.add_argument("--output", required=True, type=Path, help="transparent RGBA PNG")
    p.add_argument("--diag", type=Path, default=None, help="optional magenta composite for inspection")
    p.add_argument("--green-lo", type=int, default=30)
    p.add_argument("--green-hi", type=int, default=100)
    p.add_argument("--bright", type=int, default=170)
    p.add_argument("--min-component", type=int, default=600)
    args = p.parse_args()
    key_green(args.input, args.output, args.diag,
              args.green_lo, args.green_hi, args.bright, args.min_component)


if __name__ == "__main__":
    main()
