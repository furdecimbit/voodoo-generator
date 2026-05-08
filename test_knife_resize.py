import numpy as np
from PIL import Image
from pathlib import Path

VOODOO = Path("/Users/alperozdil/Documents/voodoo")

def resize_premult(img, size):
    arr = np.array(img).astype(np.float32)
    a = arr[:,:,3:4] / 255.0
    arr[:,:,:3] *= a
    tmp = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGBA')
    tmp = tmp.resize((size, size), Image.LANCZOS)
    arr2 = np.array(tmp).astype(np.float32)
    a2 = arr2[:,:,3:4] / 255.0
    arr2[:,:,:3] = np.where(a2 > 0, arr2[:,:,:3] / np.maximum(a2, 1e-6), 0)
    return Image.fromarray(np.clip(arr2, 0, 255).astype(np.uint8), 'RGBA')

knife = Image.open(VOODOO / "knife" / "44.png").convert("RGBA")
knife_r = resize_premult(knife, 400)

bg = Image.new("RGBA", (400, 400), (80, 80, 80, 255))
bg.paste(knife_r, (0, 0), knife_r)
bg.save(VOODOO / "test_knife_resize.png")
print("done")
