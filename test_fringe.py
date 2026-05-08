import numpy as np
from PIL import Image
from pathlib import Path

VOODOO = Path("/Users/alperozdil/Documents/voodoo")

def resize_premult(img, w, h):
    arr = np.array(img).astype(np.float32)
    a = arr[:,:,3:4] / 255.0
    arr[:,:,:3] *= a
    tmp = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGBA')
    tmp = tmp.resize((w, h), Image.LANCZOS)
    arr2 = np.array(tmp).astype(np.float32)
    a2 = arr2[:,:,3:4] / 255.0
    arr2[:,:,:3] = np.where(a2 > 0, arr2[:,:,:3] / np.maximum(a2, 1e-6), 0)
    return Image.fromarray(np.clip(arr2, 0, 255).astype(np.uint8), 'RGBA')

# Test 1: body resize only, no overlay — dark bg
body = Image.open(list((VOODOO/"body").glob("*.PNG"))[0]).convert("RGBA")
body_r = resize_premult(body, 800, 800)
bg1 = Image.new("RGBA", (800, 800), (40, 40, 40, 255))
bg1.paste(body_r, (0,0), body_r)
bg1.save(VOODOO / "test_fringe_body.png")

# Test 2: knife resize only, dark bg
knife = Image.open(VOODOO / "knife" / "44.png").convert("RGBA")
knife_r = resize_premult(knife, 400, 400)
bg2 = Image.new("RGBA", (400, 400), (40, 40, 40, 255))
bg2.paste(knife_r, (0,0), knife_r)
bg2.save(VOODOO / "test_fringe_knife.png")

print("done")
