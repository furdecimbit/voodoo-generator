from PIL import Image
from pathlib import Path
import random

VOODOO = Path("/Users/alperozdil/Documents/voodoo")

body_files = list((VOODOO / "body").glob("*.PNG")) + list((VOODOO / "body").glob("*.png"))
body = Image.open(random.choice(body_files)).convert("RGBA")

bg = Image.new("RGBA", body.size, (80, 80, 80, 255))
bg.paste(body, (0, 0), body)

out = VOODOO / "test_noresize.png"
bg.save(out)
print(f"Saved {out}  body size={body.size}")
