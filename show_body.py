from PIL import Image
from pathlib import Path
import random

VOODOO = Path("/Users/alperozdil/Documents/voodoo")
files = list((VOODOO / "body").glob("*.PNG"))
body = Image.open(files[0]).convert("RGBA")

bg = Image.new("RGBA", body.size, (80, 80, 80, 255))
bg.paste(body, (0, 0), body)
bg.save(VOODOO / "body_ref.png")
print(f"Saved body_ref.png  size={body.size}  file={files[0].name}")
