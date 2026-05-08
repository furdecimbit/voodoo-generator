import numpy as np
from PIL import Image
from pathlib import Path

VOODOO = Path("/Users/alperozdil/Documents/voodoo")

knife = Image.open(VOODOO / "knife" / "44.png").convert("RGBA")
arr = np.array(knife)

# Find edge pixels: semi-transparent (alpha 1-254) and check their RGB
semi = (arr[:,:,3] > 0) & (arr[:,:,3] < 255)
if semi.any():
    edge_rgb = arr[semi][:,:3]
    print(f"Semi-transparent pixels: {semi.sum()}")
    print(f"RGB mean: {edge_rgb.mean(axis=0)}")
    print(f"RGB max:  {edge_rgb.max(axis=0)}")
    print(f"White-ish (R>200,G>200,B>200) count: {((edge_rgb[:,0]>200)&(edge_rgb[:,1]>200)&(edge_rgb[:,2]>200)).sum()}")
else:
    print("No semi-transparent pixels — fully binary alpha")

# Also check fully transparent pixels RGB
transp = arr[:,:,3] == 0
print(f"\nFully transparent pixels: {transp.sum()}")
transp_rgb = arr[transp][:,:3]
print(f"Transparent RGB mean: {transp_rgb.mean(axis=0)}")
print(f"Transparent white-ish count: {((transp_rgb[:,0]>200)&(transp_rgb[:,1]>200)&(transp_rgb[:,2]>200)).sum()}")
