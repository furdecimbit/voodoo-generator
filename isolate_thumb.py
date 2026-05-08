import numpy as np
from PIL import Image
from pathlib import Path

VOODOO = Path("/Users/alperozdil/Documents/voodoo")

body = Image.open(VOODOO / "body" / "IMG_9977.PNG").convert("RGBA")
arr = np.array(body)
crop = arr[1100:1230, 1320:1550].copy()

# User erased what should be transparent — use their alpha mask directly
marked = np.array(Image.open(VOODOO / "thumb_test.png").convert("RGBA"))
keep_mask = marked[:,:,3] > 0

result = crop.copy()
result[~keep_mask, 3] = 0

out_img = Image.fromarray(result)
out_img.save(VOODOO / "thumb_isolated.png")

bg = Image.new("RGBA", out_img.size, (80,80,80,255))
bg.paste(out_img, (0,0), out_img)
bg.save(VOODOO / "thumb_isolated_preview.png")
print("done")
