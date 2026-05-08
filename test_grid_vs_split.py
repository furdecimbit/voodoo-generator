from PIL import Image
from pathlib import Path

VOODOO = Path("/Users/alperozdil/Documents/voodoo")

# 44.png is in items/split — which grid does it come from?
# items grids are 5x5, each cell 625x625 (3125/5)
# 44.png = index 43 (0-based), grid file 6.png = first grid = items 0-24, 7.png = 25-49...
# Let's figure out: 44 is 1-indexed, so index 43, grid index = 43//25 = 1 -> 7.png, cell = 43%25 = 18
# row=18//5=3, col=18%5=3

grid_file = VOODOO / "items" / "7.png"
grid = Image.open(grid_file).convert("RGBA")
cell_size = 625
row, col = 3, 3
cell = grid.crop((col*cell_size, row*cell_size, (col+1)*cell_size, (row+1)*cell_size))

# Load the split version
split = Image.open(VOODOO / "knife" / "44.png").convert("RGBA")

# Show both on flat bg side by side
bg = Image.new("RGBA", (1300, 650), (80, 80, 80, 255))
bg.paste(cell, (10, 10), cell)
bg.paste(split, (660, 10), split)
bg.save(VOODOO / "test_grid_vs_split.png")
print(f"grid cell size={cell.size}, split size={split.size}")
