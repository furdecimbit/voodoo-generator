import random, numpy as np
from PIL import Image, ImageFilter
from pathlib import Path

VOODOO = Path("/Users/alperozdil/Documents/voodoo")

def get_body_landmarks(body_img):
    arr = np.array(body_img)
    solid = arr[:,:,3] > 128
    rows = np.where(solid.any(axis=1))[0]
    top, bottom = int(rows[0]), int(rows[-1])
    body_h = bottom - top
    head_bottom_y = top + int(body_h * 0.38)
    max_w, head_cx, head_cy = 0, arr.shape[1]//2, top
    for y in range(top, head_bottom_y):
        c = np.where(solid[y,:])[0]
        if len(c) and c[-1]-c[0] > max_w:
            max_w = c[-1]-c[0]; head_cx = int((c[0]+c[-1])//2); head_cy = y
    head_r = max_w // 2
    neck_start = head_cy + int(head_r*0.8)
    neck_end   = top + int(body_h*0.55)
    min_nw, neck_y = 9999, neck_start
    for y in range(neck_start, neck_end):
        c = np.where(solid[y,:])[0]
        if len(c) and c[-1]-c[0] < min_nw:
            min_nw = c[-1]-c[0]; neck_y = y
    hand_range = range(top+int(body_h*0.55), top+int(body_h*0.82), 2)
    max_rx, max_ry, min_lx, min_ly = 0,0,9999,0
    for y in hand_range:
        c = np.where(solid[y,:])[0]
        if len(c):
            if c[-1]>max_rx: max_rx,max_ry=int(c[-1]),y
            if c[0]<min_lx:  min_lx,min_ly=int(c[0]),y
    foot_xs=[]
    for y in range(bottom-int(body_h*0.08), bottom+1):
        c=np.where(solid[y,:])[0]
        if len(c): foot_xs.extend(c.tolist())
    foot_cx = int(np.mean(foot_xs)) if foot_xs else head_cx
    return dict(head_cx=head_cx, head_cy=head_cy, head_r=head_r,
        eye_y=head_cy-int(head_r*0.05), eye_gap=int(head_r*0.50),
        eye_size=int(head_r*0.55*0.80*1.05),
        neck_y=neck_y, neck_cx=head_cx,
        rhand_x=max_rx, rhand_y=max_ry, lhand_x=min_lx, lhand_y=min_ly,
        body_top=top, body_bottom=bottom, body_h=body_h, foot_cx=foot_cx)

def resize_rgba(img, size):
    arr = np.array(img).astype(np.float32)
    a = arr[:,:,3:4] / 255.0
    arr[:,:,:3] *= a
    tmp = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGBA')
    tmp = tmp.resize((size, size), Image.LANCZOS)
    arr2 = np.array(tmp).astype(np.float32)
    a2 = arr2[:,:,3:4] / 255.0
    arr2[:,:,:3] = np.where(a2 > 0, arr2[:,:,:3] / np.maximum(a2, 1e-6), 0)
    return Image.fromarray(np.clip(arr2, 0, 255).astype(np.uint8), 'RGBA')

def paste_centered(canvas, img, cx, cy, size):
    img = resize_rgba(img, size)
    x, y = cx - size//2, cy - size//2
    canvas.paste(img, (x, y), img)

def paste_with_shadow(canvas, img, cx, cy, size):
    img = resize_rgba(img, size)
    shadow = Image.new("RGBA", (size+20, size+20), (0,0,0,0))
    mask = img.split()[3].filter(ImageFilter.GaussianBlur(6))
    dark = Image.new("RGBA", (size, size), (0,0,0,180))
    shadow.paste(dark, (10,10), mask)
    sx, sy = cx - (size+20)//2, cy - (size+20)//2
    canvas.paste(shadow, (sx, sy), shadow)
    x, y = cx - size//2, cy - size//2
    canvas.paste(img, (x, y), img)

def random_item(folder):
    files = list(Path(folder).glob("*.png")) + list(Path(folder).glob("*.PNG"))
    return Image.open(random.choice(files)).convert("RGBA")

bg = Image.open(VOODOO / "back.png").convert("RGBA")
W, H = bg.size

body_orig = random_item(VOODOO / "body")
bw, bh = body_orig.size
scale = min(W / bw, H / bh)
new_bw, new_bh = int(bw * scale), int(bh * scale)
body_scaled = body_orig.resize((new_bw, new_bh), Image.LANCZOS)
# NO color overlay

lm = get_body_landmarks(body_scaled)
feet_target_y = H - 560
platform_cx = W // 2
offset_x = platform_cx - lm['foot_cx']
offset_y = feet_target_y - lm['body_bottom']

scene = bg.copy()
scene.paste(body_scaled, (offset_x, offset_y), body_scaled)

def sx(x): return x + offset_x
def sy(y): return y + offset_y

bh_scene = lm['body_h']
knife_img    = random_item(VOODOO / "knife")
offhand_img  = random_item(VOODOO / "offhand")
neck_img     = random_item(VOODOO / "necklace")
eye_files    = list((VOODOO / "eyes").glob("*.png"))
eye1_img     = Image.open(random.choice(eye_files)).convert("RGBA")
eye2_img     = Image.open(random.choice(eye_files)).convert("RGBA")

knife_size   = int(bh_scene * 0.30)
offhand_size = int(bh_scene * 0.26)
neck_size    = int(lm['head_r'] * 0.85)
eye_size     = lm['eye_size']

paste_centered(scene, knife_img, sx(lm['rhand_x'])+30, sy(lm['rhand_y'])-60, knife_size)
paste_centered(scene, offhand_img.transpose(Image.FLIP_LEFT_RIGHT), sx(lm['lhand_x'])-30, sy(lm['lhand_y'])-60, offhand_size)
paste_centered(scene, neck_img, sx(lm['neck_cx']), sy(lm['neck_y'])+int(neck_size*0.3), neck_size)
paste_with_shadow(scene, eye1_img, sx(lm['head_cx'])-lm['eye_gap']+20, sy(lm['eye_y'])+20, eye_size)
paste_with_shadow(scene, eye2_img, sx(lm['head_cx'])+lm['eye_gap']+5, sy(lm['eye_y'])+10, eye_size)

scene.save(VOODOO / "test_nooverlay.png")
print("saved test_nooverlay.png")
