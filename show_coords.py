import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

VOODOO = Path("/Users/alperozdil/Documents/voodoo")
body = Image.open(VOODOO / "body" / "IMG_9977.PNG").convert("RGBA")
bg = Image.new("RGBA", body.size, (80, 80, 80, 255))
bg.paste(body, (0, 0), body)
draw = ImageDraw.Draw(bg)

W, H = body.size

# Grid every 100px
for x in range(0, W, 100):
    draw.line([(x, 0), (x, H)], fill=(255,255,255,60), width=1)
    draw.text((x+2, 2), str(x), fill=(255,255,0,200))
for y in range(0, H, 100):
    draw.line([(0, y), (W, y)], fill=(255,255,255,60), width=1)
    draw.text((2, y+2), str(y), fill=(255,255,0,200))

# Detect rhand
arr = np.array(body)
solid = arr[:,:,3] > 128
body_h_range = range(int(H*0.55), int(H*0.82), 2)
max_rx, max_ry = 0, 0
for y in body_h_range:
    c = np.where(solid[y,:])[0]
    if len(c) and c[-1] > max_rx:
        max_rx, max_ry = int(c[-1]), y

# Mark rhand
r = 15
draw.ellipse([max_rx-r, max_ry-r, max_rx+r, max_ry+r], outline=(255,0,0,255), width=3)
draw.text((max_rx+r+5, max_ry), f"rhand ({max_rx},{max_ry})", fill=(255,0,0,255))

bg.save(VOODOO / "body_coords.png")
print(f"rhand=({max_rx},{max_ry})")
