import random, numpy as np
from PIL import Image, ImageFilter
from pathlib import Path

def resize_rgba(img, size):
    arr = np.array(img).astype(np.float32)
    a = arr[:,:,3:4] / 255.0
    arr[:,:,:3] *= a  # premultiply: transparent pixels become black, not white
    tmp = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGBA')
    tmp = tmp.resize((size, size), Image.LANCZOS)
    arr2 = np.array(tmp).astype(np.float32)
    a2 = arr2[:,:,3:4] / 255.0
    arr2[:,:,:3] = np.where(a2 > 0, arr2[:,:,:3] / np.maximum(a2, 1e-6), 0)
    # Kill semi-transparent fringe pixels
    arr2[:,:,3] = np.where(arr2[:,:,3] < 20, 0, arr2[:,:,3])
    arr2[:,:,:3] *= (arr2[:,:,3:4] > 0)
    return Image.fromarray(np.clip(arr2, 0, 255).astype(np.uint8), 'RGBA')

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

def soft_light(base, blend):
    D = np.where(base<=0.25, ((16*base-12)*base+4)*base, np.sqrt(np.maximum(base,0)))
    return np.where(blend<=0.5,
        base-(1-2*blend)*base*(1-base),
        base+(2*blend-1)*(D-base))

def apply_color_overlay(img, color, opacity=0.55):
    arr = np.array(img).astype(np.float32)/255.0
    alpha = arr[:,:,3:4]; rgb = arr[:,:,:3]
    blend = np.array([color[0]/255, color[1]/255, color[2]/255], dtype=np.float32)
    result = soft_light(rgb, np.ones_like(rgb)*blend)
    # Only apply overlay on fully opaque pixels; edge pixels keep original RGB
    result = rgb*(1-opacity*alpha)+result*opacity*alpha
    return Image.fromarray((np.concatenate([np.clip(result,0,1),alpha],axis=2)*255).astype(np.uint8))

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

