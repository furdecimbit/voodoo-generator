from PIL import Image
from pathlib import Path

VOODOO = Path("/Users/alperozdil/Documents/voodoo")

knife = Image.open(VOODOO / "knife" / "44.png").convert("RGBA")
bg = Image.new("RGBA", knife.size, (80, 80, 80, 255))
bg.paste(knife, (0, 0), knife)
bg.save(VOODOO / "test_knife.png")
print(f"knife size={knife.size}")
