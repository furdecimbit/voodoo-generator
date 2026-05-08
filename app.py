import base64, io, random, math, colorsys
from pathlib import Path
from collections import deque

import numpy as np
from PIL import Image, ImageFilter, ImageDraw
from scipy.ndimage import binary_erosion
from flask import Flask, jsonify, request, send_file, render_template_string

VOODOO = Path(__file__).parent
app = Flask(__name__)

# ── image helpers ────────────────────────────────────────────────────────────

def premult_resize(img, w, h):
    a = np.array(img).astype(np.float32)
    al = a[:,:,3:4] / 255.0
    a[:,:,:3] *= al
    tmp = Image.fromarray(np.clip(a,0,255).astype(np.uint8),'RGBA').resize((w,h), Image.LANCZOS)
    a2 = np.array(tmp).astype(np.float32)
    a2c = a2[:,:,3:4]/255.0
    a2[:,:,:3] = np.where(a2c>0, a2[:,:,:3]/np.maximum(a2c,1e-6), 0)
    a2[:,:,3] = np.where(a2[:,:,3]<20, 0, a2[:,:,3])
    return Image.fromarray(np.clip(a2,0,255).astype(np.uint8),'RGBA')

def premult_resize_sq(img, size):
    return premult_resize(img, size, size)

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

