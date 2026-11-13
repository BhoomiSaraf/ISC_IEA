"""Acquires the exact standard test images used in the reference paper (Sharma et al., MTAP 2022).

Sources:
  1. USC-SIPI Image Database (http://sipi.usc.edu/database/database.php?volume=misc):
     - 5.1.12 (Couple 256x256, used in Fig 6 & Section 4.6 speed tests)
     - 4.2.03 (Mandrill / Baboon 512x512 RGB, used in Fig 7 & 8)
     - 4.2.07 (Peppers 512x512 RGB, used in Fig 9 & 10)
     - boat.512 (Boat 512x512 grayscale, Table 2/3/4)
     - 5.1.09, 5.1.10, 5.1.11, 5.1.13, 5.1.14 (Table 2/3/4)
     - 5.2.08 (Table 2/3/4)
  2. OpenCV / Academic Standard Mirror:
     - Lena 512x512 (used for Table 1 APC & standard benchmark)
"""

import io
import os
import urllib.request
import numpy as np
from PIL import Image

DEST_DIR = "experiments/paper_workflow_study/standard_dataset"
os.makedirs(DEST_DIR, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0"}

TARGETS = [
    ("5.1.12", "https://sipi.usc.edu/database/download.php?vol=misc&img=5.1.12", "gray"),
    ("5.1.09", "https://sipi.usc.edu/database/download.php?vol=misc&img=5.1.09", "gray"),
    ("5.1.10", "https://sipi.usc.edu/database/download.php?vol=misc&img=5.1.10", "gray"),
    ("5.1.11", "https://sipi.usc.edu/database/download.php?vol=misc&img=5.1.11", "gray"),
    ("5.1.13", "https://sipi.usc.edu/database/download.php?vol=misc&img=5.1.13", "gray"),
    ("5.1.14", "https://sipi.usc.edu/database/download.php?vol=misc&img=5.1.14", "gray"),
    ("5.2.08", "https://sipi.usc.edu/database/download.php?vol=misc&img=5.2.08", "gray"),
    ("boat.512", "https://sipi.usc.edu/database/download.php?vol=misc&img=boat.512", "gray"),
    ("baboon_512_rgb", "https://sipi.usc.edu/database/download.php?vol=misc&img=4.2.03", "rgb"),
    ("peppers_512_rgb", "https://sipi.usc.edu/database/download.php?vol=misc&img=4.2.07", "rgb"),
    ("lena_512_rgb", "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/lena.jpg", "rgb"),
]

print("=== Downloading Exact Standard Test Images from USC-SIPI and Mirrors ===")
for name, url, mode in TARGETS:
    out_npy = os.path.join(DEST_DIR, f"{name}.npy")
    out_png = os.path.join(DEST_DIR, f"{name}.png")
    if os.path.exists(out_npy):
        print(f"  [ALREADY PRESENT] {name}")
        continue
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        im = Image.open(io.BytesIO(data))
        if mode == "gray":
            im_conv = im.convert("L")
        else:
            im_conv = im.convert("RGB")
        arr = np.array(im_conv, dtype=np.uint8)
        np.save(out_npy, arr)
        im_conv.save(out_png)
        print(f"  [DOWNLOADED] {name:16s} shape={arr.shape} mode={mode}")
    except Exception as e:
        print(f"  [FAILED] {name}: {e}")

# Also generate grayscale Lena from Lena RGB
lena_rgb_npy = os.path.join(DEST_DIR, "lena_512_rgb.npy")
lena_gray_npy = os.path.join(DEST_DIR, "lena_512_gray.npy")
if os.path.exists(lena_rgb_npy) and not os.path.exists(lena_gray_npy):
    rgb = np.load(lena_rgb_npy)
    im_gray = Image.fromarray(rgb).convert("L")
    arr_gray = np.array(im_gray, dtype=np.uint8)
    np.save(lena_gray_npy, arr_gray)
    im_gray.save(os.path.join(DEST_DIR, "lena_512_gray.png"))
    print("  [GENERATED] lena_512_gray shape=(512, 512)")