def compose():
    bg = Image.open(VOODOO / "back.png").convert("RGBA")
    W, H = bg.size  # 3125x3125

    # Load random body
    body_orig = random_item(VOODOO / "body")

    # Resize body to fill frame: scale so the larger dim = frame size
    bw, bh = body_orig.size
    scale = min(W / bw, H / bh)
    new_bw = int(bw * scale)
    new_bh = int(bh * scale)
    arr = np.array(body_orig).astype(np.float32)
    a = arr[:,:,3:4] / 255.0
    arr[:,:,:3] *= a
    tmp = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGBA')
    tmp = tmp.resize((new_bw, new_bh), Image.LANCZOS)
    arr2 = np.array(tmp).astype(np.float32)
    a2 = arr2[:,:,3:4] / 255.0
    arr2[:,:,:3] = np.where(a2 > 0, arr2[:,:,:3] / np.maximum(a2, 1e-6), 0)
    body_scaled = Image.fromarray(np.clip(arr2, 0, 255).astype(np.uint8), 'RGBA')

    # Apply random color overlay
    color = (random.randint(80,255), random.randint(80,255), random.randint(80,255))
    body_colored = apply_color_overlay(body_scaled, color)


    # Get landmarks on scaled body
    lm = get_body_landmarks(body_colored)

    # Feet target: y = H - 820 from top = 2305 in 3125px frame
    feet_target_y = H - 560

    # Platform center x (approx center of frame)
    platform_cx = W // 2  # 1562 — center the character horizontally

    # Offset to place body: foot should land at feet_target_y
    # body_bottom (in scaled coords) should map to feet_target_y
    # foot_cx (in scaled coords) should map to platform_cx
    offset_x = platform_cx - lm['foot_cx']
    offset_y = feet_target_y - lm['body_bottom']

    # Composite scene
    scene = bg.copy()

    # Paste body
    scene.paste(body_colored, (offset_x, offset_y), body_colored)

    # Helper: landmark → scene coords
    def sx(x): return x + offset_x
    def sy(y): return y + offset_y

    bh_scene = lm['body_h']  # body height in scaled pixels

    # Items
    knife_img    = random_item(VOODOO / "knife")
    offhand_img  = random_item(VOODOO / "offhand")
    neck_img     = random_item(VOODOO / "necklace")
    eye_files    = list((VOODOO / "eyes").glob("*.png"))
    eye1_img     = Image.open(random.choice(eye_files)).convert("RGBA")
    eye2_img     = Image.open(random.choice(eye_files)).convert("RGBA")

    knife_size   = int(bh_scene * 0.30)
    offhand_size = int(bh_scene * 0.26)
    neck_size    = int(lm['head_r'] * 0.44)
    eye_size     = lm['eye_size']

    paste_centered(scene, knife_img,
        sx(lm['rhand_x'])+0, sy(lm['rhand_y'])-180, knife_size)

    # Right thumb overlay: find topmost pixel of right hand, crop just that finger
    body_solid = np.array(body_colored)[:,:,3] > 128
    hand_r = int(lm['head_r'] * 0.55)
    hx, hy = lm['rhand_x'], lm['rhand_y']
    # Thumb overlay: crop from body_colored using pre-isolated mask, paste at exact position
    thumb_mask_src = Image.open(VOODOO / "thumb_isolated.png").convert("RGBA")
    sc = body_colored.width / 2048
    thumb_origin_x = int(1320 * sc)
    thumb_origin_y = int(1100 * sc)
    thumb_w = int(230 * sc)
    thumb_h = int(130 * sc)
    # Crop colored body at thumb region
    body_thumb_crop = body_colored.crop((thumb_origin_x, thumb_origin_y,
                                         thumb_origin_x + thumb_w, thumb_origin_y + thumb_h))
    # Scale mask to match
    mask_scaled = thumb_mask_src.resize((thumb_w, thumb_h), Image.LANCZOS)
    mask_alpha = np.array(mask_scaled)[:,:,3]
    # Apply mask alpha to colored crop
    body_thumb_arr = np.array(body_thumb_crop).copy()
    body_thumb_arr[:,:,3] = np.minimum(body_thumb_arr[:,:,3], mask_alpha)
    thumb_final = Image.fromarray(body_thumb_arr)
    scene.paste(thumb_final, (thumb_origin_x + offset_x, thumb_origin_y + offset_y), thumb_final)
    paste_centered(scene, offhand_img.transpose(Image.FLIP_LEFT_RIGHT),
        sx(lm['lhand_x'])-30+100, sy(lm['lhand_y'])-60, offhand_size)
    neck_cx_final = sx(lm['neck_cx'])+int(neck_size*0.25)-20
    neck_cy_final = sy(lm['neck_y'])+int(neck_size*0.3)+neck_size//2

    # Find shoulder-level rope start points (body left/right edge at neck_y)
    body_arr = np.array(body_colored)
    solid_body = body_arr[:,:,3] > 128
    neck_row = min(lm['neck_y'], body_arr.shape[0]-1)
    cols = np.where(solid_body[neck_row,:])[0]
    if len(cols):
        left_x  = int(cols[0])
        right_x = int(cols[-1])
    else:
        left_x  = lm['neck_cx'] - lm['head_r']
        right_x = lm['neck_cx'] + lm['head_r']

    # Draw necklace string: two bezier curves from shoulders to necklace
    from PIL import ImageDraw
    draw = ImageDraw.Draw(scene)
    x1, y1 = neck_cx_final, neck_cy_final
    rope_w = max(3, neck_size // 30)
    for start_x in [left_x, right_x]:
        sx0 = start_x + offset_x
        sy0 = lm['neck_y'] + offset_y
        pts = []
        for t in [i/30 for i in range(31)]:
            cx_ctrl = (sx0 + x1) / 2
            cy_ctrl = (sy0 + y1) / 2 + neck_size * 0.15
            bx = (1-t)**2 * sx0 + 2*(1-t)*t * cx_ctrl + t**2 * x1
            by = (1-t)**2 * sy0 + 2*(1-t)*t * cy_ctrl + t**2 * y1
            pts.append((int(bx), int(by)))
        draw.line(pts, fill=(60, 40, 20, 220), width=rope_w)

    paste_centered(scene, neck_img, neck_cx_final, neck_cy_final, neck_size)
    paste_with_shadow(scene, eye1_img,
        sx(lm['head_cx'])-lm['eye_gap']+20, sy(lm['eye_y'])+20, eye_size)
    paste_with_shadow(scene, eye2_img,
        sx(lm['head_cx'])+lm['eye_gap']+5, sy(lm['eye_y'])+10, eye_size)

    out = VOODOO / "compose_test5.png"
    scene.save(out)
    print(f"Saved {out}  bg={W}x{H}  body_scaled={new_bw}x{new_bh}  offset=({offset_x},{offset_y})  feet_y={sy(lm['body_bottom'])}")

compose()
