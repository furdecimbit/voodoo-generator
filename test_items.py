import numpy as np
from PIL import Image
from pathlib import Path
from scipy.ndimage import binary_erosion

VOODOO = Path("/Users/alperozdil/Documents/voodoo")

def resize_rgba(img, size, erode_px=2):
    arr = np.array(img).astype(np.float32)
    a = arr[:,:,3:4] / 255.0
    arr[:,:,:3] *= a
    img_pre = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    img_pre = img_pre.resize((size, size), Image.LANCZOS)
    arr2 = np.array(img_pre).astype(np.float32)
    a2 = arr2[:,:,3:4] / 255.0
    arr2[:,:,:3] = np.where(a2 > 0, arr2[:,:,:3] / np.maximum(a2, 1e-6), 0)
    solid = (arr2[:,:,3] > 128)
    eroded = binary_erosion(solid, iterations=erode_px)
    arr2[:,:,3] = np.where(eroded, arr2[:,:,3], 0)
    arr2[:,:,:3] *= eroded[:,:,None]
    return Image.fromarray(np.clip(arr2, 0, 255).astype(np.uint8))

folders = ["knife", "offhand", "necklace", "eyes"]
bg = Image.new("RGBA", (2048, 512), (80, 80, 80, 255))

import random
x = 0
for folder in folders:
    files = list((VOODOO / folder).glob("*.png"))
    if not files: continue
    img = Image.open(random.choice(files)).convert("RGBA")
    img_r = resize_rgba(img, 480)
    bg.paste(img_r, (x + 16, 16), img_r)
    x += 512

bg.save(VOODOO / "test_items.png")
print("Saved test_items.png")
