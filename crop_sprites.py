#!/usr/bin/env python3
"""
Crop sprite sheets into individual PNG files.
- Transparent-background sheets: alpha-channel mask
- Opaque textured sheets: local-variance mask (discards the giant background blob)
"""

from PIL import Image, ImageFilter
import numpy as np, os
from collections import deque

SHEETS = [
    # (source,  out_dir,  method,    merge_gap, min_area, max_area)
    ("map_assets/map assets.webp",        "map_assets/sprites/outdoor",  "variance", 0,  1200, 120000),
    ("map_assets/map assets more.webp",   "map_assets/sprites/indoor",   "alpha",    0,  900,  60000),
    ("map_assets/map assets more 2.webp", "map_assets/sprites/dungeon",  "variance", 0,  900,  120000),
]

PADDING = 10

# ── Mask helpers ──────────────────────────────────────────────────────────────

def local_std_mask(gray, radius=8, threshold=15):
    """High local-variance pixels = sprite content."""
    g = Image.fromarray(gray.astype(np.uint8))
    blurred = np.array(g.filter(ImageFilter.BoxBlur(radius))).astype(float)
    sq_img  = np.minimum(gray**2 / 255, 255).astype(np.uint8)
    sq_blur = np.array(Image.fromarray(sq_img).filter(ImageFilter.BoxBlur(radius))).astype(float) * 255
    std = np.sqrt(np.maximum(sq_blur - blurred**2, 0))
    return std > threshold

def make_mask(arr, method):
    if method == "alpha":
        return arr[:, :, 3] > 30
    gray = np.array(Image.fromarray(arr).convert("L")).astype(float)
    return local_std_mask(gray)

# ── BFS connected components ──────────────────────────────────────────────────

def find_blobs(mask):
    h, w = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    blobs = []
    for r0, c0 in zip(*np.where(mask)):
        if visited[r0, c0]: continue
        q = deque([(r0, c0)]); visited[r0, c0] = True
        min_r=max_r=r0; min_c=max_c=c0
        while q:
            r, c = q.popleft()
            if r<min_r: min_r=r
            if r>max_r: max_r=r
            if c<min_c: min_c=c
            if c>max_c: max_c=c
            for dr, dc in ((-1,0),(1,0),(0,-1),(0,1)):
                nr, nc = r+dr, c+dc
                if 0<=nr<h and 0<=nc<w and mask[nr,nc] and not visited[nr,nc]:
                    visited[nr,nc]=True; q.append((nr,nc))
        blobs.append((min_c, min_r, max_c, max_r))
    return blobs

def merge_bboxes(boxes, gap):
    if gap == 0: return boxes
    changed = True
    while changed:
        changed = False
        result = []
        used = [False]*len(boxes)
        for i,(ax1,ay1,ax2,ay2) in enumerate(boxes):
            if used[i]: continue
            for j,(bx1,by1,bx2,by2) in enumerate(boxes):
                if i==j or used[j]: continue
                if max(ax1,bx1)-min(ax2,bx2) <= gap and max(ay1,by1)-min(ay2,by2) <= gap:
                    ax1=min(ax1,bx1); ay1=min(ay1,by1)
                    ax2=max(ax2,bx2); ay2=max(ay2,by2)
                    used[j]=True; changed=True
            result.append((ax1,ay1,ax2,ay2)); used[i]=True
        boxes = result
    return boxes

# ── Main ──────────────────────────────────────────────────────────────────────

def crop_sheet(src, out_dir, method, merge_gap, min_area, max_area):
    print(f"\n  {src}")
    os.makedirs(out_dir, exist_ok=True)

    img = Image.open(src).convert("RGBA")
    arr = np.array(img)
    h, w = arr.shape[:2]

    mask   = make_mask(arr, method)
    blobs  = find_blobs(mask)
    merged = merge_bboxes(blobs, merge_gap)
    kept   = [(x1,y1,x2,y2) for x1,y1,x2,y2 in merged
              if min_area <= (x2-x1)*(y2-y1) <= max_area]
    kept.sort(key=lambda b: (b[1]//80, b[0]))   # top→bottom, left→right

    print(f"  method={method}  blobs={len(blobs)}  merged={len(merged)}  kept={len(kept)}")

    for i, (x1,y1,x2,y2) in enumerate(kept):
        crop = img.crop((max(0,x1-PADDING), max(0,y1-PADDING),
                         min(w,x2+PADDING), min(h,y2+PADDING)))
        crop.save(os.path.join(out_dir, f"sprite_{i+1:03d}.png"))

    print(f"  → saved {len(kept)} sprites to {out_dir}/")
    return len(kept)

if __name__ == "__main__":
    total = 0
    for args in SHEETS:
        if os.path.exists(args[0]):
            total += crop_sheet(*args)
        else:
            print(f"\n  SKIP (not found): {args[0]}")
    print(f"\nTotal: {total} sprites saved.")
