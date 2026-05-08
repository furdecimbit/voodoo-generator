import random, numpy as np
from PIL import Image, ImageFilter, ImageDraw
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

def soft_light(base, blend):
    D = np.where(base<=0.25, ((16*base-12)*base+4)*base, np.sqrt(np.maximum(base,0)))
    return np.where(blend<=0.5, base-(1-2*blend)*base*(1-base), base+(2*blend-1)*(D-base))

def apply_color_overlay(img, color, opacity=0.75):
    arr = np.array(img).astype(np.float32)/255.0
    alpha = arr[:,:,3:4]; rgb = arr[:,:,:3]
    blend = np.array([color[0]/255, color[1]/255, color[2]/255], dtype=np.float32)
    result = soft_light(rgb, np.ones_like(rgb)*blend)
    result = rgb*(1-opacity*alpha)+result*opacity*alpha
    return Image.fromarray((np.concatenate([np.clip(result,0,1),alpha],axis=2)*255).astype(np.uint8))

def paste_centered(canvas, img, cx, cy):
    # No resize — original size
    w, h = img.size
    canvas.paste(img, (cx - w//2, cy - h//2), img)

def paste_with_shadow(canvas, img, cx, cy):
    w, h = img.size
    pad = 26
    # Expand alpha, blur to get soft shaped shadow
    alpha_big = Image.new("L", (w+pad, h+pad), 0)
    alpha_big.paste(img.split()[3], (pad//2, pad//2))
    shadow_alpha = alpha_big.filter(ImageFilter.GaussianBlur(5))
    shadow_alpha_arr = np.clip(np.array(shadow_alpha).astype(np.float32) * 1.6, 0, 255).astype(np.uint8)
    black_layer = Image.new("RGBA", (w+pad, h+pad), (0, 0, 0, 255))
    mask_img = Image.fromarray(shadow_alpha_arr, 'L')
    canvas.paste(black_layer, (cx-(w+pad)//2, cy-(h+pad)//2), mask_img)
    canvas.paste(img, (cx-w//2, cy-h//2), img)

def draw_pins(scene, body_colored, offset_x, offset_y, n_pins=1, exclude_rects=None):
    arr = np.array(body_colored)
    solid = arr[:,:,3] > 128
    from scipy.ndimage import binary_erosion
    eroded = binary_erosion(solid)
    edge = solid & ~eroded
    edge_pts = np.argwhere(edge)
    if len(edge_pts) < n_pins:
        return
    # Filter edge points that would place pin head over excluded rects
    if exclude_rects:
        def head_pos(ey, ex):
            r = 10
            y0, y1 = max(0, ey-r), min(solid.shape[0], ey+r+1)
            x0, x1 = max(0, ex-r), min(solid.shape[1], ex+r+1)
            patch = solid[y0:y1, x0:x1].astype(np.float32)
            gy2 = np.gradient(patch, axis=0); gx2 = np.gradient(patch, axis=1)
            ny2 = -float(gy2[ey-y0, ex-x0]); nx2 = -float(gx2[ey-y0, ex-x0])
            mag = np.sqrt(nx2*nx2+ny2*ny2)
            if mag < 1e-6: return None
            nx2/=mag; ny2/=mag
            import math
            L_est = 350
            hx = ex + offset_x + int(nx2 * L_est * (0.5 - 0.65)) + int(nx2 * L_est * 0.5)
            hy = ey + offset_y + int(ny2 * L_est * (0.5 - 0.65)) + int(ny2 * L_est * 0.5)
            return hx, hy
        def overlaps(hx, hy, pad=80):
            for (rx0,ry0,rx1,ry1) in exclude_rects:
                if rx0-pad < hx < rx1+pad and ry0-pad < hy < ry1+pad:
                    return True
            return False
        valid = []
        for pt in edge_pts:
            hp = head_pos(pt[0], pt[1])
            if hp and not overlaps(hp[0], hp[1]):
                valid.append(pt)
        edge_pts = np.array(valid) if valid else edge_pts
    chosen = edge_pts[np.random.choice(len(edge_pts), min(n_pins, len(edge_pts)), replace=False)]
    pin_files = list((VOODOO / "pins").glob("*.png"))
    for (ey, ex) in chosen:
        r = 10
        y0, y1 = max(0, ey-r), min(solid.shape[0], ey+r+1)
        x0, x1 = max(0, ex-r), min(solid.shape[1], ex+r+1)
        patch = solid[y0:y1, x0:x1].astype(np.float32)
        gy = np.gradient(patch, axis=0)
        gx = np.gradient(patch, axis=1)
        cy2 = ey - y0; cx2 = ex - x0
        ny = -float(gy[cy2, cx2])
        nx = -float(gx[cy2, cx2])
        mag = np.sqrt(nx*nx + ny*ny)
        if mag < 1e-6:
            continue
        nx /= mag; ny /= mag
        # Angle: pin images are vertical (head up, tip down = 270deg)
        # We want tip to point inward (-normal direction)
        import math
        # Pin default: head at top, tip at bottom (tip direction = (0,1))
        # Want tip to point inward = (-nx, -ny)
        inward_angle = math.degrees(math.atan2(-ny, -nx))
        default_tip_angle = 90.0  # (0,1) = 90deg from x-axis
        angle_deg = inward_angle - default_tip_angle
        pin_raw = Image.open(random.choice(pin_files)).convert("RGBA")
        # Replace white glow with head color
        p_arr = np.array(pin_raw).astype(np.float32)
        head_region = p_arr[:pin_raw.height//6, :, :]
        solid = head_region[:,:,3] > 128
        non_white = solid & ~((head_region[:,:,0]>220) & (head_region[:,:,1]>220) & (head_region[:,:,2]>220))
        if non_white.sum() > 0:
            hc = head_region[non_white, :3].mean(axis=0)
        else:
            hc = np.array([220, 80, 80], dtype=np.float32)
        white_mask = (p_arr[:,:,0]>220) & (p_arr[:,:,1]>220) & (p_arr[:,:,2]>220) & (p_arr[:,:,3]>10)
        p_arr[white_mask, 0] = hc[0]
        p_arr[white_mask, 1] = hc[1]
        p_arr[white_mask, 2] = hc[2]
        pin_raw = Image.fromarray(np.clip(p_arr, 0, 255).astype(np.uint8), 'RGBA')
        # Premultiplied rotate to avoid white fringe
        pa = np.array(pin_raw).astype(np.float32)
        pa[:,:,:3] *= pa[:,:,3:4] / 255.0
        pin_pre = Image.fromarray(np.clip(pa, 0, 255).astype(np.uint8), 'RGBA')
        pin_pre = pin_pre.rotate(-angle_deg, expand=True, resample=Image.BICUBIC)
        pa2 = np.array(pin_pre).astype(np.float32)
        a2 = pa2[:,:,3:4] / 255.0
        pa2[:,:,:3] = np.where(a2 > 0, pa2[:,:,:3] / np.maximum(a2, 1e-6), 0)
        pa2[:,:,3] = np.where(pa2[:,:,3] < 20, 0, pa2[:,:,3])
        pin_img = Image.fromarray(np.clip(pa2, 0, 255).astype(np.uint8), 'RGBA')
        pin_img = pin_img.resize((pin_img.width//2, pin_img.height//2), Image.LANCZOS)
        pw, ph = pin_img.size
        L = max(pw, ph)  # pin length along needle axis
        embed_frac = 0.40  # how much of pin is inside body
        # Center the pin so edge point is at embed_frac from tip (tip side = inward)
        center_x = ex + offset_x + int(nx * L * (0.5 - embed_frac))
        center_y = ey + offset_y + int(ny * L * (0.5 - embed_frac))
        sx2 = center_x - pw // 2
        sy2 = center_y - ph // 2
        scene.paste(pin_img, (sx2, sy2), pin_img)

def random_item(folder):
    files = list(Path(folder).glob("*.png")) + list(Path(folder).glob("*.PNG"))
    return Image.open(random.choice(files)).convert("RGBA")

def compose(flat_bg=None):
    W, H = 2048, 2048

    # Background layers, all scaled to 2048x2048
    if flat_bg is not None:
        bg = Image.new("RGBA", (W, H), flat_bg + (255,))
    else:
        bg = Image.open(VOODOO / "back3.png").convert("RGBA").resize((W, H), Image.LANCZOS)
        import colorsys as _cs
        ov_h = random.random()
        ov_r, ov_g, ov_b = _cs.hsv_to_rgb(ov_h, 0.7, 0.9)
        ov_color = np.array([ov_r, ov_g, ov_b], dtype=np.float32)
        bg_arr = np.array(bg).astype(np.float32) / 255.0
        b = bg_arr[:,:,:3]
        g = np.ones_like(b) * ov_color
        overlay_blend = np.where(b < 0.5, 2*b*g, 1 - 2*(1-b)*(1-g))
        blended = np.clip(b * 0.55 + overlay_blend * 0.45, 0, 1)
        bg_arr[:,:,:3] = blended
        bg = Image.fromarray((bg_arr * 255).astype(np.uint8), 'RGBA')
    # Remove white bg via flood fill from all 4 corners before resize
    from collections import deque
    plat_orig = Image.open(VOODOO / "platform.png").convert("RGBA")
    plat_arr = np.array(plat_orig)
    PH, PW = plat_arr.shape[:2]
    is_white = (plat_arr[:,:,0] > 230) & (plat_arr[:,:,1] > 230) & (plat_arr[:,:,2] > 230)
    visited = np.zeros((PH, PW), bool)
    q = deque()
    for sy2, sx2 in [(0,0),(0,PW-1),(PH-1,0),(PH-1,PW-1)]:
        if is_white[sy2, sx2] and not visited[sy2, sx2]:
            visited[sy2, sx2] = True
            q.append((sy2, sx2))
    while q:
        y2, x2 = q.popleft()
        for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
            ny, nx = y2+dy, x2+dx
            if 0<=ny<PH and 0<=nx<PW and not visited[ny,nx] and is_white[ny,nx]:
                visited[ny,nx] = True
                q.append((ny,nx))
    plat_arr[visited, 3] = 0
    # Erode alpha by 2px to remove white fringe at platform edges
    from scipy.ndimage import binary_erosion
    alpha_mask = plat_arr[:,:,3] > 0
    eroded = binary_erosion(alpha_mask, iterations=2)
    plat_arr[~eroded, 3] = 0
    plat_clean = Image.fromarray(plat_arr)
    # Premultiplied resize to avoid white fringe
    pa = np.array(plat_clean).astype(np.float32)
    a = pa[:,:,3:4] / 255.0
    pa[:,:,:3] *= a
    tmp = Image.fromarray(np.clip(pa, 0, 255).astype(np.uint8), 'RGBA').resize((W, H), Image.LANCZOS)
    pa2 = np.array(tmp).astype(np.float32)
    a2 = pa2[:,:,3:4] / 255.0
    pa2[:,:,:3] = np.where(a2 > 0, pa2[:,:,:3] / np.maximum(a2, 1e-6), 0)
    pa2[:,:,3] = np.where(pa2[:,:,3] < 15, 0, pa2[:,:,3])
    platform_img = Image.fromarray(np.clip(pa2, 0, 255).astype(np.uint8), 'RGBA')

    # Body: original size, no resize
    body_orig = random_item(VOODOO / "body")
    color = (random.randint(80,255), random.randint(80,255), random.randint(80,255))
    body_colored = apply_color_overlay(body_orig, color)

    lm = get_body_landmarks(body_colored)

    # Feet target: proportional to 3125 setup (was H-560 in 3125)
    feet_target_y = int(H * (1 - 560/3125))  # ≈ 1633
    platform_cx = W // 2

    offset_x = platform_cx - lm['foot_cx']
    offset_y = feet_target_y - lm['body_bottom'] + 100

    scene = bg.copy()

    # Vintage layer just above background — overlay blend
    vintage_img = Image.open(VOODOO / "vintage.png").convert("RGBA").resize((W, H), Image.LANCZOS)
    base = np.array(scene).astype(np.float32) / 255.0
    vin = np.array(vintage_img).astype(np.float32) / 255.0
    v_alpha = vin[:,:,3:4]
    b = base[:,:,:3]; g = vin[:,:,:3]
    overlay = np.where(b < 0.5, 2*b*g, 1 - 2*(1-b)*(1-g))
    blended = np.clip(b + (overlay - b) * v_alpha, 0, 1)
    out_arr = np.concatenate([blended, base[:,:,3:4]], axis=2)
    scene = Image.fromarray((out_arr * 255).astype(np.uint8), 'RGBA')


    def sx(x): return x + offset_x
    def sy(y): return y + offset_y

    bh = lm['body_h']

    knife_img   = random_item(VOODOO / "knife" / "approved")
    offhand_img = random_item(VOODOO / "offhand")
    neck_img    = random_item(VOODOO / "necklace")
    eye_files   = list((VOODOO / "eyes").glob("*.png"))
    eye1_img    = Image.open(random.choice(eye_files)).convert("RGBA")
    eye2_img    = Image.open(random.choice(eye_files)).convert("RGBA")

    neck_size = int(lm['head_r'] * 0.44)
    neck_cx_final = sx(lm['neck_cx'])+int(neck_size*0.25)-20+3
    neck_cy_final = sy(lm['neck_y'])+int(neck_size*0.3)+neck_size//2+20

    # Knife = sağ taraf (büyük x), offhand = sol taraf (küçük x) — izleyici perspektifinden
    right_x = max(lm['rhand_x'], lm['lhand_x'])
    right_y = lm['rhand_y'] if lm['rhand_x'] >= lm['lhand_x'] else lm['lhand_y']
    left_x  = min(lm['rhand_x'], lm['lhand_x'])
    left_y  = lm['lhand_y'] if lm['rhand_x'] >= lm['lhand_x'] else lm['rhand_y']

    kw, kh = knife_img.size
    knife_cx = sx(right_x); knife_cy = sy(right_y) - 180
    ow, oh = offhand_img.size
    offhand_cx = sx(left_x) + 70; offhand_cy = sy(left_y) - 60

    neck_w, neck_h = neck_img.size
    neck_new_w = int(neck_w * 0.80)
    neck_new_h = int(neck_h * 0.80)

    eye_size = int(lm['eye_size'] * 0.6 * 1.30 * 1.15)
    mouth_img = random_item(VOODOO / "mouths")
    mouth_cx = sx(lm['head_cx']) + 10
    mouth_cy = sy(lm['eye_y']) + eye_size // 2 + 100
    mw, mh = mouth_img.size
    eye1x = sx(lm['head_cx'])-lm['eye_gap']+20; eye1y = sy(lm['eye_y'])+20
    eye2x = sx(lm['head_cx'])+lm['eye_gap']+5;  eye2y = sy(lm['eye_y'])+10

    # Item bounding boxes for pin collision avoidance (also exclude hands and feet)
    hand_pad = 120
    foot_pad = 150
    item_rects = [
        # Hands (body coords + offset = canvas coords)
        (sx(right_x)-hand_pad, sy(right_y)-hand_pad, sx(right_x)+hand_pad, sy(right_y)+hand_pad),
        (sx(left_x)-hand_pad,  sy(left_y)-hand_pad,  sx(left_x)+hand_pad,  sy(left_y)+hand_pad),
        # Feet
        (0, sy(lm['body_bottom'])-foot_pad, W, sy(lm['body_bottom'])+foot_pad),
        (knife_cx - kw//2, knife_cy - kh//2, knife_cx + kw//2, knife_cy + kh//2),
        (offhand_cx - ow//2, offhand_cy - oh//2, offhand_cx + ow//2, offhand_cy + oh//2),
        (neck_cx_final - neck_new_w//2, neck_cy_final - neck_new_h//2, neck_cx_final + neck_new_w//2, neck_cy_final + neck_new_h//2),
        (eye1x - eye_size//2, eye1y - eye_size//2, eye1x + eye_size//2, eye1y + eye_size//2),
        (eye2x - eye_size//2, eye2y - eye_size//2, eye2x + eye_size//2, eye2y + eye_size//2),
        (mouth_cx - mw//2, mouth_cy - mh//2, mouth_cx + mw//2, mouth_cy + mh//2),
    ]

    # Layer order: pin (behind body) → body → items
    draw_pins(scene, body_colored, offset_x, offset_y, n_pins=1, exclude_rects=item_rects)
    scene.paste(body_colored, (offset_x, offset_y), body_colored)

    paste_centered(scene, knife_img, knife_cx, knife_cy)
    paste_centered(scene, offhand_img, offhand_cx, offhand_cy)

    # Necklace rope
    from PIL import ImageDraw
    draw = ImageDraw.Draw(scene)
    body_arr = np.array(body_colored)
    solid_body = body_arr[:,:,3] > 128
    neck_row = min(lm['neck_y'], body_arr.shape[0]-1)
    cols = np.where(solid_body[neck_row,:])[0]
    left_x  = int(cols[0])  if len(cols) else lm['neck_cx']-lm['head_r']
    right_x = int(cols[-1]) if len(cols) else lm['neck_cx']+lm['head_r']
    rope_w = max(2, neck_size // 30)
    for start_x in [left_x, right_x]:
        sx0 = start_x + offset_x; sy0 = lm['neck_y'] + offset_y
        pts = []
        for t in [i/30 for i in range(31)]:
            cx_ctrl = (sx0+neck_cx_final)/2; cy_ctrl = (sy0+neck_cy_final)/2+neck_size*0.15
            bx = (1-t)**2*sx0+2*(1-t)*t*cx_ctrl+t**2*neck_cx_final
            by = (1-t)**2*sy0+2*(1-t)*t*cy_ctrl+t**2*neck_cy_final
            pts.append((int(bx),int(by)))
        draw.line(pts, fill=(60,40,20,220), width=rope_w)

    neck_img_r = neck_img.resize((neck_new_w, neck_new_h), Image.LANCZOS)
    scene.paste(neck_img_r, (neck_cx_final - neck_new_w//2, neck_cy_final - neck_new_h//2), neck_img_r)

    def premult_resize(img, size):
        a = np.array(img).astype(np.float32)
        alpha = a[:,:,3:4] / 255.0
        a[:,:,:3] *= alpha
        tmp = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'RGBA').resize((size, size), Image.LANCZOS)
        a2 = np.array(tmp).astype(np.float32)
        a2c = a2[:,:,3:4] / 255.0
        a2[:,:,:3] = np.where(a2c > 0, a2[:,:,:3] / np.maximum(a2c, 1e-6), 0)
        a2[:,:,3] = np.where(a2[:,:,3] < 20, 0, a2[:,:,3])
        return Image.fromarray(np.clip(a2, 0, 255).astype(np.uint8), 'RGBA')
    eye1_r = premult_resize(eye1_img, eye_size)
    eye2_r = premult_resize(eye2_img, eye_size)
    paste_with_shadow(scene, eye1_r, eye1x, eye1y)
    paste_with_shadow(scene, eye2_r, eye2x, eye2y)

    paste_centered(scene, mouth_img, mouth_cx, mouth_cy)

    # Thumb: fill only inside black outline, from interior seed point
    from collections import deque
    body_thumb = np.array(body_colored.crop((1320, 1100, 1550, 1230))).copy()
    H2, W2 = body_thumb.shape[:2]
    is_black = (body_thumb[:,:,0] < 60) & (body_thumb[:,:,1] < 60) & (body_thumb[:,:,2] < 60) & (body_thumb[:,:,3] > 128)
    is_transparent = body_thumb[:,:,3] == 0
    barrier = is_black | is_transparent
    # Find interior seed: centroid of non-barrier pixels in upper half
    candidates = np.argwhere(~barrier[:H2//2, :])
    interior = np.zeros((H2,W2), bool)
    if len(candidates):
        sy, sx = candidates[len(candidates)//2]
        q = deque([(sy, sx)])
        interior[sy, sx] = True
        while q:
            y,x = q.popleft()
            for dy,dx in [(-1,0),(1,0),(0,-1),(0,1)]:
                ny,nx = y+dy,x+dx
                if 0<=ny<H2 and 0<=nx<W2 and not barrier[ny,nx] and not interior[ny,nx]:
                    interior[ny,nx] = True
                    q.append((ny,nx))
    # Keep: interior + black outline, remove everything else
    keep = interior | is_black
    body_thumb[~keep, 3] = 0
    thumb_src = Image.fromarray(body_thumb)
    scene.paste(thumb_src, (1320 + offset_x, 1100 + offset_y), thumb_src)


    return scene

for i in range(1, 4):
    scene = compose()
    out = VOODOO / f"compose_test_{i}.png"
    scene.save(out)
    print(f"Saved {out}")
