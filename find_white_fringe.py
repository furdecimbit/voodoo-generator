import numpy as np
from PIL import Image
from pathlib import Path

VOODOO = Path("/Users/alperozdil/Documents/voodoo")

for folder in ["knife", "offhand", "necklace", "eyes"]:
    bad = []
    for f in sorted((VOODOO / folder).glob("*.png")):
        arr = np.array(Image.open(f).convert("RGBA"))
        transp = arr[:,:,3] == 0
        if transp.any():
            rgb = arr[transp][:,:3]
            white_count = ((rgb[:,0]>200) & (rgb[:,1]>200) & (rgb[:,2]>200)).sum()
            if white_count > 10:
                bad.append(f"{f.name}: {white_count} white transparent pixels")
    if bad:
        print(f"\n{folder}/")
        for b in bad: print(f"  {b}")
    else:
        print(f"\n{folder}/: temiz")