def overlay_blend_arr(base_arr, color_rgb, strength=0.45):
    b = base_arr[:,:,:3].astype(np.float32)/255.0
    g = np.array([c/255.0 for c in color_rgb], dtype=np.float32)
    ov = np.where(b<0.5, 2*b*g, 1-2*(1-b)*(1-g))
    blended = np.clip(b*( 1-strength) + ov*strength, 0, 1)
    out = base_arr.copy().astype(np.float32)
    out[:,:,:3] = blended*255
    return out.astype(np.uint8)

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
            max_w=c[-1]-c[0]; head_cx=int((c[0]+c[-1])//2); head_cy=y
    head_r = max_w//2
    neck_start = head_cy+int(head_r*0.8)
    neck_end   = top+int(body_h*0.55)
    min_nw, neck_y = 9999, neck_start
    for y in range(neck_start, neck_end):
        c = np.where(solid[y,:])[0]
        if len(c) and c[-1]-c[0] < min_nw:
            min_nw=c[-1]-c[0]; neck_y=y
    hand_range = range(top+int(body_h*0.55), top+int(body_h*0.82), 2)
    max_rx,max_ry,min_lx,min_ly = 0,0,9999,0
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
    return dict(head_cx=head_cx,head_cy=head_cy,head_r=head_r,
        eye_y=head_cy-int(head_r*0.05),eye_gap=int(head_r*0.50),
        eye_size=int(head_r*0.55*0.80*1.05),
        neck_y=neck_y,neck_cx=head_cx,
        rhand_x=max_rx,rhand_y=max_ry,lhand_x=min_lx,lhand_y=min_ly,
        body_top=top,body_bottom=bottom,body_h=body_h,foot_cx=foot_cx)

def paste_centered(canvas, img, cx, cy):
    w,h = img.size
    canvas.paste(img, (cx-w//2, cy-h//2), img)

def paste_with_shadow(canvas, img, cx, cy):
    w,h = img.size; pad=26
    alpha_big = Image.new("L",(w+pad,h+pad),0)
    alpha_big.paste(img.split()[3],(pad//2,pad//2))
    sa = alpha_big.filter(ImageFilter.GaussianBlur(5))
    sa_arr = np.clip(np.array(sa).astype(np.float32)*1.6,0,255).astype(np.uint8)
    black = Image.new("RGBA",(w+pad,h+pad),(0,0,0,255))
    canvas.paste(black,(cx-(w+pad)//2,cy-(h+pad)//2),Image.fromarray(sa_arr,'L'))
    canvas.paste(img,(cx-w//2,cy-h//2),img)

def draw_pins(scene, body_colored, offset_x, offset_y, n_pins=1, exclude_rects=None):
    if n_pins == 0: return
    arr = np.array(body_colored)
    solid = arr[:,:,3]>128
    eroded = binary_erosion(solid)
    edge = solid & ~eroded
    edge_pts = np.argwhere(edge)
    if len(edge_pts) < n_pins: return
    if exclude_rects:
        def head_pos(ey,ex):
            r=10; y0,y1=max(0,ey-r),min(solid.shape[0],ey+r+1)
            x0,x1=max(0,ex-r),min(solid.shape[1],ex+r+1)
            patch=solid[y0:y1,x0:x1].astype(np.float32)
            gy2=np.gradient(patch,axis=0); gx2=np.gradient(patch,axis=1)
            ny2=-float(gy2[ey-y0,ex-x0]); nx2=-float(gx2[ey-y0,ex-x0])
            mag=np.sqrt(nx2*nx2+ny2*ny2)
            if mag<1e-6: return None
            nx2/=mag; ny2/=mag
            L_est=350
            hx=ex+offset_x+int(nx2*L_est*0.5); hy=ey+offset_y+int(ny2*L_est*0.5)
            return hx,hy
        def overlaps(hx,hy,pad=80):
            for (rx0,ry0,rx1,ry1) in exclude_rects:
                if rx0-pad<hx<rx1+pad and ry0-pad<hy<ry1+pad: return True
            return False
        valid=[]
        for pt in edge_pts:
            hp=head_pos(pt[0],pt[1])
            if hp and not overlaps(hp[0],hp[1]): valid.append(pt)
        edge_pts=np.array(valid) if valid else edge_pts
    chosen=edge_pts[np.random.choice(len(edge_pts),min(n_pins,len(edge_pts)),replace=False)]
    pin_files=list((VOODOO/"pins").glob("*.png"))
    for (ey,ex) in chosen:
        r=10; y0,y1=max(0,ey-r),min(solid.shape[0],ey+r+1)
        x0,x1=max(0,ex-r),min(solid.shape[1],ex+r+1)
        patch=solid[y0:y1,x0:x1].astype(np.float32)
        gy=np.gradient(patch,axis=0); gx=np.gradient(patch,axis=1)
        cy2=ey-y0; cx2=ex-x0
        ny_v=-float(gy[cy2,cx2]); nx_v=-float(gx[cy2,cx2])
        mag=np.sqrt(nx_v*nx_v+ny_v*ny_v)
        if mag<1e-6: continue
        nx_v/=mag; ny_v/=mag
        inward_angle=math.degrees(math.atan2(-ny_v,-nx_v))
        angle_deg=inward_angle-90.0
        pin_raw=Image.open(random.choice(pin_files)).convert("RGBA")
        p_arr=np.array(pin_raw).astype(np.float32)
        head_region=p_arr[:pin_raw.height//6,:,:]
        s_mask=head_region[:,:,3]>128
        non_white=s_mask&~((head_region[:,:,0]>220)&(head_region[:,:,1]>220)&(head_region[:,:,2]>220))
        hc=head_region[non_white,:3].mean(axis=0) if non_white.sum()>0 else np.array([220,80,80],dtype=np.float32)
        white_mask=(p_arr[:,:,0]>220)&(p_arr[:,:,1]>220)&(p_arr[:,:,2]>220)&(p_arr[:,:,3]>10)
        p_arr[white_mask,0]=hc[0]; p_arr[white_mask,1]=hc[1]; p_arr[white_mask,2]=hc[2]
        pin_raw=Image.fromarray(np.clip(p_arr,0,255).astype(np.uint8),'RGBA')
        pa=np.array(pin_raw).astype(np.float32)
        pa[:,:,:3]*=pa[:,:,3:4]/255.0
        pin_pre=Image.fromarray(np.clip(pa,0,255).astype(np.uint8),'RGBA')
        pin_pre=pin_pre.rotate(-angle_deg,expand=True,resample=Image.BICUBIC)
        pa2=np.array(pin_pre).astype(np.float32)
        a2=pa2[:,:,3:4]/255.0
        pa2[:,:,:3]=np.where(a2>0,pa2[:,:,:3]/np.maximum(a2,1e-6),0)
        pa2[:,:,3]=np.where(pa2[:,:,3]<20,0,pa2[:,:,3])
        pin_img=Image.fromarray(np.clip(pa2,0,255).astype(np.uint8),'RGBA')
        pin_img=pin_img.resize((pin_img.width//2,pin_img.height//2),Image.LANCZOS)
        pw,ph=pin_img.size; L=max(pw,ph)
        embed_frac=0.40
        center_x=ex+offset_x+int(nx_v*L*(0.5-embed_frac))
        center_y=ey+offset_y+int(ny_v*L*(0.5-embed_frac))
        scene.paste(pin_img,(center_x-pw//2,center_y-ph//2),pin_img)

def build_platform():
    from collections import deque
    plat_orig = Image.open(VOODOO/"platform.png").convert("RGBA")
    plat_arr = np.array(plat_orig)
    PH,PW = plat_arr.shape[:2]
    is_white=(plat_arr[:,:,0]>230)&(plat_arr[:,:,1]>230)&(plat_arr[:,:,2]>230)
    visited=np.zeros((PH,PW),bool)
    q=deque()
    for sy2,sx2 in [(0,0),(0,PW-1),(PH-1,0),(PH-1,PW-1)]:
        if is_white[sy2,sx2] and not visited[sy2,sx2]:
            visited[sy2,sx2]=True; q.append((sy2,sx2))
    while q:
        y2,x2=q.popleft()
        for dy,dx in [(-1,0),(1,0),(0,-1),(0,1)]:
            ny,nx=y2+dy,x2+dx
            if 0<=ny<PH and 0<=nx<PW and not visited[ny,nx] and is_white[ny,nx]:
                visited[ny,nx]=True; q.append((ny,nx))
    plat_arr[visited,3]=0
    alpha_mask=plat_arr[:,:,3]>0
    eroded=binary_erosion(alpha_mask,iterations=2)
    plat_arr[~eroded,3]=0
    return Image.fromarray(plat_arr)

# ── core compose ─────────────────────────────────────────────────────────────

def compose(params):
    W, H = 2048, 2048

    # Background
    bg_type = params.get('bg_type', 'back3')
    if bg_type == 'flat':
        hex_c = params.get('bg_color', '#4feaff').lstrip('#')
        r,g,b = int(hex_c[0:2],16),int(hex_c[2:4],16),int(hex_c[4:6],16)
        bg = Image.new("RGBA",(W,H),(r,g,b,255))
    else:
        bg = Image.open(VOODOO/"back3.png").convert("RGBA").resize((W,H),Image.LANCZOS)

    # Overlay color on background
    ov_hue = float(params.get('overlay_hue', random.random()))  # 0-1
    ov_sat = float(params.get('overlay_sat', 0.7))
    ov_val = float(params.get('overlay_val', 0.9))
    ov_str = float(params.get('overlay_strength', 0.45))
    ov_r,ov_g,ov_b = colorsys.hsv_to_rgb(ov_hue, ov_sat, ov_val)
    bg_arr = overlay_blend_arr(np.array(bg), (int(ov_r*255),int(ov_g*255),int(ov_b*255)), ov_str)
    bg = Image.fromarray(bg_arr,'RGBA')

    # Body
    body_file = params.get('body_file')
    if body_file:
        body_orig = open_img(VOODOO/"body"/body_file)
    else:
        files = []
        for r in RARITIES:
            files += list((VOODOO/"body"/r).glob("*.PNG")) + list((VOODOO/"body"/r).glob("*.png"))
        body_orig = open_img(random.choice(files))

    # Body color
    body_hue = float(params.get('body_hue', random.random()))
    body_sat = float(params.get('body_sat', 0.6))
    body_val = float(params.get('body_val', 0.85))
    br,bg2,bb = colorsys.hsv_to_rgb(body_hue, body_sat, body_val)
    color = (int(br*255),int(bg2*255),int(bb*255))
    body_colored = apply_color_overlay(body_orig, color)

    lm = get_body_landmarks(body_colored)
    feet_target_y = int(H*(1-560/3125))
    platform_cx = W//2
    offset_x = platform_cx - lm['foot_cx']
    offset_y = feet_target_y - lm['body_bottom'] + 100

    scene = bg.copy()

    # Vintage overlay blend
    vintage_img = Image.open(VOODOO/"vintage.png").convert("RGBA").resize((W,H),Image.LANCZOS)
    base = np.array(scene).astype(np.float32)/255.0
    vin = np.array(vintage_img).astype(np.float32)/255.0
    v_alpha = vin[:,:,3:4]
    b_ch=base[:,:,:3]; g_ch=vin[:,:,:3]
    ov2=np.where(b_ch<0.5,2*b_ch*g_ch,1-2*(1-b_ch)*(1-g_ch))
    blended=np.clip(b_ch+(ov2-b_ch)*v_alpha,0,1)
    out_arr=np.concatenate([blended,base[:,:,3:4]],axis=2)
    scene=Image.fromarray((out_arr*255).astype(np.uint8),'RGBA')

    def sx(x): return x+offset_x
    def sy(y): return y+offset_y

    bh = lm['body_h']

    # Items
    def load_item(folder, fname):
        base = VOODOO/folder
        if fname and fname != '__random__':
            # fname may be "common/53.png" or just "53.png"
            return open_img(base/fname)
        # Random: search flat + all rarity subfolders
        files = list(base.glob("*.png")) + list(base.glob("*.PNG"))
        for r in RARITIES:
            files += list((base/r).glob("*.png")) + list((base/r).glob("*.PNG"))
        return open_img(random.choice(files))

    knife_img   = load_item("knife/approved",  params.get('knife_file'))
    offhand_img = load_item("offhand",        params.get('offhand_file'))
    neck_img    = load_item("necklace",       params.get('necklace_file'))
    eye1_img    = load_item("eyes",           params.get('eye_left_file'))
    eye2_img    = load_item("eyes",           params.get('eye_right_file'))
    mouth_img   = load_item("mouths",         params.get('mouth_file'))

    neck_size = int(lm['head_r']*0.44)
    neck_cx_final = sx(lm['neck_cx'])+int(neck_size*0.25)-20+3
    neck_cy_final = sy(lm['neck_y'])+int(neck_size*0.3)+neck_size//2+20

    right_x=max(lm['rhand_x'],lm['lhand_x'])
    right_y=lm['rhand_y'] if lm['rhand_x']>=lm['lhand_x'] else lm['lhand_y']
    left_x =min(lm['rhand_x'],lm['lhand_x'])
    left_y =lm['lhand_y'] if lm['rhand_x']>=lm['lhand_x'] else lm['rhand_y']

    kw,kh=knife_img.size; knife_cx=sx(right_x); knife_cy=sy(right_y)-180
    ow,oh=offhand_img.size; offhand_cx=sx(left_x)+70; offhand_cy=sy(left_y)-60

    neck_new_w=int(neck_img.size[0]*0.80); neck_new_h=int(neck_img.size[1]*0.80)
    eye_size=int(lm['eye_size']*0.6*1.30*1.15*1.10)
    mouth_cx=sx(lm['head_cx'])+10; mouth_cy=sy(lm['eye_y'])+eye_size//2+100
    mw,mh=mouth_img.size
    eye1x=sx(lm['head_cx'])-lm['eye_gap']+20; eye1y=sy(lm['eye_y'])+20
    eye2x=sx(lm['head_cx'])+lm['eye_gap']+5;  eye2y=sy(lm['eye_y'])+10

    hand_pad=120; foot_pad=150
    item_rects=[
        (sx(right_x)-hand_pad,sy(right_y)-hand_pad,sx(right_x)+hand_pad,sy(right_y)+hand_pad),
        (sx(left_x)-hand_pad, sy(left_y)-hand_pad, sx(left_x)+hand_pad, sy(left_y)+hand_pad),
        (0,sy(lm['body_bottom'])-foot_pad,W,sy(lm['body_bottom'])+foot_pad),
        (knife_cx-kw//2,knife_cy-kh//2,knife_cx+kw//2,knife_cy+kh//2),
        (offhand_cx-ow//2,offhand_cy-oh//2,offhand_cx+ow//2,offhand_cy+oh//2),
        (neck_cx_final-neck_new_w//2,neck_cy_final-neck_new_h//2,neck_cx_final+neck_new_w//2,neck_cy_final+neck_new_h//2),
        (eye1x-eye_size//2,eye1y-eye_size//2,eye1x+eye_size//2,eye1y+eye_size//2),
        (eye2x-eye_size//2,eye2y-eye_size//2,eye2x+eye_size//2,eye2y+eye_size//2),
        (mouth_cx-mw//2,mouth_cy-mh//2,mouth_cx+mw//2,mouth_cy+mh//2),
    ]

    n_pins = int(params.get('pin_count', 1))
    draw_pins(scene, body_colored, offset_x, offset_y, n_pins=n_pins, exclude_rects=item_rects)
    scene.paste(body_colored,(offset_x,offset_y),body_colored)

    # Hair strands — drawn on top of everything (front layer)
    n_hair = int(params.get('hair_count', 15))
    if n_hair > 0:
        hair_draw = ImageDraw.Draw(scene)
        rng = random.Random(params.get('hair_seed', random.randint(0, 99999)))
        head_top_y = sy(lm['body_top'])
        head_cx_s  = sx(lm['head_cx'])
        spread = int(lm['head_r'] * 0.65)

        def bez_chain(pts, steps=30):
            out = []
            for i in range(len(pts)-1):
                p0 = pts[max(0,i-1)]
                p1 = pts[i]
                p2 = pts[i+1]
                p3 = pts[min(len(pts)-1,i+2)]
                for t in range(steps):
                    u = t / steps
                    x = 0.5*((2*p1[0])+(-p0[0]+p2[0])*u+(2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*u*u+(-p0[0]+3*p1[0]-3*p2[0]+p3[0])*u*u*u)
                    y = 0.5*((2*p1[1])+(-p0[1]+p2[1])*u+(2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*u*u+(-p0[1]+3*p1[1]-3*p2[1]+p3[1])*u*u*u)
                    out.append((int(x),int(y)))
            out.append(pts[-1])
            return out

        hair_hex = params.get('hair_color', '#1a1008').lstrip('#')
        hr, hg, hb = int(hair_hex[0:2],16), int(hair_hex[2:4],16), int(hair_hex[4:6],16)

        min_y = head_top_y - 180   # strands won't go above this

        for _ in range(n_hair):
            start_x = head_cx_s + rng.randint(-150, 150)
            start_y = head_top_y + rng.randint(55, 85)
            pts = [(start_x, start_y)]
            cx2, cy2 = start_x, start_y

            # Phase 1: 2 straight-up segments, ±1-5° from vertical
            straight_segs = 2
            straight_len = rng.randint(30, 60)
            for s in range(straight_segs):
                angle_deg = rng.uniform(-4, 4)           # ±4° from straight up
                dx = int(straight_len * math.sin(math.radians(angle_deg)))
                dy = straight_len + rng.randint(-5, 5)
                cx2 += dx
                cy2 -= dy
                cy2 = max(cy2, min_y)
                pts.append((cx2, cy2))

            # Phase 2: 2-4 bending segments with more drift
            bend_segs = rng.randint(2, 4)
            bend_len = rng.randint(25, 60)
            for s in range(bend_segs):
                cx2 += rng.randint(-70, 70)
                cy2 -= bend_len + rng.randint(-15, 15)
                cy2 = max(cy2, min_y)
                pts.append((cx2, cy2))
            strand = bez_chain(pts)
            if len(strand) >= 2:
                thickness = rng.randint(4, 10)
                # slight color variation per strand
                var = rng.randint(-18, 18)
                rc = max(0, min(255, hr + var))
                gc = max(0, min(255, hg + var))
                bc = max(0, min(255, hb + var))
                hair_draw.line(strand, fill=(rc, gc, bc, 235), width=thickness)

    # Knife rarity glow
    knife_file = params.get('knife_file','')
    knife_rarity = knife_file.split('/')[0] if '/' in knife_file else 'common'
    glow_colors = {
        'rare':      (240, 200,  40),
        'legendary': ( 60, 220, 255),
        'ultimate':  (255, 100, 200),
    }
    if knife_rarity in glow_colors:
        gc = glow_colors[knife_rarity]
        kw2, kh2 = knife_img.size
        pad = 60
        glow_surf = Image.new("RGBA", (kw2+pad*2, kh2+pad*2), (0,0,0,0))
        glow_surf.paste(knife_img, (pad, pad), knife_img)
        mask = glow_surf.split()[3]
        for radius, alpha in [(25, 255), (15, 255), (8, 255), (3, 255)]:
            blurred = mask.filter(ImageFilter.GaussianBlur(radius))
            ba = np.array(blurred).astype(np.float32)
            ba = np.clip(ba * 1.6, 0, 255).astype(np.uint8)
            color_layer = Image.new("RGBA", glow_surf.size, gc+(alpha,))
            glow_layer = Image.new("RGBA", glow_surf.size, (0,0,0,0))
            glow_layer.paste(color_layer, mask=Image.fromarray(ba,'L'))
            scene.alpha_composite(glow_layer, (knife_cx-kw2//2-pad, knife_cy-kh2//2-pad))

    paste_centered(scene,knife_img,knife_cx,knife_cy)
    paste_centered(scene,offhand_img,offhand_cx,offhand_cy)

    draw2=ImageDraw.Draw(scene)
    body_arr=np.array(body_colored); solid_body=body_arr[:,:,3]>128
    neck_row=min(lm['neck_y'],body_arr.shape[0]-1)
    cols=np.where(solid_body[neck_row,:])[0]
    lx2=int(cols[0]) if len(cols) else lm['neck_cx']-lm['head_r']
    rx2=int(cols[-1]) if len(cols) else lm['neck_cx']+lm['head_r']
    rope_w=max(2,neck_size//30)
    for start_x in [lx2,rx2]:
        sx0=start_x+offset_x; sy0=lm['neck_y']+offset_y
        pts=[]
        for t in [i/30 for i in range(31)]:
            cx_ctrl=(sx0+neck_cx_final)/2; cy_ctrl=(sy0+neck_cy_final)/2+neck_size*0.15
            bx=(1-t)**2*sx0+2*(1-t)*t*cx_ctrl+t**2*neck_cx_final
            by=(1-t)**2*sy0+2*(1-t)*t*cy_ctrl+t**2*neck_cy_final
            pts.append((int(bx),int(by)))
        draw2.line(pts,fill=(60,40,20,220),width=rope_w)

    neck_img_r=neck_img.resize((neck_new_w,neck_new_h),Image.LANCZOS)
    scene.paste(neck_img_r,(neck_cx_final-neck_new_w//2,neck_cy_final-neck_new_h//2),neck_img_r)

    eye1_r=premult_resize_sq(eye1_img,eye_size); eye2_r=premult_resize_sq(eye2_img,eye_size)
    paste_with_shadow(scene,eye1_r,eye1x,eye1y)
    paste_with_shadow(scene,eye2_r,eye2x,eye2y)
    paste_centered(scene,mouth_img,mouth_cx,mouth_cy)

    # Thumb
    body_thumb=np.array(body_colored.crop((1320,1100,1550,1230))).copy()
    H2,W2=body_thumb.shape[:2]
    is_black=(body_thumb[:,:,0]<60)&(body_thumb[:,:,1]<60)&(body_thumb[:,:,2]<60)&(body_thumb[:,:,3]>128)
    is_transparent=body_thumb[:,:,3]==0
    barrier=is_black|is_transparent
    candidates=np.argwhere(~barrier[:H2//2,:])
    interior=np.zeros((H2,W2),bool)
    if len(candidates):
        sy_t,sx_t=candidates[len(candidates)//2]
        q=deque([(sy_t,sx_t)]); interior[sy_t,sx_t]=True
        while q:
            y,x=q.popleft()
            for dy,dx in [(-1,0),(1,0),(0,-1),(0,1)]:
                ny,nx=y+dy,x+dx
                if 0<=ny<H2 and 0<=nx<W2 and not barrier[ny,nx] and not interior[ny,nx]:
                    interior[ny,nx]=True; q.append((ny,nx))
    keep=interior|is_black
    body_thumb[~keep,3]=0
    thumb_src=Image.fromarray(body_thumb)
    scene.paste(thumb_src,(1320+offset_x,1100+offset_y),thumb_src)

    # Name text: y range 1800-1900, curved arc (center dips down), bloodcrowc font
    name = params.get('name', '').strip()
    if name:
        from PIL import ImageFont
        FONT_PATH = str(VOODOO / "bloodcrowc.ttf")
        y_center = 1870
        max_w = int(W * 0.80)

        # Auto-fit font size — cap at 110px so it stays smaller
        lo, hi = 20, 110
        best_font = None
        while lo <= hi:
            mid = (lo + hi) // 2
            try:
                fnt = ImageFont.truetype(FONT_PATH, mid)
            except Exception:
                fnt = ImageFont.load_default()
            tmp = Image.new("RGBA", (1,1))
            td = ImageDraw.Draw(tmp)
            bb = td.textbbox((0,0), name, font=fnt)
            if bb[2]-bb[0] <= max_w and bb[3]-bb[1] <= 90:
                best_font = fnt; lo = mid+1
            else:
                hi = mid-1

        if best_font:
            # Measure each character individually for arc placement
            tmp = Image.new("RGBA", (1,1))
            td = ImageDraw.Draw(tmp)
            chars = list(name)
            # total width
            full_bb = td.textbbox((0,0), name, font=best_font)
            total_w = full_bb[2] - full_bb[0]

            # Arc params: downward curve, center dips by arc_depth px
            arc_depth = 28   # how many px the center drops below edges
            cx = W // 2

            # Render each char onto a temp surface, then rotate+paste at arc position
            x_cursor = cx - total_w // 2
            char_data = []  # (char, x_offset, char_w)
            for ch in chars:
                bb_ch = td.textbbox((0,0), ch, font=best_font)
                cw = bb_ch[2] - bb_ch[0]
                char_data.append((ch, x_cursor - (cx - total_w//2), cw, bb_ch))
                x_cursor += cw

            # For each char compute arc y and rotation
            draw_name = ImageDraw.Draw(scene)
            for ch, x_off, cw, bb_ch in char_data:
                # normalized position -1..1 across total width
                t = (x_off + cw/2) / max(total_w, 1)  # 0..1
                t_centered = t * 2 - 1                  # -1..1
                # downward parabola: y increases at center
                arc_y = arc_depth * (1 - t_centered**2) * (-1)  # negative = up at edges, 0 at center... wait
                # We want center DOWN: arc_y = arc_depth * (1 - t_centered**2)  gives max at center=0 → actually (1-0)=1 max at center
                arc_y = int(arc_depth * (1 - t_centered**2))
                # angle: tangent of the parabola arc
                angle_deg = math.degrees(math.atan2(-2 * arc_depth * t_centered / max(total_w,1) * 2, 1)) * 0.6

                char_x = cx - total_w//2 + x_off
                char_y = y_center + arc_y

                # Render char on small transparent surface, rotate, paste
                ch_w = bb_ch[2]-bb_ch[0]+4; ch_h = bb_ch[3]-bb_ch[1]+4
                ch_surf = Image.new("RGBA", (ch_w+40, ch_h+40), (0,0,0,0))
                ch_draw = ImageDraw.Draw(ch_surf)
                ox = 20 - bb_ch[0]; oy = 20 - bb_ch[1]
                # shadow
                for sxo,syo in [(-2,3),(2,3),(0,4)]:
                    ch_draw.text((ox+sxo, oy+syo), ch, font=best_font, fill=(0,0,0,150))
                # main
                ch_draw.text((ox, oy), ch, font=best_font, fill=(220,190,130,255))

                # Premultiplied rotate
                pa = np.array(ch_surf).astype(np.float32)
                pa[:,:,:3] *= pa[:,:,3:4]/255.0
                rotated = Image.fromarray(np.clip(pa,0,255).astype(np.uint8),'RGBA')
                rotated = rotated.rotate(angle_deg, expand=True, resample=Image.BICUBIC)
                pa2 = np.array(rotated).astype(np.float32)
                a2 = pa2[:,:,3:4]/255.0
                pa2[:,:,:3] = np.where(a2>0, pa2[:,:,:3]/np.maximum(a2,1e-6), 0)
                pa2[:,:,3] = np.where(pa2[:,:,3]<15, 0, pa2[:,:,3])
                rotated = Image.fromarray(np.clip(pa2,0,255).astype(np.uint8),'RGBA')

                rw, rh = rotated.size
                paste_x = char_x + cw//2 - rw//2
                paste_y = char_y - rh//2
                scene.paste(rotated, (paste_x, paste_y), rotated)

    return scene

# ── routes ───────────────────────────────────────────────────────────────────

def open_img(path):
    from PIL import ImageOps
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    return img.convert("RGBA")

RARITIES = ['common', 'rare', 'legendary', 'ultimate']

def list_folder_flat(rel, exts=('png','PNG')):
    p = VOODOO/rel
    files=[]
    for e in exts: files+=sorted([f.name for f in p.glob(f'*.{e}')])
    return files

def list_folder_rarity(base, exts=('png','PNG')):
    """Returns {rarity: [filenames]} for categories with rarity subfolders."""
    result = {}
    for r in RARITIES:
        p = VOODOO/base/r
        if not p.exists(): continue
        files = []
        for e in exts: files += sorted([f.name for f in p.glob(f'*.{e}')])
        if files: result[r] = files
    return result

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/list')
def list_items():
    return jsonify({
        'body':     list_folder_rarity('body', ('PNG','png')),
        'knife':    list_folder_rarity('knife/approved'),
        'offhand':  list_folder_flat('offhand'),
        'necklace': list_folder_rarity('necklace'),
        'eyes':     list_folder_rarity('eyes'),
        'mouths':   list_folder_flat('mouths'),
    })

@app.route('/img/<path:rel_path>')
def serve_img(rel_path):
    p = VOODOO/rel_path
    return send_file(str(p))

@app.route('/generate', methods=['POST'])
def generate():
    params = request.json or {}
    scene = compose(params)
    # Downscale for preview (800px) to keep response fast
    preview_size = int(params.get('preview_size', 800))
    if preview_size < 2048:
        scene = scene.resize((preview_size,preview_size), Image.LANCZOS)
    buf = io.BytesIO()
    scene.save(buf, 'PNG', optimize=False)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return jsonify({'image': b64})

@app.route('/save', methods=['POST'])
def save():
    params = request.json or {}
    params['preview_size'] = 2048
    scene = compose(params)
    import time
    fname = f"generated_{int(time.time())}.png"
    out = VOODOO/fname
    scene.save(str(out))
    return jsonify({'filename': fname})

# ── HTML ──────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Voodoo Generator</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Crimson+Text:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<style>
  @font-face { font-family:'Blackburn'; src:url('/img/Blackburn.ttf'); }
  @font-face { font-family:'Bloodcrow'; src:url('/img/bloodcrowc.ttf'); }
</style>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{
    background:#080608;
    color:#d0c8b8;
    font-family:'Crimson Text',Georgia,serif;
    font-size:15px;
    height:100vh;display:flex;overflow:hidden;
  }

  /* sidebar */
  #sidebar{
    width:460px;min-width:460px;
    background:#100e10;
    border-right:1px solid #2e1f1f;
    overflow-y:auto;display:flex;flex-direction:column;gap:0;
  }
  #sidebar::-webkit-scrollbar{width:7px}
  #sidebar::-webkit-scrollbar-thumb{background:#3a2828;border-radius:4px}

  /* sidebar title */
  #sidebar-title{
    padding:30px 18px 14px;
    font-family:'Blackburn',serif;
    font-size:44px;
    color:#c8903a;
    letter-spacing:.06em;
    text-align:center;
    border-bottom:1px solid #2e1f1f;
    text-shadow:0 0 18px #c8903a66;
  }

  .section{border-bottom:1px solid #1e1414}
  .section-header{
    padding:14px 18px;
    font-family:'Blackburn',serif;
    font-size:20px;
    letter-spacing:.04em;
    color:#9a7858;
    cursor:pointer;
    display:flex;align-items:center;justify-content:space-between;
    user-select:none;
    transition:color .15s,background .15s;
  }
  .section-header:hover{color:#d4a84b;background:#1a1018}
  .section.open .section-header{color:#d4a84b}
  .section-body{
    padding:0 16px;
    background:#0c0a0c;
    max-height:0;
    overflow:hidden;
    transition:max-height .35s cubic-bezier(.4,0,.2,1), padding .35s;
  }
  .section.open .section-body{
    max-height:2000px;
    padding:12px 16px;
  }
  .section-header .arrow{font-size:16px;transition:transform .2s;opacity:.7}
  .section.open .section-header .arrow{transform:rotate(90deg)}

  /* grid of thumbnails */
  .thumb-grid{display:flex;flex-wrap:wrap;gap:8px}
  .thumb{
    width:72px;height:72px;
    object-fit:contain;
    background:#181018;
    border:2px solid #2a1e1e;
    border-radius:8px;
    cursor:pointer;
    transition:border-color .15s,transform .12s,box-shadow .15s;
  }
  .thumb:hover{border-color:#7a5a38;transform:scale(1.07);box-shadow:0 0 10px #c8903a44}
  .thumb.selected{border-color:#d4a84b;background:#231a08;box-shadow:0 0 14px #d4a84b55}

  /* rarity borders */
  .thumb.rarity-common  {border-color:#555}
  .thumb.rarity-rare    {border-color:#b8960a}
  .thumb.rarity-legendary{border-color:#4ab8d4}
  .thumb.rarity-ultimate{border-color:#d45a9a}
  .thumb.rarity-common.selected  {border-color:#aaa;  box-shadow:0 0 12px #aaa6}
  .thumb.rarity-rare.selected    {border-color:#f0c020;box-shadow:0 0 12px #f0c02066}
  .thumb.rarity-legendary.selected{border-color:#60d8f8;box-shadow:0 0 12px #60d8f866}
  .thumb.rarity-ultimate.selected {border-color:#f870c0;box-shadow:0 0 12px #f870c066}

  .rarity-label{font-family:'Blackburn',serif;font-size:17px;letter-spacing:.05em;margin:12px 0 6px;padding:2px 0}

  /* rarity filter bar */
  .rarity-filter{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px}
  .rf-btn{
    padding:4px 10px;
    border:1px solid #3a2828;
    border-radius:20px;
    background:#181018;
    font-family:'Blackburn',serif;
    font-size:13px;
    color:#7a6858;
    cursor:pointer;
    transition:background .15s,color .15s,border-color .15s;
  }
  .rf-btn:hover{color:#d4a84b;border-color:#6a4820}
  .rf-btn.active{background:#2a1a08;color:#d4a84b;border-color:#d4a84b}
  .rf-btn.rf-common.active  {color:#aaa;border-color:#aaa;background:#1e1e1e}
  .rf-btn.rf-rare.active    {color:#f0c020;border-color:#f0c020;background:#1e1800}
  .rf-btn.rf-legendary.active{color:#60d8f8;border-color:#60d8f8;background:#001e28}
  .rf-btn.rf-ultimate.active {color:#f870c0;border-color:#f870c0;background:#28001e}
  .rarity-label.common  {color:#888}
  .rarity-label.rare    {color:#c8a010}
  .rarity-label.legendary{color:#50c0d8}
  .rarity-label.ultimate{color:#e060b0}

  /* sub-labels (Left Eye / Right Eye) */
  .sub-label{
    font-family:'Blackburn',serif;
    font-size:17px;
    color:#6a4a30;
    letter-spacing:.04em;
    margin:10px 0 6px;
  }

  /* sub-accordion inside Eyes */
  .sub-section{border:1px solid #2a1a1a;border-radius:6px;margin-bottom:8px;overflow:hidden}
  .sub-section-header{
    padding:10px 14px;
    font-family:'Blackburn',serif;
    font-size:16px;
    letter-spacing:.04em;
    color:#8a6848;
    cursor:pointer;
    display:flex;align-items:center;justify-content:space-between;
    background:#181018;
    user-select:none;
    transition:color .15s,background .15s;
  }
  .sub-section-header:hover{color:#d4a84b;background:#201520}
  .sub-section.open .sub-section-header{color:#d4a84b;background:#1e1418}
  .sub-section-body{
    max-height:0;overflow:hidden;
    padding:0 12px;
    background:#100c10;
    transition:max-height .3s cubic-bezier(.4,0,.2,1), padding .3s;
  }
  .sub-section.open .sub-section-body{max-height:1200px;padding:10px 12px}
  .sub-section-header .sarrow{font-size:14px;transition:transform .2s;opacity:.6}
  .sub-section.open .sub-section-header .sarrow{transform:rotate(90deg)}

  /* sliders */
  .slider-row{display:flex;align-items:center;gap:10px;margin-bottom:10px}
  .slider-row label{
    width:140px;
    font-family:'Crimson Text',serif;
    font-size:16px;
    color:#a09078;
    flex-shrink:0;
    font-style:italic;
  }
  .slider-row input[type=range]{
    flex:1;
    accent-color:#d4a84b;
    height:5px;
    cursor:pointer;
  }
  .slider-row .val{width:42px;font-size:15px;color:#c8a870;text-align:right}

  /* color swatch */
  .hue-preview{width:28px;height:28px;border-radius:5px;border:1px solid #3a2828;flex-shrink:0}

  /* radio */
  .radio-row{display:flex;gap:16px;margin-bottom:12px}
  .radio-row label{
    font-family:'Crimson Text',serif;
    font-size:17px;
    font-style:italic;
    cursor:pointer;
    display:flex;align-items:center;gap:5px;
    color:#b09878;
  }
  .radio-row label:hover{color:#d4a84b}

  /* buttons */
  #btn-area{padding:16px;display:flex;flex-direction:column;gap:10px;border-top:1px solid #2e1f1f}
  button{
    padding:13px 10px;
    border:none;border-radius:8px;
    font-family:'Blackburn',serif;
    font-size:20px;
    letter-spacing:.04em;
    cursor:pointer;
    transition:opacity .15s,box-shadow .15s;
  }
  #btn-gen{
    background:linear-gradient(135deg,#c8801a,#e8b04a);
    color:#1a0e04;
    box-shadow:0 2px 18px #c8803a55;
  }
  #btn-gen:hover{box-shadow:0 2px 28px #c8803a99}
  #btn-rand{
    background:#1e1018;color:#c8903a;
    border:1px solid #4a3020;
  }
  #btn-save{
    background:#101e10;color:#7acc7a;
    border:1px solid #2a4a2a;
  }
  button:hover{opacity:.88}
  button:active{opacity:.65}

  /* preview area */
  #preview-area{
    flex:1;display:flex;flex-direction:column;
    align-items:center;justify-content:center;
    padding:24px;background:#080608;position:relative;
  }
  #preview-img{
    max-width:100%;max-height:calc(100vh - 80px);
    border-radius:12px;
    box-shadow:0 8px 50px #000c,0 0 60px #c8803a18;
    display:block;
  }
  #loading{
    position:absolute;inset:0;
    background:#080608c8;
    display:none;align-items:center;justify-content:center;
    flex-direction:column;gap:16px;
  }
  #loading.show{display:flex}
  .spinner{
    width:52px;height:52px;
    border:4px solid #2a1a10;
    border-top-color:#d4a84b;
    border-radius:50%;
    animation:spin .9s linear infinite;
  }
  @keyframes spin{to{transform:rotate(360deg)}}
  #loading p{
    font-family:'Blackburn',serif;
    font-size:18px;
    color:#d4a84b;
    letter-spacing:.1em;
    text-shadow:0 0 12px #d4a84b88;
  }

  #status{
    position:absolute;bottom:14px;right:18px;
    font-family:'Crimson Text',serif;
    font-size:18px;font-style:italic;
    color:#8a7060;
    letter-spacing:.03em;
  }

  input[type=color]{width:44px;height:32px;border:none;background:none;cursor:pointer;padding:0;border-radius:4px}
</style>
</head>
<body>

<div id="sidebar">
  <div id="sidebar-title">✦ VOODOO FORGE ✦</div>

  <div class="section" id="sec-bg">
    <div class="section-header" onclick="toggleSection('sec-bg')">⬡ Background <span class="arrow">›</span></div>
    <div class="section-body">
      <div class="radio-row">
        <label><input type="radio" name="bg_type" value="back3" checked onchange="scheduleGen()"> Texture</label>
        <label><input type="radio" name="bg_type" value="flat" onchange="scheduleGen()"> Flat Color</label>
      </div>
      <div id="flat-color-row" class="slider-row" style="display:none">
        <label>Color</label>
        <input type="color" id="bg_color" value="#1a1a2e" oninput="scheduleGen()">
      </div>
      <div class="slider-row">
        <label>Overlay Hue</label>
        <div class="hue-preview" id="ov-swatch"></div>
        <input type="range" id="overlay_hue" min="0" max="360" value="180" oninput="updateSwatch();scheduleGen()">
        <span class="val" id="overlay_hue_v">180</span>
      </div>
      <div class="slider-row">
        <label>Overlay Strength</label>
        <input type="range" id="overlay_strength" min="0" max="100" value="45" oninput="scheduleGen()">
        <span class="val" id="overlay_strength_v">45</span>
      </div>
    </div>
  </div>

  <div class="section" id="sec-body">
    <div class="section-header" onclick="toggleSection('sec-body')">☽ Body <span class="arrow">›</span></div>
    <div class="section-body">
      <div class="thumb-grid" id="grid-body"></div>
      <div style="margin-top:12px">
        <div class="slider-row">
          <label>Color Hue</label>
          <div class="hue-preview" id="body-swatch"></div>
          <input type="range" id="body_hue" min="0" max="360" value="30" oninput="updateBodySwatch();scheduleGen()">
          <span class="val" id="body_hue_v">30</span>
        </div>
        <div class="slider-row">
          <label>Saturation</label>
          <input type="range" id="body_sat" min="0" max="100" value="60" oninput="scheduleGen()">
          <span class="val" id="body_sat_v">60</span>
        </div>
      </div>
    </div>
  </div>

  <div class="section" id="sec-knife">
    <div class="section-header" onclick="toggleSection('sec-knife')">🗡 Blade — Right Hand <span class="arrow">›</span></div>
    <div class="section-body"><div class="thumb-grid" id="grid-knife"></div></div>
  </div>

  <div class="section" id="sec-offhand">
    <div class="section-header" onclick="toggleSection('sec-offhand')">☠ Offhand — Left Hand <span class="arrow">›</span></div>
    <div class="section-body"><div class="thumb-grid" id="grid-offhand"></div></div>
  </div>

  <div class="section" id="sec-necklace">
    <div class="section-header" onclick="toggleSection('sec-necklace')">⛧ Necklace <span class="arrow">›</span></div>
    <div class="section-body"><div class="thumb-grid" id="grid-necklace"></div></div>
  </div>

  <div class="section" id="sec-eyes">
    <div class="section-header" onclick="toggleSection('sec-eyes')">◉ Eyes <span class="arrow">›</span></div>
    <div class="section-body">
      <div class="sub-section" id="subsec-eye-left">
        <div class="sub-section-header" onclick="toggleSubSection('subsec-eye-left')">Left Eye <span class="sarrow">›</span></div>
        <div class="sub-section-body"><div class="thumb-grid" id="grid-eye-left"></div></div>
      </div>
      <div class="sub-section" id="subsec-eye-right">
        <div class="sub-section-header" onclick="toggleSubSection('subsec-eye-right')">Right Eye <span class="sarrow">›</span></div>
        <div class="sub-section-body"><div class="thumb-grid" id="grid-eye-right"></div></div>
      </div>
    </div>
  </div>

  <div class="section" id="sec-mouth">
    <div class="section-header" onclick="toggleSection('sec-mouth')">⌇ Mouth <span class="arrow">›</span></div>
    <div class="section-body"><div class="thumb-grid" id="grid-mouth"></div></div>
  </div>

  <div class="section" id="sec-pins">
    <div class="section-header" onclick="toggleSection('sec-pins')">✠ Pins <span class="arrow">›</span></div>
    <div class="section-body">
      <div class="slider-row">
        <label>Pin Count</label>
        <input type="range" id="pin_count" min="0" max="6" step="1" value="1" oninput="scheduleGen()">
        <span class="val" id="pin_count_v">1</span>
      </div>
    </div>
  </div>

  <div class="section" id="sec-hair">
    <div class="section-header" onclick="toggleSection('sec-hair')">〰 Hair <span class="arrow">›</span></div>
    <div class="section-body">
      <div class="slider-row">
        <label>Strand Count</label>
        <input type="range" id="hair_count" min="0" max="30" step="1" value="15" oninput="scheduleGen()">
        <span class="val" id="hair_count_v">20</span>
      </div>
      <div class="slider-row" style="margin-top:4px">
        <label>Color</label>
        <input type="color" id="hair_color" value="#1a1008" oninput="scheduleGen()">
      </div>
      <div class="slider-row">
        <label>Randomize</label>
        <button onclick="document.getElementById('hair_seed').value=Math.floor(Math.random()*99999);scheduleGen()" style="padding:6px 14px;font-size:14px;background:#1e1018;color:#c8903a;border:1px solid #4a3020;border-radius:6px">↻ New Style</button>
        <input type="hidden" id="hair_seed" value="12345">
      </div>
    </div>
  </div>

  <div class="section" id="sec-name">
    <div class="section-header" onclick="toggleSection('sec-name')">𖤐 Name <span class="arrow">›</span></div>
    <div class="section-body">
      <input type="text" id="name_input" placeholder="Enter name…" oninput="scheduleGen()"
        style="
          width:100%;padding:10px 14px;
          background:#180e18;
          border:1px solid #3a2030;
          border-radius:8px;
          color:#e8d8a8;
          font-family:'Bloodcrow',serif;
          font-size:15px;
          letter-spacing:.06em;
          outline:none;
          transition:border-color .2s;
        "
        onfocus="this.style.borderColor='#d4a84b'"
        onblur="this.style.borderColor='#3a2030'"
      >
      <p style="margin-top:8px;font-size:12px;font-style:italic;color:#6a5040">
        Appears between y 1800–1900 on the canvas
      </p>
    </div>
  </div>

  <div id="btn-area">
    <button id="btn-gen" onclick="generate()">⚡ Conjure</button>
    <button id="btn-rand" onclick="randomizeAll()">✦ Randomize All</button>
    <button id="btn-save" onclick="saveHQ()">☽ Save 2048px</button>
  </div>

</div>

<div id="preview-area">
  <img id="preview-img" src="" alt="Preview">
  <div id="loading">
    <div class="spinner"></div>
    <p>Conjuring…</p>
  </div>
  <div id="status">awaiting ritual…</div>
</div>

<script>
// State
const sel = {
  body_file: null, knife_file: null, offhand_file: null,
  necklace_file: null, eye_left_file: null, eye_right_file: null, mouth_file: null
};

let genTimer = null;
let isGenerating = false;

function toggleSection(id){
  const target = document.getElementById(id);
  const isOpen = target.classList.contains('open');
  document.querySelectorAll('.section.open').forEach(s => s.classList.remove('open'));
  if(!isOpen) target.classList.add('open');
}

function toggleSubSection(id){
  document.getElementById(id).classList.toggle('open');
}

function v(id){ return document.getElementById(id).value; }
function sv(id,val){ document.getElementById(id).textContent = val; }

// Update slider value displays
['overlay_hue','overlay_strength','body_hue','body_sat','pin_count','hair_count'].forEach(id=>{
  const el=document.getElementById(id);
  const lbl=document.getElementById(id+'_v');
  if(el&&lbl) el.addEventListener('input',()=>lbl.textContent=el.value);
});

document.querySelectorAll('input[name=bg_type]').forEach(r=>{
  r.addEventListener('change',()=>{
    document.getElementById('flat-color-row').style.display =
      r.value==='flat'&&r.checked ? 'flex' : 'none';
  });
});

function hsvToHex(h,s,v){
  // h 0-1, s 0-1, v 0-1
  let r,g,b;
  const i=Math.floor(h*6),f=h*6-i,p=v*(1-s),q=v*(1-f*s),t=v*(1-(1-f)*s);
  switch(i%6){case 0:r=v;g=t;b=p;break;case 1:r=q;g=v;b=p;break;case 2:r=p;g=v;b=t;break;
    case 3:r=p;g=q;b=v;break;case 4:r=t;g=p;b=v;break;case 5:r=v;g=p;b=q;break;}
  return '#'+[r,g,b].map(x=>Math.round(x*255).toString(16).padStart(2,'0')).join('');
}

function updateSwatch(){
  const h=parseInt(v('overlay_hue'))/360;
  document.getElementById('ov-swatch').style.background=hsvToHex(h,0.7,0.9);
}
function updateBodySwatch(){
  const h=parseInt(v('body_hue'))/360;
  document.getElementById('body-swatch').style.background=hsvToHex(h,0.6,0.85);
}
updateSwatch(); updateBodySwatch();

// Thumbnail grids
async function loadItems(){
  const res = await fetch('/list');
  const data = await res.json();

  buildGridRarity('grid-body',    'body',          data.body,     'body_file');
  buildGridRarity('grid-knife',   'knife/approved',data.knife,    'knife_file');
  buildGridFlat(  'grid-offhand', 'offhand',       data.offhand,  'offhand_file');
  buildGridFlat(  'grid-mouth',   'mouths',        data.mouths,   'mouth_file');
  buildGridRarity('grid-necklace','necklace',      data.necklace, 'necklace_file');
  buildGridRarity('grid-eye-left','eyes',          data.eyes,     'eye_left_file');
  buildGridRarity('grid-eye-right','eyes',         data.eyes,     'eye_right_file');
}

function buildGridFlat(gridId, folder, files, key){
  const grid=document.getElementById(gridId);
  grid.innerHTML='';
  if(!files||!files.length) return;
  files.forEach(fname=>{
    const img=document.createElement('img');
    img.className='thumb';
    img.src=`/img/${folder}/${fname}`;
    img.title=fname;
    img.dataset.path=fname;
    img.onclick=()=>selectThumb(grid, img, key, fname, scheduleGen);
    grid.appendChild(img);
  });
}

const RARITY_GLOW = {
  rare:      'drop-shadow(0 0 5px #f0c020aa)',
  legendary: 'drop-shadow(0 0 5px #60d8f8aa)',
  ultimate:  'drop-shadow(0 0 7px #f870c0cc)',
};

function buildGridRarity(gridId, folder, data, key){
  const gridEl = document.getElementById(gridId);
  const existingBar = gridEl.previousElementSibling;
  if(existingBar && existingBar.classList.contains('rarity-filter')) existingBar.remove();

  const grid=document.getElementById(gridId);
  grid.innerHTML='';
  if(!data) return;

  const isKnife = folder.includes('knife');
  const order=['common','rare','legendary','ultimate'];
  const available = order.filter(r => data[r]&&data[r].length);

  // Build filter bar
  const bar = document.createElement('div');
  bar.className = 'rarity-filter';

  function applyFilter(active){
    bar.querySelectorAll('.rf-btn').forEach(b=>b.classList.remove('active'));
    active.classList.add('active');
    const r = active.dataset.rarity;
    grid.querySelectorAll('.thumb').forEach(img=>{
      img.style.display = (r==='all' || img.classList.contains(`rarity-${r}`)) ? '' : 'none';
    });
  }

  const allBtn = document.createElement('button');
  allBtn.className='rf-btn active'; allBtn.textContent='All'; allBtn.dataset.rarity='all';
  allBtn.onclick=()=>applyFilter(allBtn);
  bar.appendChild(allBtn);

  available.forEach(r=>{
    const btn=document.createElement('button');
    btn.className=`rf-btn rf-${r}`; btn.textContent=r[0].toUpperCase()+r.slice(1); btn.dataset.rarity=r;
    btn.onclick=()=>applyFilter(btn);
    bar.appendChild(btn);
  });

  grid.before(bar);

  // Populate thumbs
  order.forEach(rarity=>{
    const files=data[rarity];
    if(!files||!files.length) return;
    files.forEach(fname=>{
      const path=`${rarity}/${fname}`;
      const img=document.createElement('img');
      img.className=`thumb rarity-${rarity}`;
      img.src=`/img/${folder}/${path}`;
      img.title=path;
      img.dataset.path=path;
      if(isKnife && RARITY_GLOW[rarity]) img.style.filter=RARITY_GLOW[rarity];
      img.onclick=()=>selectThumb(grid, img, key, path, scheduleGen);
      grid.appendChild(img);
    });
  });
}

function selectThumb(grid, img, key, path, cb){
  grid.querySelectorAll('.thumb').forEach(t=>t.classList.remove('selected'));
  img.classList.add('selected');
  sel[key]=path;
  if(cb) cb();
}

function selectRandom(gridId, key){
  const grid=document.getElementById(gridId);
  const thumbs=[...grid.querySelectorAll('.thumb')];
  if(!thumbs.length) return;
  grid.querySelectorAll('.thumb').forEach(t=>t.classList.remove('selected'));
  const pick=thumbs[Math.floor(Math.random()*thumbs.length)];
  pick.classList.add('selected');
  sel[key]=pick.dataset.path||pick.title;
}

function randomizeAll(){
  // Randomize all selections
  selectRandom('grid-body','body_file');
  selectRandom('grid-knife','knife_file');
  selectRandom('grid-offhand','offhand_file');
  selectRandom('grid-necklace','necklace_file');
  selectRandom('grid-eye-left','eye_left_file');
  selectRandom('grid-eye-right','eye_right_file');
  selectRandom('grid-mouth','mouth_file');
  // Randomize sliders
  document.getElementById('overlay_hue').value=Math.floor(Math.random()*360);
  document.getElementById('body_hue').value=Math.floor(Math.random()*360);
  document.getElementById('body_sat').value=40+Math.floor(Math.random()*50);
  document.getElementById('pin_count').value=Math.floor(Math.random()*4);
  ['overlay_hue','body_hue','body_sat','pin_count'].forEach(id=>{
    document.getElementById(id+'_v').textContent=document.getElementById(id).value;
  });
  updateSwatch(); updateBodySwatch();
  generate();
}

function scheduleGen(){
  clearTimeout(genTimer);
  genTimer=setTimeout(generate, 400);
}

function buildParams(){
  const bg_type=document.querySelector('input[name=bg_type]:checked').value;
  return {
    bg_type,
    bg_color: v('bg_color'),
    overlay_hue: parseInt(v('overlay_hue'))/360,
    overlay_sat: 0.7,
    overlay_val: 0.9,
    overlay_strength: parseInt(v('overlay_strength'))/100,
    body_file: sel.body_file,
    body_hue: parseInt(v('body_hue'))/360,
    body_sat: parseInt(v('body_sat'))/100,
    body_val: 0.85,
    knife_file: sel.knife_file,
    offhand_file: sel.offhand_file,
    necklace_file: sel.necklace_file,
    eye_left_file: sel.eye_left_file,
    eye_right_file: sel.eye_right_file,
    mouth_file: sel.mouth_file,
    pin_count: parseInt(v('pin_count')),
    hair_count: parseInt(v('hair_count')),
    hair_seed: parseInt(document.getElementById('hair_seed').value),
    hair_color: v('hair_color'),
    name: document.getElementById('name_input').value.trim(),
    preview_size: 800,
  };
}

async function generate(){
  if(isGenerating) return;
  isGenerating=true;
  document.getElementById('loading').classList.add('show');
  document.getElementById('status').textContent='generating…';
  const t0=performance.now();
  try{
    const res=await fetch('/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(buildParams())});
    const data=await res.json();
    document.getElementById('preview-img').src='data:image/png;base64,'+data.image;
    const ms=Math.round(performance.now()-t0);
    document.getElementById('status').textContent=`${ms}ms`;
  }catch(e){
    document.getElementById('status').textContent='error: '+e.message;
  }
  document.getElementById('loading').classList.remove('show');
  isGenerating=false;
}

async function saveHQ(){
  document.getElementById('status').textContent='saving 2048px…';
  const params={...buildParams(),preview_size:2048};
  const res=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(params)});
  const data=await res.json();
  document.getElementById('status').textContent='saved: '+data.filename;
}

// Init
loadItems().then(()=>{
  randomizeAll();
  document.getElementById('sec-body').classList.add('open');
});
</script>
</body>
</html>"""

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5050))
    print(f"http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
