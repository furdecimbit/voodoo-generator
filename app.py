import base64, io, random, math, colorsys
from pathlib import Path
from collections import deque

import numpy as np
from PIL import Image, ImageFilter, ImageDraw
from scipy.ndimage import binary_erosion
from flask import Flask, jsonify, request, send_file, render_template_string, Response

VOODOO = Path(__file__).parent
app = Flask(__name__)

HELIUS_API_KEY = "d9dba9ac-f923-4ed6-9a90-f389a71e9bcc"
COLLECTION_ADDRESS = "DFfnpWWfzTj4TEPQTZMSbpyg4JpbYzRjoTm4pM93xEdy"

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

def _place_pin(scene, solid, ex, ey, offset_x, offset_y, pin_files, edge_pts=None):
    """Place a single pin at body edge point (ex,ey) perpendicular to edge."""
    # ── Normal direction via local PCA of nearby edge points ──
    nx_v, ny_v = 1.0, 0.0
    if edge_pts is not None and len(edge_pts) >= 4:
        dists = (edge_pts[:,0].astype(float)-ey)**2 + (edge_pts[:,1].astype(float)-ex)**2
        radius = 20
        nearby_idx = np.where(dists < radius**2)[0]
        # Expand radius if too few points
        if len(nearby_idx) < 4:
            nearby_idx = np.argsort(dists)[:12]
        nearby = edge_pts[nearby_idx].astype(float)
        pts = nearby - nearby.mean(axis=0)
        _, _, vt = np.linalg.svd(pts, full_matrices=False)
        tangent = vt[0]  # principal axis = tangent along edge
        # Two possible normals (rotate tangent 90°)
        cand1 = np.array([-tangent[1],  tangent[0]])
        cand2 = np.array([ tangent[1], -tangent[0]])
        # Pick the one pointing outward (away from body centroid)
        cy_c, cx_c = float(np.mean(np.argwhere(solid)[:,0])), float(np.mean(np.argwhere(solid)[:,1]))
        out = np.array([ey - cy_c, ex - cx_c])
        normal = cand1 if np.dot(cand1, out) >= 0 else cand2
        ny_v, nx_v = float(normal[0]), float(normal[1])
        mag = math.sqrt(nx_v*nx_v + ny_v*ny_v)
        if mag > 1e-6:
            nx_v /= mag; ny_v /= mag
        else:
            nx_v, ny_v = 1.0, 0.0
    else:
        # Fallback: gradient of local solid patch
        r=10; y0,y1=max(0,ey-r),min(solid.shape[0],ey+r+1)
        x0,x1=max(0,ex-r),min(solid.shape[1],ex+r+1)
        patch=solid[y0:y1,x0:x1].astype(np.float32)
        gy=np.gradient(patch,axis=0); gx=np.gradient(patch,axis=1)
        ny_v=-float(gy[ey-y0,ex-x0]); nx_v=-float(gx[ey-y0,ex-x0])
        mag=math.sqrt(nx_v*nx_v+ny_v*ny_v)
        if mag<1e-6: return
        nx_v/=mag; ny_v/=mag

    # Pin points inward: angle from outward normal
    angle_deg = math.degrees(math.atan2(ny_v, nx_v)) - 90.0

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
    # 3× bigger than before (was //5, now //5*3)
    pin_img=pin_img.resize((max(1,pin_img.width*3//5),max(1,pin_img.height*3//5)),Image.LANCZOS)
    pw,ph=pin_img.size; L=max(pw,ph)
    embed_frac=0.42
    center_x=ex+offset_x+int(nx_v*L*(0.5-embed_frac))
    center_y=ey+offset_y+int(ny_v*L*(0.5-embed_frac))
    scene.paste(pin_img,(center_x-pw//2,center_y-ph//2),pin_img)

def draw_pins(scene, body_colored, offset_x, offset_y, n_pins=1, exclude_rects=None, explicit_positions=None):
    arr = np.array(body_colored)
    solid = arr[:,:,3]>128
    eroded = binary_erosion(solid)
    edge = solid & ~eroded
    edge_pts = np.argwhere(edge)
    pin_files=list((VOODOO/"pins").glob("*.png"))
    if not pin_files or len(edge_pts)==0: return

    if explicit_positions:
        for (sx_, sy_) in explicit_positions:
            bx = sx_ - offset_x; by_ = sy_ - offset_y
            dists = (edge_pts[:,0].astype(float)-by_)**2 + (edge_pts[:,1].astype(float)-bx)**2
            idx = int(np.argmin(dists))
            ey_n, ex_n = edge_pts[idx]
            _place_pin(scene, solid, ex_n, ey_n, offset_x, offset_y, pin_files, edge_pts)
        return

    if n_pins == 0: return
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
            hx=ex+offset_x+int(nx2*350*0.5); hy=ey+offset_y+int(ny2*350*0.5)
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
    body_h_total = solid.shape[0]
    foot_cutoff = int(body_h_total * 0.75)
    edge_pts = edge_pts[edge_pts[:,0] < foot_cutoff]
    if len(edge_pts) == 0: return
    chosen=edge_pts[np.random.choice(len(edge_pts),min(n_pins,len(edge_pts)),replace=False)]
    for (ey,ex) in chosen:
        _place_pin(scene, solid, ex, ey, offset_x, offset_y, pin_files, edge_pts)

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
    preview_size = int(params.get('preview_size', 800))
    W = H = preview_size
    _s = W / 2048

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

    # Scale body to fit canvas
    bw, bh = body_colored.size
    sc = min(W / bw, H / bh)
    if abs(sc - 1.0) > 0.01:
        body_colored = premult_resize(body_colored, int(bw*sc), int(bh*sc))

    lm = get_body_landmarks(body_colored)
    feet_target_y = int(H*(1-560/3125)) - int(150*_s)
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

    # Items — None means skip
    def load_item(folder, fname):
        if not fname: return None
        base = VOODOO/folder
        if fname != '__random__':
            return open_img(base/fname)
        files = list(base.glob("*.png")) + list(base.glob("*.PNG"))
        for r in RARITIES:
            files += list((base/r).glob("*.png")) + list((base/r).glob("*.PNG"))
        return open_img(random.choice(files)) if files else None

    knife_img   = load_item("knife",    params.get('knife_file'))
    offhand_img = load_item("offhand",  params.get('offhand_file'))
    neck_img    = load_item("necklace", params.get('necklace_file'))
    eye1_img    = load_item("eyes",     params.get('eye_left_file'))
    eye2_img    = load_item("eyes",     params.get('eye_right_file'))
    mouth_img   = load_item("mouths",   params.get('mouth_file'))

    neck_size = int(lm['head_r']*0.44)
    neck_cx_final = sx(lm['neck_cx'])+int(neck_size*0.25)-int(17*_s)
    neck_cy_final = sy(lm['neck_y'])+int(neck_size*0.3)+neck_size//2+int(20*_s)

    right_x=max(lm['rhand_x'],lm['lhand_x'])
    right_y=lm['rhand_y'] if lm['rhand_x']>=lm['lhand_x'] else lm['lhand_y']
    left_x =min(lm['rhand_x'],lm['lhand_x'])
    left_y =lm['lhand_y'] if lm['rhand_x']>=lm['lhand_x'] else lm['rhand_y']

    knife_size   = int(bh * 0.312)
    offhand_size = int(bh * 0.234)
    mouth_size   = int(lm['head_r'] * 0.90)
    eye_size     = int(lm['eye_size']*0.6*1.30*1.15*1.10)
    neck_new_w   = int(neck_img.size[0]*0.80*_s) if neck_img else 0
    neck_new_h   = int(neck_img.size[1]*0.80*_s) if neck_img else 0

    knife_cx  = sx(right_x); knife_cy  = sy(right_y)-int(180*_s)
    offhand_cx= sx(left_x)+int(70*_s); offhand_cy= sy(left_y)-int(160*_s)
    mouth_cx  = sx(lm['head_cx'])+int(10*_s)
    mouth_cy  = sy(lm['eye_y'])+eye_size//2+int(100*_s)
    eye1x     = sx(lm['head_cx'])-lm['eye_gap']+int(20*_s); eye1y=sy(lm['eye_y'])+int(20*_s)
    eye2x     = sx(lm['head_cx'])+lm['eye_gap']+int(5*_s);  eye2y=sy(lm['eye_y'])+int(10*_s)
    mw,mh     = mouth_img.size if mouth_img else (0,0)

    hand_pad=int(120*_s); foot_pad=int(150*_s)
    item_rects=[
        (sx(right_x)-hand_pad,sy(right_y)-hand_pad,sx(right_x)+hand_pad,sy(right_y)+hand_pad),
        (sx(left_x)-hand_pad, sy(left_y)-hand_pad, sx(left_x)+hand_pad, sy(left_y)+hand_pad),
        (0,sy(lm['body_bottom'])-foot_pad,W,sy(lm['body_bottom'])+foot_pad),
    ]

    explicit_pins = params.get('pins', [])
    if explicit_pins:
        W_cur = W
        positions = [(int(p['x']*W_cur), int(p['y']*W_cur)) for p in explicit_pins]
        draw_pins(scene, body_colored, offset_x, offset_y, explicit_positions=positions)
    else:
        n_pins = int(params.get('pin_count', 0))
        if n_pins > 0:
            draw_pins(scene, body_colored, offset_x, offset_y, n_pins=n_pins, exclude_rects=item_rects)
    scene.paste(body_colored,(offset_x,offset_y),body_colored)

    # Knife
    if knife_img:
        knife_file  = params.get('knife_file','')
        knife_rarity= knife_file.split('/')[0] if '/' in knife_file else 'common'
        glow_colors = {'rare':(240,200,40),'legendary':(60,220,255),'ultimate':(255,100,200)}
        knife_img   = premult_resize_sq(knife_img, knife_size)
        if knife_rarity in glow_colors:
            gc=glow_colors[knife_rarity]; kw2,kh2=knife_img.size; pad=int(60*_s)
            glow_surf=Image.new("RGBA",(kw2+pad*2,kh2+pad*2),(0,0,0,0))
            glow_surf.paste(knife_img,(pad,pad),knife_img)
            mask=glow_surf.split()[3]
            for radius,alpha in [(int(25*_s),255),(int(15*_s),255),(int(8*_s),255),(3,255)]:
                blurred=mask.filter(ImageFilter.GaussianBlur(max(1,radius)))
                ba=np.clip(np.array(blurred).astype(np.float32)*1.6,0,255).astype(np.uint8)
                cl=Image.new("RGBA",glow_surf.size,gc+(alpha,)); gl=Image.new("RGBA",glow_surf.size,(0,0,0,0))
                gl.paste(cl,mask=Image.fromarray(ba,'L'))
                scene.alpha_composite(gl,(knife_cx-kw2//2-pad,knife_cy-kh2//2-pad))
        paste_centered(scene,knife_img,knife_cx,knife_cy)

    if offhand_img:
        offhand_img=premult_resize_sq(offhand_img,offhand_size)
        paste_centered(scene,offhand_img,offhand_cx,offhand_cy)

    draw2=ImageDraw.Draw(scene)
    body_arr=np.array(body_colored); solid_body=body_arr[:,:,3]>128
    neck_row=min(lm['neck_y'],body_arr.shape[0]-1)
    cols=np.where(solid_body[neck_row,:])[0]
    lx2=int(cols[0]) if len(cols) else lm['neck_cx']-lm['head_r']
    rx2=int(cols[-1]) if len(cols) else lm['neck_cx']+lm['head_r']
    rope_w=max(4,neck_size//15)
    if neck_img:
     for start_x in [lx2, rx2]:
        sx0=start_x+offset_x; sy0=lm['neck_y']+offset_y
        pts=[]
        for t in [i/30 for i in range(31)]:
            cx_ctrl=(sx0+neck_cx_final)/2; cy_ctrl=(sy0+neck_cy_final)/2+neck_size*0.15
            bx=(1-t)**2*sx0+2*(1-t)*t*cx_ctrl+t**2*neck_cx_final
            by=(1-t)**2*sy0+2*(1-t)*t*cy_ctrl+t**2*neck_cy_final
            pts.append((int(bx),int(by)))
        draw2.line(pts,fill=(10,8,6,255),width=rope_w+4)
        draw2.line(pts,fill=(30,20,10,230),width=rope_w)

    if neck_img:
        neck_img_r=neck_img.resize((neck_new_w,neck_new_h),Image.LANCZOS)
        scene.paste(neck_img_r,(neck_cx_final-neck_new_w//2,neck_cy_final-neck_new_h//2),neck_img_r)

    if eye1_img:
        eye1_r=premult_resize_sq(eye1_img,eye_size)
        paste_with_shadow(scene,eye1_r,eye1x,eye1y)
    if eye2_img:
        eye2_r=premult_resize_sq(eye2_img,eye_size)
        paste_with_shadow(scene,eye2_r,eye2x,eye2y)
    if mouth_img and mw>0:
        mouth_img=premult_resize(mouth_img,int(mw*mouth_size/max(mw,mh)),int(mh*mouth_size/max(mw,mh)))
        paste_centered(scene,mouth_img,mouth_cx,mouth_cy)


    # Name text: y range 1800-1900, curved arc (center dips down), bloodcrowc font
    name = params.get('name', '').strip()
    if name:
        from PIL import ImageFont
        FONT_PATH = str(VOODOO / "bloodcrowc.ttf")
        y_center = int(H * 1870 / 2048) + 5
        max_w = int(W * 0.80)

        # Auto-fit font size — cap at 110px so it stays smaller
        lo, hi = 20, max(20, int(110 * H / 2048))
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
            arc_depth = 12   # how many px the center drops below edges
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
    """Returns {rarity: [filenames]} for categories with rarity subfolders. Skips hide/ subfolders."""
    result = {}
    for r in RARITIES:
        p = VOODOO/base/r
        if not p.exists(): continue
        files = []
        for e in exts: files += sorted([f.name for f in p.glob(f'*.{e}') if f.parent.name != 'hide'])
        if files: result[r] = files
    return result

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/list')
def list_items():
    pins_dir = VOODOO / 'pins'
    pin_files = sorted([f.name for f in pins_dir.glob('*.png')], key=lambda x: int(x.split('.')[0]) if x.split('.')[0].isdigit() else 999) if pins_dir.exists() else []
    return jsonify({
        'body':     list_folder_rarity('body', ('PNG','png')),
        'knife':    list_folder_rarity('knife'),
        'offhand':  list_folder_flat('offhand'),
        'necklace': list_folder_rarity('necklace'),
        'eyes':     list_folder_rarity('eyes'),
        'mouths':   list_folder_flat('mouths'),
        'pins':     pin_files,
    })

@app.route('/img/<path:rel_path>')
def serve_img(rel_path):
    p = VOODOO/rel_path
    if p.suffix.lower() == '.mp4':
        range_header = request.headers.get('Range')
        size = p.stat().st_size
        if range_header:
            byte1, byte2 = 0, None
            m = __import__('re').search(r'(\d+)-(\d*)', range_header)
            if m:
                byte1 = int(m.group(1))
                byte2 = int(m.group(2)) if m.group(2) else size - 1
            length = byte2 - byte1 + 1
            with open(p, 'rb') as f:
                f.seek(byte1)
                data = f.read(length)
            rv = Response(data, 206, mimetype='video/mp4')
            rv.headers['Content-Range'] = f'bytes {byte1}-{byte2}/{size}'
            rv.headers['Accept-Ranges'] = 'bytes'
            return rv
        return send_file(str(p), mimetype='video/mp4')
    return send_file(str(p))

@app.route('/generate', methods=['POST'])
def generate():
    params = request.json or {}
    scene = compose(params)
    buf = io.BytesIO()
    scene.save(buf, 'PNG', optimize=False)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return jsonify({'image': b64})

@app.route('/check_holder', methods=['POST'])
def check_holder():
    import requests as req
    wallet = (request.json or {}).get('wallet', '')
    if not wallet:
        return jsonify({'holder': False})
    try:
        url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
        payload = {
            "jsonrpc": "2.0", "id": "1",
            "method": "getAssetsByOwner",
            "params": {
                "ownerAddress": wallet,
                "page": 1, "limit": 1000,
                "displayOptions": {"showCollectionMetadata": False}
            }
        }
        r = req.post(url, json=payload, timeout=12)
        items = r.json().get('result', {}).get('items', [])
        for asset in items:
            for g in asset.get('grouping', []):
                if g.get('group_value') == COLLECTION_ADDRESS:
                    return jsonify({'holder': True})
        return jsonify({'holder': False})
    except Exception as e:
        return jsonify({'holder': False, 'error': str(e)})

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
    height:100vh;overflow:hidden;
    position:relative;
  }
  #bg-video{
    position:fixed;top:0;left:0;width:100%;height:100%;
    object-fit:cover;z-index:-1;opacity:0.45;pointer-events:none;
  }

  /* ── SIDEBAR ── */
  /* desktop: body is a grid — left col = sidebar+sidebar-content, right col = preview */
  body{
    display:grid;
    grid-template-columns:460px 1fr;
    grid-template-rows:auto 1fr;
    grid-template-areas:
      "sidebar  preview"
      "items    preview";
  }
  #sidebar{
    grid-area:sidebar;
    background:linear-gradient(180deg,#3d2b0f 0%,#2c1e0a 40%,#1e1508 100%);
    display:flex;flex-direction:column;gap:0;flex-shrink:0;
    border-right:3px solid #7a5520;
    box-shadow:inset -6px 0 24px #00000099,inset 2px 0 8px #c8901410;
  }
  #sidebar-content{
    grid-area:items;
    background:linear-gradient(180deg,#1e1508 0%,#141008 100%);
    overflow-y:auto;display:flex;flex-direction:column;gap:0;
    border-right:3px solid #7a5520;
    box-shadow:inset -6px 0 24px #00000099,4px 0 32px #00000077;
  }
  #sidebar-content::-webkit-scrollbar{width:6px}
  #sidebar-content::-webkit-scrollbar-track{background:#140e04}
  #sidebar-content::-webkit-scrollbar-thumb{background:#7a5520;border-radius:3px}
  #preview-area{grid-area:preview}

  /* title */
  #sidebar-title{
    padding:20px 18px 6px;
    font-family:'Bloodcrow',serif;
    font-size:46px;
    color:#e8c060;
    letter-spacing:.06em;
    text-align:center;
    background:linear-gradient(180deg,#3d2b0f,#2c1e0a);
    position:relative;
    text-shadow:0 0 28px #e8c06099, 0 2px 6px #000;
    animation:titlePulse 3.5s ease-in-out infinite;
    line-height:1;
  }
  #sidebar-subtitle{
    display:flex;align-items:center;justify-content:center;gap:8px;
    padding:4px 18px 16px;
    background:linear-gradient(180deg,#2c1e0a,#251a08);
    border-bottom:2px solid #7a5520;
    position:relative;
  }
  #sidebar-subtitle::after{
    content:'';position:absolute;bottom:-1px;left:10%;right:10%;
    height:1px;background:linear-gradient(90deg,transparent,#c8a04088,transparent);
  }
  #sidebar-subtitle img{
    height:1em;width:auto;object-fit:contain;
    filter:drop-shadow(0 0 6px #e8c06088);
  }
  #sidebar-subtitle span{
    font-family:'Bloodcrow',serif;
    font-size:14px;letter-spacing:.12em;
    color:#c8a050;text-transform:uppercase;
    text-shadow:0 0 10px #c8a05055;
  }
  @keyframes titlePulse{
    0%,100%{text-shadow:0 0 20px #e8c06077,0 2px 6px #000}
    50%{text-shadow:0 0 44px #e8c060bb,0 0 90px #e8c06033,0 2px 6px #000}
  }

  /* wallet bar */
  #wallet-bar{
    padding:8px 16px 12px;
    display:flex;align-items:center;gap:10px;
    border-bottom:1px solid #3a2810;
  }
  #btn-wallet{
    padding:7px 16px;
    font-family:'Bloodcrow',serif;font-size:13px;letter-spacing:.06em;
    background:linear-gradient(180deg,#2a1e10,#1a1208);
    border:1px solid #7a5520;border-radius:4px;
    color:#c8a050;cursor:pointer;
    transition:background .2s,box-shadow .2s;
    white-space:nowrap;
  }
  #btn-wallet:hover{background:linear-gradient(180deg,#3a2810,#2a1a08);box-shadow:0 0 12px #c8a05033}
  #btn-wallet.connected{border-color:#307030;color:#70cc70;background:linear-gradient(180deg,#1a2e1a,#101e10)}
  #wallet-status{display:flex;align-items:center;gap:8px;flex:1;min-width:0}
  #wallet-addr{
    font-family:'Bloodcrow',serif;font-size:12px;letter-spacing:.04em;
    color:#a09070;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  }
  #wallet-badge{
    font-family:'Bloodcrow',serif;font-size:12px;letter-spacing:.06em;
    padding:2px 8px;border-radius:3px;white-space:nowrap;flex-shrink:0;
  }
  #wallet-badge.holder{background:#1a3a1a;color:#70cc70;border:1px solid #308030}
  #wallet-badge.not-holder{background:#2a0a0a;color:#cc4040;border:1px solid #602020}

  /* sections */
  .section{
    border-bottom:1px solid #4a3210;
  }
  .section-header{
    padding:13px 18px;
    font-family:'Bloodcrow',serif;
    font-size:19px;
    letter-spacing:.08em;
    color:#c49a50;
    cursor:pointer;
    display:flex;align-items:center;justify-content:space-between;
    user-select:none;
    transition:color .2s,background .2s;
    text-transform:uppercase;
  }
  .section-header:hover{
    color:#f0d070;
    background:linear-gradient(90deg,#4a3010cc,transparent);
    text-shadow:0 0 14px #f0d07055;
  }
  .section.open .section-header{
    color:#f0d070;
    background:linear-gradient(90deg,#4a3010cc,transparent);
    text-shadow:0 0 12px #f0d07066;
    border-bottom:1px solid #6a4a18;
  }
  .section-body{
    padding:0 14px;
    background:linear-gradient(180deg,#2a1e0c 0%,#1e1508 20%,#181208 60%,#141008 100%);
    max-height:0;overflow:hidden;
    transition:max-height .4s cubic-bezier(.4,0,.2,1),padding .4s;
  }
  .section.open .section-body{max-height:2000px;padding:12px 14px}
  .section-header .arrow{font-size:14px;transition:transform .25s;opacity:.5}
  .section.open .section-header .arrow{transform:rotate(90deg)}

  /* thumb grid */
  .thumb-grid{display:flex;flex-wrap:wrap;gap:6px}
  #grid-mouth .thumb{background:#e8e4dc}
  .thumb{
    width:54px;height:54px;
    object-fit:contain;
    background:#0e0b07;
    border:2px solid #3a280e;
    border-radius:6px;
    cursor:pointer;
    transition:border-color .15s,transform .12s,box-shadow .15s;
    box-shadow:inset 0 1px 4px #00000088;
  }
  .thumb:hover{border-color:#9a7030;transform:scale(1.08);box-shadow:0 0 12px #c8a03844,inset 0 1px 4px #00000088}
  .thumb.selected{border-color:#e8c050;background:#1e1508;box-shadow:0 0 16px #e8c05066,inset 0 1px 4px #00000066}

  /* rarity borders */
  .thumb.rarity-common   {border-color:#4a4a3a}
  .thumb.rarity-rare     {border-color:#9a7808}
  .thumb.rarity-legendary{border-color:#2a8aaa}
  .thumb.rarity-ultimate {border-color:#aa3a80}
  .thumb.rarity-common.selected  {border-color:#b0b090;box-shadow:0 0 12px #b0b09066}
  .thumb.rarity-rare.selected    {border-color:#f0c020;box-shadow:0 0 14px #f0c02066}
  .thumb.rarity-legendary.selected{border-color:#50d0f0;box-shadow:0 0 14px #50d0f066}
  .thumb.rarity-ultimate.selected {border-color:#f060b8;box-shadow:0 0 14px #f060b866}

  .rarity-label{font-family:'Bloodcrow',serif;font-size:16px;letter-spacing:.06em;margin:10px 0 5px;padding:2px 0;text-transform:uppercase}

  /* rarity filter bar */
  .rarity-filter{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px}
  .rf-btn{
    padding:3px 11px;
    border:1px solid #3a2c12;
    border-radius:3px;
    background:linear-gradient(180deg,#221808,#1a1205);
    font-family:'Bloodcrow',serif;
    font-size:12px;
    letter-spacing:.05em;
    color:#7a6040;
    cursor:pointer;
    text-transform:uppercase;
    transition:background .15s,color .15s,border-color .15s,box-shadow .15s;
  }
  .rf-btn:hover{color:#e8c060;border-color:#7a5820;background:linear-gradient(180deg,#2e2010,#221808)}
  .rf-btn.active{
    background:linear-gradient(180deg,#5a3c10,#3a2808);
    color:#f0d060;border-color:#c0900a;
    box-shadow:0 0 8px #c0900a44;
  }
  .rf-btn.rf-common.active  {color:#c8c8a8;border-color:#a0a080;background:linear-gradient(180deg,#2a2a20,#1e1e18);box-shadow:0 0 8px #a0a08044}
  .rf-btn.rf-rare.active    {color:#f0d020;border-color:#c09008;background:linear-gradient(180deg,#2e2400,#221a00);box-shadow:0 0 8px #f0d02055}
  .rf-btn.rf-legendary.active{color:#60e0ff;border-color:#30b0d8;background:linear-gradient(180deg,#001e2e,#001422);box-shadow:0 0 8px #60e0ff44}
  .rf-btn.rf-ultimate.active {color:#ff80d8;border-color:#c040a0;background:linear-gradient(180deg,#280018,#1a0010);box-shadow:0 0 8px #ff80d855}
  .rarity-label.common  {color:#a0a080}
  .rarity-label.rare    {color:#c8a010}
  .rarity-label.legendary{color:#40c0e0}
  .rarity-label.ultimate{color:#e050b0}

  /* sub-labels */
  .sub-label{
    font-family:'Bloodcrow',serif;font-size:15px;letter-spacing:.06em;
    color:#7a5830;margin:10px 0 5px;text-transform:uppercase;
  }

  /* sub-accordion */
  .sub-section{border:1px solid #2e1e08;border-radius:4px;margin-bottom:7px;overflow:hidden}
  .sub-section-header{
    padding:9px 12px;
    font-family:'Bloodcrow',serif;font-size:15px;letter-spacing:.05em;
    color:#8a6840;cursor:pointer;
    display:flex;align-items:center;justify-content:space-between;
    background:linear-gradient(180deg,#1a1208,#120e06);
    user-select:none;transition:color .15s,background .15s;
    text-transform:uppercase;
  }
  .sub-section-header:hover{color:#e8c060;background:linear-gradient(180deg,#2a1e0c,#1e1608)}
  .sub-section.open .sub-section-header{color:#e8c060;background:linear-gradient(180deg,#2e2010,#1e1608)}
  .sub-section-body{
    max-height:0;overflow:hidden;padding:0 10px;
    background:linear-gradient(180deg,#221808,#141008);
    transition:max-height .3s cubic-bezier(.4,0,.2,1),padding .3s;
  }
  .sub-section.open .sub-section-body{max-height:1200px;padding:9px 10px}
  .sub-section-header .sarrow{font-size:12px;transition:transform .2s;opacity:.5}
  .sub-section.open .sub-section-header .sarrow{transform:rotate(90deg)}

  /* sliders */
  .slider-row{display:flex;align-items:center;gap:10px;margin-bottom:10px}
  .slider-row label{
    width:140px;font-family:'Bloodcrow',serif;font-size:15px;
    color:#9a8868;flex-shrink:0;letter-spacing:.04em;
  }
  .slider-row input[type=range]{flex:1;accent-color:#d4a84b;height:4px;cursor:pointer}
  .slider-row .val{width:42px;font-size:15px;color:#c0a060;text-align:right}

  .hue-preview{width:26px;height:26px;border-radius:4px;border:1px solid #3a2818;flex-shrink:0}

  /* radio */
  .radio-row{display:flex;gap:14px;margin-bottom:12px}
  .radio-row label{
    font-family:'Bloodcrow',serif;font-size:15px;letter-spacing:.04em;
    cursor:pointer;display:flex;align-items:center;gap:5px;color:#a09070;
  }
  .radio-row label:hover{color:#e8c060}

  /* action buttons */
  #btn-area{
    padding:14px 0 0 0;
    display:flex;flex-direction:row;gap:14px;justify-content:center;width:100%;
  }
  button{
    padding:12px 22px;border:none;border-radius:4px;
    font-family:'Bloodcrow',serif;font-size:19px;letter-spacing:.05em;
    cursor:pointer;transition:opacity .15s,box-shadow .15s,transform .1s;
    text-transform:uppercase;
  }
  #btn-rand{
    background:linear-gradient(180deg,#5a3c10,#3a2208);
    color:#f0d060;
    border:1px solid #c0900a;
    box-shadow:0 2px 12px #00000077,0 0 8px #c0900a22;
  }
  #btn-rand:hover{box-shadow:0 2px 22px #f0d06055,0 0 16px #c0900a44;transform:translateY(-1px)}
  #btn-save{
    background:linear-gradient(180deg,#1a3020,#0e1e14);
    color:#70cc70;border:1px solid #308030;
    box-shadow:0 2px 12px #00000077;
  }
  #btn-save:hover{box-shadow:0 2px 18px #70cc7044;transform:translateY(-1px)}
  #btn-clear{
    background:linear-gradient(180deg,#2a1818,#180e0e);
    color:#886050;border:1px solid #4a2820;
    box-shadow:0 2px 10px #00000066;
  }
  #btn-clear:hover{color:#cc8060;border-color:#883020;box-shadow:0 2px 14px #cc806033}
  button:active{opacity:.6;transform:translateY(0)}

  /* selected items panel */
  #selected-panel{
    margin-top:10px;display:flex;flex-wrap:wrap;gap:6px;justify-content:center;min-height:0;
  }
  .sel-tag{
    font-family:'Bloodcrow',serif;font-size:17px;letter-spacing:.04em;text-transform:uppercase;
    color:#e8c878;background:linear-gradient(180deg,#2e1e08,#1e1405);
    border:1px solid #7a5518;border-radius:3px;padding:3px 12px;
    animation:tagIn .25s ease;box-shadow:0 0 8px #e8c87822;
  }
  @keyframes tagIn{from{opacity:0;transform:scale(.85) translateY(4px)}to{opacity:1;transform:none}}

  /* thumb wrapper for badges */
  .thumb-wrap{position:relative;display:inline-block;cursor:pointer}
  .thumb-wrap .thumb{cursor:pointer}
  .thumb-badge{
    position:absolute;top:-5px;right:-5px;
    width:16px;height:16px;border-radius:50%;
    font-size:10px;font-weight:bold;
    display:none;align-items:center;justify-content:center;
    pointer-events:none;z-index:2;
    box-shadow:0 0 4px #000a;
  }
  .thumb-wrap.staged .thumb-badge{
    display:flex;background:#e8c050;color:#1a0e00;content:'◆';
  }
  .thumb-wrap.equipped .thumb-badge{
    display:flex;background:#40bb40;color:#001a00;
  }
  .thumb-wrap.staged .thumb{
    border-color:#e8c050 !important;
    animation:stagedPulse 1.8s ease-in-out infinite;
  }
  .thumb-wrap.equipped .thumb{
    border-color:#40bb40 !important;
    box-shadow:0 0 10px #40bb4055 !important;
  }
  .thumb-wrap.staged.equipped .thumb{
    border-color:#e8c050 !important;
    animation:stagedPulse 1.8s ease-in-out infinite;
  }
  @keyframes stagedPulse{
    0%,100%{box-shadow:0 0 6px #e8c05066}
    50%{box-shadow:0 0 16px #e8c050cc,0 0 30px #e8c05044}
  }

  /* toast notifications */
  #toast-area{
    position:fixed;bottom:32px;right:32px;
    display:flex;flex-direction:column;gap:8px;
    z-index:200;pointer-events:none;
  }
  .toast{
    background:linear-gradient(180deg,#2e1e08,#1a1004);
    border:1px solid #c8a040;border-radius:3px;
    padding:8px 18px;
    font-family:'Bloodcrow',serif;font-size:15px;letter-spacing:.05em;
    color:#e8c878;text-shadow:0 0 8px #e8c87844;
    animation:toastIn .3s ease, toastOut .4s ease 2.4s forwards;
    white-space:nowrap;
  }
  .toast.equipped-toast{border-color:#40bb40;color:#90ee90}
  @keyframes toastIn{from{opacity:0;transform:translateX(50px)}to{opacity:1;transform:none}}
  @keyframes toastOut{to{opacity:0;transform:translateX(50px)}}

  /* preview area */
  #preview-area{
    flex:1;display:flex;flex-direction:column;
    align-items:center;justify-content:flex-start;
    padding:28px 24px 20px;background:transparent;position:relative;
  }
  #preview-wrap{position:relative;display:inline-block}
  #preview-img{
    max-width:100%;max-height:calc(100vh - 140px);
    border-radius:8px;
    box-shadow:0 8px 60px #000e,0 0 80px #c8803a14;
    display:block;
    border:1px solid #4a3010;
  }
  /* pin drop overlay */
  #pin-overlay{
    position:absolute;inset:0;
    pointer-events:auto;
    border-radius:8px;
    z-index:5;
  }
  #pin-overlay.drop-active{
    outline:2px dashed #e8c05088;
    background:rgba(232,192,80,0.04);
  }
  .placed-pin{
    position:absolute;
    width:32px;height:32px;
    transform:translate(-50%,-50%);
    pointer-events:auto;
    cursor:pointer;
    filter:drop-shadow(0 0 3px #000a);
    transition:filter .15s;
  }
  .placed-pin:hover{filter:drop-shadow(0 0 6px #ff3020bb)}
  .placed-pin .pin-remove{
    position:absolute;top:-7px;right:-7px;
    width:14px;height:14px;border-radius:50%;
    background:#c01010;color:#fff;
    font-size:9px;display:none;align-items:center;justify-content:center;
    cursor:pointer;border:1px solid #ff4040;
  }
  .placed-pin:hover .pin-remove{display:flex}

  /* pending indicator above bewitch */
  #pending-indicator{
    font-family:'Bloodcrow',serif;font-size:14px;letter-spacing:.06em;
    color:#e8c050;text-align:center;min-height:22px;
    text-transform:uppercase;
    animation:pendingPulse 1.5s ease-in-out infinite;
    opacity:0;transition:opacity .3s;
  }
  #pending-indicator.active{opacity:1}
  @keyframes pendingPulse{
    0%,100%{text-shadow:0 0 6px #e8c05066}
    50%{text-shadow:0 0 18px #e8c050cc,0 0 32px #e8c05044}
  }
  /* bewitch pulse when pending */
  #btn-curse.has-pending{
    animation:cursePulse 1.8s ease-in-out infinite;
  }
  @keyframes cursePulse{
    0%,100%{box-shadow:0 2px 14px #00000088,0 0 10px #a0201033}
    50%{box-shadow:0 2px 26px #ff503088,0 0 28px #ff503066;text-shadow:0 0 14px #ff5030cc}
  }

  /* pin drag source */
  .pin-drag-thumb{
    width:44px;height:44px;object-fit:contain;
    background:#0e0b07;border:2px solid #3a280e;border-radius:6px;
    cursor:grab;transition:border-color .15s,transform .12s;
    box-shadow:inset 0 1px 4px #00000088;
  }
  .pin-drag-thumb:hover{border-color:#9a7030;transform:scale(1.1)}
  .pin-drag-thumb:active{cursor:grabbing}
  .pin-drag-thumb.dragging{opacity:.5}
  #pin-counter{
    font-family:'Bloodcrow',serif;font-size:13px;color:#a09060;letter-spacing:.05em;
    margin-bottom:8px;
  }
  #pin-clear{
    padding:4px 14px;border:1px solid #5a2010;border-radius:3px;
    background:linear-gradient(180deg,#2a1008,#1a0a04);
    font-family:'Bloodcrow',serif;font-size:13px;color:#c06040;
    cursor:pointer;letter-spacing:.04em;margin-top:6px;
    transition:border-color .15s,color .15s;
  }
  #pin-clear:hover{border-color:#c04020;color:#ff6040}
  #loading{
    position:absolute;inset:0;
    background:#080608cc;
    display:none;align-items:center;justify-content:center;
    flex-direction:column;gap:16px;z-index:10;
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
    font-family:'Bloodcrow',serif;font-size:18px;
    color:#d4a84b;letter-spacing:.1em;text-shadow:0 0 12px #d4a84b88;
  }

  /* ── ritual veil ── */
  #ritual-veil{
    position:absolute;inset:0;pointer-events:none;
    display:flex;align-items:center;justify-content:center;
    z-index:20;opacity:0;
  }
  #ritual-veil.active{pointer-events:auto}
  #ritual-veil .veil-bg{
    position:absolute;inset:0;
    background:radial-gradient(ellipse at 50% 50%,#2a000088 0%,#10000099 50%,#000000bb 100%);
  }

  /* bewitch image */
  #bewitch-img{
    position:absolute;
    width:min(60vw,460px);height:min(60vw,460px);
    object-fit:contain;
    transform-origin:center;
    opacity:0;
  }
  #ritual-veil.active #bewitch-img{
    animation:bewitchSpin 1.4s linear forwards, bewitchFade 1.4s ease forwards;
  }
  @keyframes bewitchSpin{
    0%  {transform:scale(0.05) rotate(0deg)}
    8%  {transform:scale(1.2) rotate(28.8deg)}
    85% {transform:scale(1.1) rotate(306deg)}
    100%{transform:scale(1.8) rotate(360deg)}
  }
  @keyframes bewitchFade{
    0%  {opacity:0;filter:brightness(20) saturate(0) drop-shadow(0 0 0px #ff0000)}
    8%  {opacity:1;filter:brightness(5) drop-shadow(0 0 80px #ff0000) drop-shadow(0 0 160px #ff000088)}
    30% {opacity:1;filter:brightness(2.5) drop-shadow(0 0 60px #ff3010cc) drop-shadow(0 0 120px #ff100077)}
    75% {opacity:1;filter:brightness(7) saturate(2) drop-shadow(0 0 100px #ff0000) drop-shadow(0 0 200px #ff0000aa)}
    88% {opacity:.5;filter:brightness(14) saturate(0) drop-shadow(0 0 120px #ffffff)}
    100%{opacity:0;filter:brightness(20) drop-shadow(0 0 80px #ff0000)}
  }

  /* explosion rings */
  .glow-ring{
    position:absolute;border-radius:50%;
    width:8px;height:8px;pointer-events:none;opacity:0;
  }
  #ritual-veil.active .glow-ring:nth-child(2){
    border:5px solid #ff1000;
    box-shadow:0 0 30px 14px #ff100099,0 0 60px 20px #ff000055;
    animation:explodeRing .7s cubic-bezier(0,.5,.3,1) forwards;
  }
  #ritual-veil.active .glow-ring:nth-child(3){
    border:4px solid #ff5010;
    box-shadow:0 0 22px 10px #ff501088,0 0 50px 16px #ff200044;
    animation:explodeRing .8s cubic-bezier(0,.5,.3,1) .08s forwards;
  }
  #ritual-veil.active .glow-ring:nth-child(4){
    border:3px solid #ffbb30;
    box-shadow:0 0 16px 8px #ffbb3077,0 0 40px 14px #ff600033;
    animation:explodeRing .9s cubic-bezier(0,.5,.3,1) .18s forwards;
  }
  @keyframes explodeRing{
    0%  {opacity:1;transform:scale(1)}
    30% {opacity:1;transform:scale(28)}
    70% {opacity:.6;transform:scale(55)}
    100%{opacity:0;transform:scale(80)}
  }

  /* flash burst at moment of impact */
  #ritual-veil::after{
    content:'';position:absolute;inset:0;border-radius:inherit;
    background:radial-gradient(circle at 50% 50%,#ff200066 0%,transparent 70%);
    opacity:0;pointer-events:none;
  }
  #ritual-veil.active::after{animation:flashBurst .5s ease-out .07s forwards}
  @keyframes flashBurst{
    0%  {opacity:0;transform:scale(0.2)}
    20% {opacity:1;transform:scale(1)}
    100%{opacity:0;transform:scale(1.8)}
  }

  /* veil bg */
  #ritual-veil .veil-bg{opacity:0}
  #ritual-veil.active .veil-bg{animation:veilBgAnim 1.4s ease forwards}
  @keyframes veilBgAnim{
    0%  {opacity:0}
    8%  {opacity:1}
    70% {opacity:1}
    100%{opacity:0}
  }

  #ritual-veil.revealing{animation:veilReveal .3s ease-out forwards}
  @keyframes veilReveal{0%{opacity:1}100%{opacity:0}}

  #preview-img.curse-reveal{animation:imgReveal .7s ease-out forwards}
  @keyframes imgReveal{
    0%  {opacity:0;filter:brightness(3) saturate(0)}
    100%{opacity:1;filter:brightness(1) saturate(1)}
  }

  /* CURSE button */
  #btn-curse{
    background:linear-gradient(180deg,#3a0808,#1e0404);
    color:#ff5030;border:1px solid #a02010;
    box-shadow:0 2px 14px #00000088,0 0 10px #a0201033;
    letter-spacing:.08em;
  }
  #btn-curse:hover{
    box-shadow:0 2px 26px #ff503066,0 0 20px #ff503044;
    transform:translateY(-1px);
    text-shadow:0 0 12px #ff5030bb;
  }

  /* ── staged item panel (bottom-right fixed) ── */
  #staged-panel{
    position:fixed;bottom:28px;right:28px;
    width:260px;
    background:linear-gradient(160deg,#3a0808,#1a0404);
    border:3px solid #7a1008;
    border-radius:6px;
    padding:14px 16px 12px;
    display:none;
    flex-direction:column;gap:10px;
    z-index:150;
    box-shadow:0 4px 32px #000c,0 0 20px #c8201022;
    animation:panelSlideIn .3s ease;
    cursor:pointer;
    user-select:none;
    overflow:visible;
  }
  #staged-panel:hover{background:linear-gradient(160deg,#4a0a0a,#220606);box-shadow:0 4px 40px #000e,0 0 30px #ff302044}
  #staged-panel:active{transform:scale(.98)}
  #staged-panel.visible{display:flex}
  @keyframes panelSlideIn{from{opacity:0;transform:translateX(30px)}to{opacity:1;transform:none}}
  /* SVG traveling dot border */
  #border-glow-svg{
    position:absolute;inset:-4px;
    width:calc(100% + 8px);height:calc(100% + 8px);
    pointer-events:none;overflow:visible;
  }
  #bgr{
    fill:none;stroke:#ff4018;stroke-width:4;stroke-linecap:round;
    stroke-dasharray:40 9999;
    animation:travelBorder 1.2s linear infinite;
    filter:drop-shadow(0 0 8px #ff4018) drop-shadow(0 0 18px #ff2008) drop-shadow(0 0 30px #ff000066);
  }
  @keyframes travelBorder{to{stroke-dashoffset:var(--perim,-760)}}
  .staged-item-row{display:flex;align-items:center;gap:12px}
  .staged-item-icon{
    width:52px;height:52px;object-fit:contain;
    border-radius:5px;border:2px solid #ff4030;
    background:#0e0404;flex-shrink:0;
    box-shadow:0 0 12px #ff403066;
  }
  .staged-item-info{flex:1;min-width:0}
  .staged-item-label{
    font-family:'Bloodcrow',serif;font-size:12px;letter-spacing:.08em;
    color:#c08080;text-transform:uppercase;margin-bottom:2px;
  }
  .staged-item-name{
    font-family:'Bloodcrow',serif;font-size:18px;
    color:#ff8060;text-shadow:0 0 10px #ff604077;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  }
  .staged-hint{
    font-family:'Bloodcrow',serif;font-size:14px;font-style:italic;
    color:#ff6040;text-align:center;
    animation:hintPulse 2s ease-in-out infinite;
  }
  @keyframes hintPulse{0%,100%{opacity:.7}50%{opacity:1;text-shadow:0 0 10px #ff604088}}

  #status{
    position:absolute;bottom:14px;right:18px;
    font-family:'Bloodcrow',serif;
    font-size:18px;font-style:italic;
    color:#8a7060;
    letter-spacing:.03em;
  }

  /* save slots */
  #save-slots{
    display:flex;gap:10px;
    padding:10px 0 4px;
    width:100%;justify-content:center;
    flex-wrap:nowrap;
  }
  .save-slot{
    position:relative;
    width:80px;height:80px;
    border:2px solid #4a3010;
    border-radius:6px;
    background:#0e0b07;
    cursor:pointer;
    overflow:hidden;
    transition:border-color .2s,box-shadow .2s;
    flex-shrink:0;
  }
  .save-slot:hover{border-color:#c8a050;box-shadow:0 0 14px #c8a05044}
  .save-slot.filled{border-color:#6a4a18}
  .save-slot.filled:hover{border-color:#e8c060;box-shadow:0 0 18px #e8c06055}
  .slot-num{
    position:absolute;top:3px;left:5px;
    font-family:'Bloodcrow',serif;font-size:11px;
    color:#7a6040;z-index:2;pointer-events:none;
  }
  .slot-img{
    width:100%;height:100%;object-fit:cover;
    display:none;border-radius:4px;
  }
  .save-slot.filled .slot-img{display:block}
  .slot-empty-label{
    position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
    font-family:'Bloodcrow',serif;font-size:11px;color:#3a2810;
    pointer-events:none;
  }
  .save-slot.filled .slot-empty-label{display:none}
  .slot-del{
    position:absolute;top:2px;right:2px;
    width:18px;height:18px;
    background:#2a0808;border:1px solid #5a1818;
    border-radius:3px;color:#cc4040;font-size:10px;
    cursor:pointer;display:none;z-index:3;
    line-height:1;padding:0;
  }
  .save-slot.filled .slot-del{display:flex;align-items:center;justify-content:center}
  .slot-del:hover{background:#4a0808;color:#ff6060}
  .save-slot.active-slot{
    border-color:#e8c050;
    box-shadow:0 0 18px #e8c05066, inset 0 0 8px #e8c05022;
  }
  .save-slot.active-slot .slot-num{color:#e8c050}

  @media(max-width:768px){
    #save-slots{gap:6px;padding:8px 10px 4px}
    .save-slot{width:calc(25% - 5px);height:0;padding-bottom:calc(25% - 5px)}
    .save-slot .slot-img{position:absolute;inset:0;height:100%}
    .save-slot .slot-empty-label{font-size:9px}
  }

  input[type=color]{width:44px;height:32px;border:none;background:none;cursor:pointer;padding:0;border-radius:4px}

  /* mobile */
  #menu-toggle{display:none}
  @media(max-width:768px){
    body{
      flex-direction:column;
      overflow:auto;
      height:auto;
      min-height:100vh;
    }

    /* reset desktop grid, switch to flex-column */
    body{
      display:flex;
      flex-direction:column;
      height:auto;
      min-height:100vh;
      overflow:auto;
    }

    /* ── 1. TITLE + SUBTITLE ── */
    #sidebar{
      order:0;
      width:100%;
      grid-area:unset;
      border-right:none;
      border-bottom:1px solid #4a3010;
      background:linear-gradient(180deg,#3d2b0f,#1e1508);
      box-shadow:none;
    }
    #sidebar-title{font-size:30px;padding:12px 16px 4px;cursor:default}

    /* ── 2. PREVIEW: sticky below title ── */
    #preview-area{
      order:1;
      grid-area:unset;
      position:sticky;
      top:0;
      z-index:30;
      width:100%;
      padding:8px 10px;
      background:rgba(8,6,8,0.94);
      backdrop-filter:blur(4px);
      align-items:center;
      flex-shrink:0;
    }
    #preview-wrap{width:calc(100vw - 20px)}
    #preview-img{width:100%;max-height:none;height:auto}

    /* ── BUTTONS inside preview area ── */
    #btn-area{
      width:100%;
      flex-direction:row;
      flex-wrap:nowrap;
      gap:6px;
      margin:8px 0 0;
      padding:0;
    }
    #btn-area button{flex:1;padding:9px 4px;font-size:14px;min-width:0}

    /* ── 3. ITEM MENU ── */
    #sidebar-content{
      order:2;
      grid-area:unset;
      width:100%;
      height:auto;
      overflow:visible;
      border-right:none;
      border-top:2px solid #6a4a1a;
      box-shadow:none;
    }

    /* ── BEWITCH PANEL: full width fixed at bottom ── */
    #staged-panel{
      position:fixed;
      bottom:0;left:0;right:0;
      width:100%;
      border-radius:0;
      border-left:none;border-right:none;border-bottom:none;
      flex-direction:row;
      align-items:center;
      padding:12px 16px;
      gap:14px;
      z-index:200;
    }
    @keyframes panelSlideIn{from{opacity:0;transform:translateY(40px)}to{opacity:1;transform:none}}
    #staged-img-preview{width:50px;height:50px;flex-shrink:0}
    #staged-name{font-size:17px}
    #staged-hint{display:none}
    #border-glow-svg{inset:-3px;width:calc(100% + 6px);height:calc(100% + 6px)}
  }
</style>
</head>
<body>

<video id="bg-video" autoplay muted loop playsinline>
  <source src="/img/back.mp4" type="video/mp4">
</video>

<div id="sidebar">
  <div id="sidebar-title">HEX &amp; THREAD</div>
  <div id="sidebar-subtitle">
    <img src="/img/icon.png" alt="">
    <span>Ritual Effigy Forge</span>
  </div>
  <div id="wallet-bar">
    <button id="btn-wallet" onclick="connectWallet()">Connect Wallet</button>
    <div id="wallet-status" style="display:none">
      <span id="wallet-addr"></span>
      <span id="wallet-badge"></span>
    </div>
  </div>
</div>
<div id="sidebar-content">

<div class="section" id="sec-bg">
    <div class="section-header" onclick="toggleSection('sec-bg')">Background <span class="arrow">›</span></div>
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
    <div class="section-header" onclick="toggleSection('sec-body')">Body <span class="arrow">›</span></div>
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
    <div class="section-header" onclick="toggleSection('sec-knife')">Blade — Right Hand <span class="arrow">›</span></div>
    <div class="section-body"><div class="thumb-grid" id="grid-knife"></div></div>
  </div>

  <div class="section" id="sec-offhand">
    <div class="section-header" onclick="toggleSection('sec-offhand')">Offhand — Left Hand <span class="arrow">›</span></div>
    <div class="section-body"><div class="thumb-grid" id="grid-offhand"></div></div>
  </div>

  <div class="section" id="sec-necklace">
    <div class="section-header" onclick="toggleSection('sec-necklace')">Necklace <span class="arrow">›</span></div>
    <div class="section-body"><div class="thumb-grid" id="grid-necklace"></div></div>
  </div>

  <div class="section" id="sec-eyes">
    <div class="section-header" onclick="toggleSection('sec-eyes')">Eyes <span class="arrow">›</span></div>
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
    <div class="section-header" onclick="toggleSection('sec-mouth')">Mouth <span class="arrow">›</span></div>
    <div class="section-body"><div class="thumb-grid" id="grid-mouth"></div></div>
  </div>

  <div class="section" id="sec-pins">
    <div class="section-header" onclick="toggleSection('sec-pins')">Pins <span class="arrow">›</span></div>
    <div class="section-body">
      <div id="pin-counter">Placed: <span id="pin-placed-count">0</span> / 5</div>
      <div style="font-family:'Bloodcrow',serif;font-size:13px;color:#7a6848;letter-spacing:.04em;margin-bottom:10px;line-height:1.5">
        Drag a pin onto the preview to place it on the doll. Up to 5 pins. Click a placed pin to remove it. Press Bewitch to apply.
      </div>
      <div class="thumb-grid" id="grid-pins"></div>
      <button id="pin-clear" onclick="clearPins()">✕ Clear All Pins</button>
    </div>
  </div>


  <div class="section" id="sec-name">
    <div class="section-header" onclick="toggleSection('sec-name')">Name <span class="arrow">›</span></div>
    <div class="section-body">
      <div style="display:flex;gap:8px;align-items:center">
        <input type="text" id="name_input" placeholder="Enter name…"
          onkeydown="if(event.key==='Enter') applyName()"
          style="
            flex:1;padding:10px 14px;
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
        <button onclick="applyName()" style="
          padding:10px 14px;
          background:#2a1820;border:1px solid #6a3848;border-radius:8px;
          color:#d4a84b;font-family:'Bloodcrow',serif;font-size:14px;
          cursor:pointer;white-space:nowrap;transition:background .2s;
        " onmouseover="this.style.background='#3a2030'" onmouseout="this.style.background='#2a1820'">Apply</button>
      </div>
    </div>
  </div>

  </div><!-- /sidebar-content -->

<div id="preview-area">
  <div id="preview-wrap">
    <img id="preview-img" src="" alt="Preview">
    <div id="pin-overlay"></div>
  </div>
  <div id="loading">
    <div class="spinner"></div>
    <p>Conjuring…</p>
  </div>
  <!-- ritual reveal veil -->
  <div id="ritual-veil">
    <div class="veil-bg"></div>
    <div class="glow-ring"></div>
    <div class="glow-ring"></div>
    <div class="glow-ring"></div>
    <img id="bewitch-img" src="/img/bewitch.png" alt="">
  </div>
  <div id="selected-panel"></div>
  <div id="pending-indicator"></div>
  <div id="status">awaiting ritual…</div>
  <div id="btn-area">
    <button id="btn-rand" onclick="randomizeAll()">Randomize</button>
    <button id="btn-save" onclick="saveHQ()">☽ Bind</button>
    <button id="btn-clear" onclick="clearAll()">✕ Clear</button>
  </div>
  <div id="save-slots" style="display:none">
    <div class="save-slot" id="slot-0" onclick="slotClick(0)"><span class="slot-num">I</span><button class="slot-del" onclick="deleteSlot(event,0)">✕</button><img class="slot-img" src="" alt=""><div class="slot-empty-label">Empty</div></div>
    <div class="save-slot" id="slot-1" onclick="slotClick(1)"><span class="slot-num">II</span><button class="slot-del" onclick="deleteSlot(event,1)">✕</button><img class="slot-img" src="" alt=""><div class="slot-empty-label">Empty</div></div>
    <div class="save-slot" id="slot-2" onclick="slotClick(2)"><span class="slot-num">III</span><button class="slot-del" onclick="deleteSlot(event,2)">✕</button><img class="slot-img" src="" alt=""><div class="slot-empty-label">Empty</div></div>
    <div class="save-slot" id="slot-3" onclick="slotClick(3)"><span class="slot-num">IV</span><button class="slot-del" onclick="deleteSlot(event,3)">✕</button><img class="slot-img" src="" alt=""><div class="slot-empty-label">Empty</div></div>
  </div>
</div>

<div id="toast-area"></div>

<!-- staged item panel, bottom-right -->
<div id="staged-panel" onclick="castCurse()">
  <svg id="border-glow-svg" xmlns="http://www.w3.org/2000/svg">
    <rect id="bgr" rx="9" ry="9"/>
  </svg>
  <div class="staged-item-row">
    <img id="staged-icon" class="staged-item-icon" src="" alt="">
    <div class="staged-item-info">
      <div class="staged-item-label" id="staged-label">Selected</div>
      <div class="staged-item-name" id="staged-name">—</div>
    </div>
  </div>
  <div class="staged-hint">⛧ Tap to Bewitch</div>
</div>

<script>
// State — staged (selected) vs equipped (on character)
const sel = {
  body_file: null, knife_file: null, offhand_file: null,
  necklace_file: null, eye_left_file: null, eye_right_file: null, mouth_file: null
};
const equipped = {
  body_file: null, knife_file: null, offhand_file: null,
  necklace_file: null, eye_left_file: null, eye_right_file: null, mouth_file: null
};

// Placed pins: [{x:0-1, y:0-1, src:string}]
let placedPins = [];
let walletConnected = false;
let isHolder = false;
let activeSlot = -1;
let dragPinSrc = null;  // src of pin being dragged

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
['overlay_hue','overlay_strength','body_hue','body_sat'].forEach(id=>{
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
  buildGridRarity('grid-knife',   'knife',data.knife,    'knife_file');
  buildGridFlat(  'grid-offhand', 'offhand',       data.offhand,  'offhand_file');
  buildGridFlat(  'grid-mouth',   'mouths',        data.mouths,   'mouth_file');
  buildGridRarity('grid-necklace','necklace',      data.necklace, 'necklace_file');
  buildGridRarity('grid-eye-left','eyes',          data.eyes,     'eye_left_file');
  buildGridRarity('grid-eye-right','eyes',         data.eyes,     'eye_right_file');
  buildPinGrid(data.pins||[]);
  applyHolderFilter();
}

function makeWrap(src, title, path, extraClass){
  const wrap=document.createElement('div');
  wrap.className='thumb-wrap'+(extraClass?' '+extraClass:'');
  wrap.dataset.path=path;
  const img=document.createElement('img');
  img.className='thumb';
  img.src=src; img.title=title;
  const badge=document.createElement('span');
  badge.className='thumb-badge';
  wrap.appendChild(img);
  wrap.appendChild(badge);
  return wrap;
}

function buildGridFlat(gridId, folder, files, key){
  const grid=document.getElementById(gridId);
  grid.innerHTML='';
  if(!files||!files.length) return;
  files.forEach(fname=>{
    const wrap=makeWrap(`/img/${folder}/${fname}`, fname, fname);
    wrap.onclick=()=>selectThumb(grid, wrap, key, fname);
    grid.appendChild(wrap);
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
      const wrap=makeWrap(`/img/${folder}/${path}`, path, path, `rarity-wrap-${rarity}`);
      wrap.querySelector('.thumb').classList.add(`rarity-${rarity}`);
      if(isKnife && RARITY_GLOW[rarity]) wrap.querySelector('.thumb').style.filter=RARITY_GLOW[rarity];
      wrap.onclick=()=>selectThumb(grid, wrap, key, path);
      grid.appendChild(wrap);
    });
  });
}

// Mark a wrap as staged (selected but not yet equipped)
function selectThumb(grid, wrap, key, path){
  grid.querySelectorAll('.thumb-wrap').forEach(w=>{
    w.classList.remove('staged');
    // keep equipped badge if equipped
    const badge=w.querySelector('.thumb-badge');
    if(w.classList.contains('equipped')) badge.textContent='✓';
    else badge.textContent='';
  });
  wrap.classList.add('staged');
  wrap.querySelector('.thumb-badge').textContent='◆';
  sel[key]=path;
  updateBewitchState();
  showStagedPanel(key, path, wrap.querySelector('img').src);
}

// Sync equipped visuals across all grids
function updateEquippedVisuals(){
  const keyToGrid={
    body_file:'grid-body', knife_file:'grid-knife', offhand_file:'grid-offhand',
    necklace_file:'grid-necklace', eye_left_file:'grid-eye-left',
    eye_right_file:'grid-eye-right', mouth_file:'grid-mouth'
  };
  for(const [key, gridId] of Object.entries(keyToGrid)){
    const grid=document.getElementById(gridId);
    if(!grid) continue;
    grid.querySelectorAll('.thumb-wrap').forEach(w=>{
      const isEquipped = equipped[key] && w.dataset.path===equipped[key];
      const isStaged   = sel[key] && w.dataset.path===sel[key];
      w.classList.toggle('equipped', isEquipped);
      w.classList.toggle('staged', isStaged && !isEquipped);
      const badge=w.querySelector('.thumb-badge');
      if(isStaged && !isEquipped) badge.textContent='◆';
      else if(isEquipped) badge.textContent='✓';
      else badge.textContent='';
    });
  }
}

function updateSelectedPanel(){
  const panel=document.getElementById('selected-panel');
  const labels={
    body_file:'Body',knife_file:'Knife',offhand_file:'Offhand',
    necklace_file:'Necklace',eye_left_file:'L.Eye',eye_right_file:'R.Eye',mouth_file:'Mouth'
  };
  panel.innerHTML='';
  for(const [k,label] of Object.entries(labels)){
    if(!equipped[k]) continue;
    const name=equipped[k].split('/').pop().replace(/\.png$/i,'').replace(/_/g,' ');
    const tag=document.createElement('span');
    tag.className='sel-tag';
    tag.textContent=label+': '+name;
    panel.appendChild(tag);
  }
}

function showToast(text, type=''){
  const area=document.getElementById('toast-area');
  const t=document.createElement('div');
  t.className='toast'+(type?' '+type:'');
  t.textContent=text;
  area.appendChild(t);
  setTimeout(()=>t.remove(), 3000);
}

// ── Pin drag-and-drop ─────────────────────────────────────────────────────────
function buildPinGrid(files){
  const grid=document.getElementById('grid-pins');
  if(!grid) return;
  grid.innerHTML='';
  // List all pins from /img/pins/ — if server doesn't send, use numbered fallback
  const pinList = files.length ? files : Array.from({length:35},(_,i)=>`${i+1}.png`);
  pinList.forEach(fname=>{
    const img=document.createElement('img');
    img.className='pin-drag-thumb';
    img.src=`/img/pins/${fname}`;
    img.draggable=true;
    img.addEventListener('dragstart',e=>{
      dragPinSrc=img.src;
      img.classList.add('dragging');
      e.dataTransfer.effectAllowed='copy';
    });
    img.addEventListener('dragend',()=>img.classList.remove('dragging'));
    grid.appendChild(img);
  });
}

function initPinOverlay(){
  const overlay=document.getElementById('pin-overlay');
  const previewImg=document.getElementById('preview-img');

  overlay.addEventListener('dragover',e=>{
    if(!dragPinSrc) return;
    e.preventDefault();
    e.dataTransfer.dropEffect='copy';
    overlay.classList.add('drop-active');
  });
  overlay.addEventListener('dragleave',()=>overlay.classList.remove('drop-active'));
  overlay.addEventListener('drop',e=>{
    e.preventDefault();
    overlay.classList.remove('drop-active');
    if(!dragPinSrc || placedPins.length>=5) return;
    const rect=previewImg.getBoundingClientRect();
    const nx=(e.clientX-rect.left)/rect.width;
    const ny=(e.clientY-rect.top)/rect.height;
    if(nx<0||nx>1||ny<0||ny>1) return;
    addPlacedPin(nx, ny, dragPinSrc);
    dragPinSrc=null;
    updateBewitchState();
  });
}

function addPlacedPin(nx, ny, src){
  placedPins.push({x:nx, y:ny, src});
  renderPlacedPins();
}

function renderPlacedPins(){
  const overlay=document.getElementById('pin-overlay');
  const previewImg=document.getElementById('preview-img');
  // Remove existing placed-pin elements
  overlay.querySelectorAll('.placed-pin').forEach(el=>el.remove());

  // Size of overlay matches preview image display size
  const w=previewImg.offsetWidth, h=previewImg.offsetHeight;

  placedPins.forEach((pin,i)=>{
    const wrap=document.createElement('div');
    wrap.className='placed-pin';
    wrap.style.left=(pin.x*100)+'%';
    wrap.style.top=(pin.y*100)+'%';

    const img=document.createElement('img');
    img.src=pin.src;
    img.style.cssText='width:32px;height:32px;object-fit:contain;display:block';

    const rm=document.createElement('div');
    rm.className='pin-remove';
    rm.textContent='✕';
    rm.onclick=(e)=>{
      e.stopPropagation();
      placedPins.splice(i,1);
      renderPlacedPins();
      updatePinCounter();
      updateBewitchState();
    };

    wrap.appendChild(img);
    wrap.appendChild(rm);
    overlay.appendChild(wrap);
  });
  updatePinCounter();
}

function clearPins(){
  placedPins=[];
  renderPlacedPins();
  updateBewitchState();
}

function updatePinCounter(){
  const el=document.getElementById('pin-placed-count');
  if(el) el.textContent=placedPins.length;
}

// ── Pending state ─────────────────────────────────────────────────────────────
function checkPending(){
  const keys=Object.keys(sel);
  for(const k of keys){
    if(sel[k]!==equipped[k]) return true;
  }
  if(placedPins.length>0) return true;
  return false;
}

function updateBewitchState(){
  const ind=document.getElementById('pending-indicator');
  const pending=checkPending();

  if(pending){
    const changes=[];
    const labels={body_file:'Body',knife_file:'Blade',offhand_file:'Offhand',
      necklace_file:'Necklace',eye_left_file:'L.Eye',eye_right_file:'R.Eye',mouth_file:'Mouth'};
    for(const [k,label] of Object.entries(labels)){
      if(sel[k] && sel[k]!==equipped[k]){
        const name=sel[k].split('/').pop().replace(/\.png$/i,'').replace(/_/g,' ');
        changes.push(label+': '+name);
      }
    }
    if(placedPins.length>0) changes.push(placedPins.length+' pin'+(placedPins.length>1?'s':''));
    ind.textContent='⛧ '+changes.join(' · ')+' — ready to bewitch';
    ind.classList.add('active');
  } else {
    ind.textContent='';
    ind.classList.remove('active');
  }
}

function showStagedPanel(key, path, iconSrc){
  const labels={body_file:'Body',knife_file:'Blade',offhand_file:'Offhand',
    necklace_file:'Necklace',eye_left_file:'L. Eye',eye_right_file:'R. Eye',mouth_file:'Mouth'};
  const name=path.split('/').pop().replace(/\.png$/i,'').replace(/_/g,' ');
  document.getElementById('staged-label').textContent=labels[key]||key;
  document.getElementById('staged-name').textContent=name;
  document.getElementById('staged-icon').src=iconSrc;
  const panel=document.getElementById('staged-panel');
  panel.classList.remove('visible');
  void panel.offsetWidth;
  panel.classList.add('visible');
  // Update SVG border rect to actual panel dimensions
  requestAnimationFrame(()=>{
    const pw=panel.offsetWidth, ph=panel.offsetHeight;
    const rx=9, pad=4;
    const rw=pw+pad*2, rh=ph+pad*2;
    const rect=document.getElementById('bgr');
    rect.setAttribute('x', pad+1.5);
    rect.setAttribute('y', pad+1.5);
    rect.setAttribute('width', pw-3);
    rect.setAttribute('height', ph-3);
    // Perimeter of rounded rect
    const perim=Math.round(2*(pw-3-2*rx)+2*(ph-3-2*rx)+2*Math.PI*rx);
    rect.style.setProperty('--perim', `-${perim}`);
  });
}

function hideStagedPanel(){
  document.getElementById('staged-panel').classList.remove('visible');
}

function clearAll(){
  const keys=Object.keys(sel);
  // Clear staged
  keys.forEach(k=>{ sel[k]=null; });
  // Clear equipped
  keys.forEach(k=>{ equipped[k]=null; });
  // Clear all visual states on all grids
  document.querySelectorAll('.thumb-wrap').forEach(w=>{
    w.classList.remove('staged','equipped');
    const b=w.querySelector('.thumb-badge');
    if(b) b.textContent='';
  });
  clearPins();
  hideStagedPanel();
  updateSelectedPanel();
  updateBewitchState();
  // Re-select first body so preview isn't empty
  const firstBody=document.querySelector('#grid-body .thumb-wrap');
  if(firstBody){
    const path=firstBody.dataset.path;
    sel.body_file=path; equipped.body_file=path;
    firstBody.classList.add('equipped');
    firstBody.querySelector('.thumb-badge').textContent='✓';
    updateBewitchState();
    generate();
  }
}

function selectRandom(gridId, key){
  const grid=document.getElementById(gridId);
  const wraps=[...grid.querySelectorAll('.thumb-wrap')].filter(w=>w.style.display!=='none');
  if(!wraps.length) return;
  const pick=wraps[Math.floor(Math.random()*wraps.length)];
  sel[key]=pick.dataset.path;
}

async function randomizeAll(){
  // Pick random items
  selectRandom('grid-body','body_file');
  selectRandom('grid-knife','knife_file');
  selectRandom('grid-offhand','offhand_file');
  selectRandom('grid-necklace','necklace_file');
  selectRandom('grid-eye-left','eye_left_file');
  selectRandom('grid-eye-right','eye_right_file');
  selectRandom('grid-mouth','mouth_file');
  document.getElementById('overlay_hue').value=Math.floor(Math.random()*360);
  document.getElementById('body_hue').value=Math.floor(Math.random()*360);
  document.getElementById('body_sat').value=40+Math.floor(Math.random()*50);
  ['overlay_hue','body_hue','body_sat'].forEach(id=>{
    const lbl=document.getElementById(id+'_v');
    if(lbl) lbl.textContent=document.getElementById(id).value;
  });
  updateSwatch(); updateBodySwatch();
  clearPins();
  Object.assign(equipped, sel);
  updateEquippedVisuals();
  updateSelectedPanel();
  updateBewitchState();

  // Force-reset generating state and run animation
  isGenerating = false;
  const veil = document.getElementById('ritual-veil');
  const img  = document.getElementById('preview-img');
  veil.classList.remove('active','revealing');
  veil.style.cssText='opacity:1;pointer-events:auto';
  void veil.offsetWidth;
  veil.classList.add('active');
  isGenerating = true;
  const ANIM_MS = 1400;
  const animDone = new Promise(r=>setTimeout(r, ANIM_MS));
  const fetchDone = fetch('/generate',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(buildParams())}).then(r=>r.json());
  try{
    const [data] = await Promise.all([fetchDone, animDone]);
    img.style.opacity='0';
    img.src='data:image/png;base64,'+data.image;
    veil.style.cssText='opacity:0;pointer-events:none';
    veil.classList.remove('active','revealing');
    img.classList.remove('curse-reveal');
    void img.offsetWidth;
    img.classList.add('curse-reveal');
    img.addEventListener('animationend',()=>{img.classList.remove('curse-reveal');img.style.opacity='';},{once:true});
    document.getElementById('status').textContent='randomized';
  }catch(e){
    veil.style.cssText='opacity:0;pointer-events:none';
    veil.classList.remove('active','revealing');
  }
  isGenerating = false;
}

function scheduleGen(){
  generate();
}

function applyName(){
  generate();
}

function toggleSidebar(){
  if(window.innerWidth<=768)
    document.getElementById('sidebar').classList.toggle('collapsed');
}

async function connectWallet(){
  if(!window.solana || !window.solana.isPhantom){
    alert('Phantom wallet not found. Please install it from phantom.app');
    return;
  }
  try{
    const resp = await window.solana.connect();
    const pubkey = resp.publicKey.toString();
    walletConnected = true;

    const btnW = document.getElementById('btn-wallet');
    btnW.textContent = 'Disconnect';
    btnW.classList.add('connected');
    btnW.onclick = disconnectWallet;

    document.getElementById('wallet-addr').textContent =
      pubkey.slice(0,4)+'...'+pubkey.slice(-4);
    document.getElementById('wallet-status').style.display='flex';

    const badge = document.getElementById('wallet-badge');
    badge.textContent = 'Checking…';
    badge.className = 'wallet-badge';

    const res = await fetch('/check_holder',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({wallet: pubkey})
    });
    const data = await res.json();
    isHolder = data.holder === true;

    badge.textContent = isHolder ? 'HOLDER' : 'NOT HOLDER';
    badge.className = isHolder ? 'holder' : 'not-holder';

    applyHolderFilter();
  } catch(e){
    console.error('Wallet connect error', e);
  }
}

function disconnectWallet(){
  if(window.solana) window.solana.disconnect();
  walletConnected = false;
  isHolder = false;
  const btnW = document.getElementById('btn-wallet');
  btnW.textContent = 'Connect Wallet';
  btnW.classList.remove('connected');
  btnW.onclick = connectWallet;
  document.getElementById('wallet-status').style.display='none';
  applyHolderFilter();
}

function applyHolderFilter(){
  const nonCommon = ['rare','legendary','ultimate'];
  nonCommon.forEach(r=>{
    document.querySelectorAll(`.rarity-wrap-${r}`).forEach(el=>{
      el.style.display = isHolder ? '' : 'none';
    });
    document.querySelectorAll(`.rf-${r}`).forEach(el=>{
      el.style.display = isHolder ? '' : 'none';
    });
  });
  // Show save slots when wallet connected; locked visually for non-holders
  const slots = document.getElementById('save-slots');
  if(slots) slots.style.display = walletConnected ? 'flex' : 'none';
  if(walletConnected) renderSlots();
  // Lock/unlock slot interaction for non-holders
  document.querySelectorAll('.save-slot').forEach(el=>{
    el.style.opacity = isHolder ? '' : '0.35';
    el.style.pointerEvents = isHolder ? '' : 'none';
  });
}

// ── Save Slots ──────────────────────────────────────────────
const SLOTS_KEY = 'voodoo_slots';

function getSlotsData(){
  try{ return JSON.parse(localStorage.getItem(SLOTS_KEY)||'[null,null,null,null]'); }
  catch{ return [null,null,null,null]; }
}

function compressImage(b64, maxW=120) {
  return new Promise(resolve => {
    const img = new Image();
    img.onload = () => {
      try {
        const scale = Math.min(1, maxW / img.width);
        const canvas = document.createElement('canvas');
        canvas.width = Math.round(img.width * scale);
        canvas.height = Math.round(img.height * scale);
        canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL('image/jpeg', 0.7).split(',')[1]);
      } catch(e) {
        console.error('[compressImage] error:', e);
        resolve(b64.slice(0, 50000)); // fallback: truncate
      }
    };
    img.onerror = (e) => {
      console.error('[compressImage] image load failed:', e);
      resolve(b64.slice(0, 50000));
    };
    // accept full data URL or raw b64
    img.src = b64.startsWith('data:') ? b64 : 'data:image/png;base64,' + b64;
  });
}

async function saveSlotData(idx, data){
  const slots = getSlotsData();
  if(data && data.image){
    data = {...data, image: await compressImage(data.image)};
  }
  slots[idx] = data;
  try {
    localStorage.setItem(SLOTS_KEY, JSON.stringify(slots));
  } catch(e) {
    // localStorage full — clear oldest filled slot and retry
    const fallback = [...slots];
    for(let i=0;i<4;i++){ if(i!==idx && fallback[i]){ fallback[i]=null; break; } }
    fallback[idx] = data;
    try { localStorage.setItem(SLOTS_KEY, JSON.stringify(fallback)); } catch(e2){}
  }
}

function renderSlots(){
  const slots = getSlotsData();
  for(let i=0;i<4;i++){
    const el = document.getElementById(`slot-${i}`);
    if(!el) continue;
    const d = slots[i];
    if(d){
      el.classList.add('filled');
      const img = el.querySelector('.slot-img');
      if(img && d.image) img.src = 'data:image/jpeg;base64,'+d.image;
    } else {
      el.classList.remove('filled');
      const img = el.querySelector('.slot-img');
      if(img) img.src='';
    }
  }
}

function slotClick(idx){
  const slots = getSlotsData();
  toggleSlot(idx);
  // If slot has data and we just activated it, load it
  if(activeSlot === idx && slots[idx]) loadSlot(idx);
}

function toggleSlot(idx){
  // Deactivate previously active slot
  if(activeSlot !== -1){
    document.getElementById(`slot-${activeSlot}`)?.classList.remove('active-slot');
  }
  if(activeSlot === idx){
    activeSlot = -1; // toggle off
  } else {
    activeSlot = idx;
    document.getElementById(`slot-${idx}`)?.classList.add('active-slot');
  }
}

async function saveToSlot(imageB64){
  console.log('[saveToSlot] called, walletConnected='+walletConnected+' activeSlot='+activeSlot+' imageB64 len='+(imageB64||'').length);
  const slots = getSlotsData();
  let idx = activeSlot !== -1 ? activeSlot : slots.findIndex(s => s === null);
  if(idx === -1) idx = 0;
  activeSlot = idx;
  const snapshot = {
    equipped: {...equipped},
    sliders: {
      overlay_hue: v('overlay_hue'),
      overlay_strength: v('overlay_strength'),
      body_hue: v('body_hue'),
      body_sat: v('body_sat'),
      bg_type: document.querySelector('input[name=bg_type]:checked').value,
      bg_color: v('bg_color'),
    },
    pins: [...placedPins],
    name: document.getElementById('name_input').value,
    image: imageB64
  };
  console.log('[saveToSlot] saving to idx='+idx);
  await saveSlotData(idx, snapshot);
  console.log('[saveToSlot] done, slots now=', getSlotsData().map(s=>s?'filled':'null'));
  renderSlots();
  showToast(`Saved to slot ${['I','II','III','IV'][idx]}`);
}

function loadSlot(idx){
  const slots = getSlotsData();
  const d = slots[idx];
  if(!d) return;

  Object.assign(equipped, d.equipped);
  Object.assign(sel, d.equipped);
  updateEquippedVisuals();

  // Restore sliders
  ['overlay_hue','overlay_strength','body_hue','body_sat'].forEach(id=>{
    const el=document.getElementById(id);
    const lbl=document.getElementById(id+'_v');
    if(el && d.sliders[id]!=null){ el.value=d.sliders[id]; if(lbl)lbl.textContent=el.value; }
  });
  if(d.sliders.bg_type){
    document.querySelectorAll('input[name=bg_type]').forEach(r=>{ r.checked=(r.value===d.sliders.bg_type); });
    document.getElementById('flat-color-row').style.display = d.sliders.bg_type==='flat'?'flex':'none';
  }
  const bgc=document.getElementById('bg_color');
  if(bgc && d.sliders.bg_color) bgc.value=d.sliders.bg_color;

  updateSwatch(); updateBodySwatch();

  // Restore pins
  clearPins();
  if(d.pins) d.pins.forEach(p=>addPlacedPin(p.x,p.y,p.src||''));

  // Restore name
  const nameEl=document.getElementById('name_input');
  if(nameEl) nameEl.value=d.name||'';

  // Show saved image immediately then regenerate
  const previewImg=document.getElementById('preview-img');
  if(d.image) previewImg.src='data:image/jpeg;base64,'+d.image;

  generate();
  showToast(`Loaded slot ${['I','II','III','IV'][idx]}`);
}

async function deleteSlot(e, idx){
  e.stopPropagation();
  await saveSlotData(idx, null);
  renderSlots();
  showToast(`Slot ${['I','II','III','IV'][idx]} cleared`);
}

function buildParams(useStaged=false){
  const src = useStaged ? sel : equipped;
  const bg_type=document.querySelector('input[name=bg_type]:checked').value;
  return {
    bg_type,
    bg_color: v('bg_color'),
    overlay_hue: parseInt(v('overlay_hue'))/360,
    overlay_sat: 0.7,
    overlay_val: 0.9,
    overlay_strength: parseInt(v('overlay_strength'))/100,
    body_file: src.body_file,
    body_hue: parseInt(v('body_hue'))/360,
    body_sat: parseInt(v('body_sat'))/100,
    body_val: 0.85,
    knife_file: src.knife_file,
    offhand_file: src.offhand_file,
    necklace_file: src.necklace_file,
    eye_left_file: src.eye_left_file,
    eye_right_file: src.eye_right_file,
    mouth_file: src.mouth_file,
    pins: placedPins.map(p=>({x:p.x, y:p.y})),
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

async function castCurse({save=true}={}){
  if(isGenerating) return;
  const veil=document.getElementById('ritual-veil');
  const img=document.getElementById('preview-img');

  const labels={body_file:'Body',knife_file:'Blade',offhand_file:'Offhand',
    necklace_file:'Necklace',eye_left_file:'L. Eye',eye_right_file:'R. Eye',mouth_file:'Mouth'};
  const newlyEquipped=[];
  for(const [k,label] of Object.entries(labels)){
    if(sel[k] && sel[k]!==equipped[k]){
      const name=sel[k].split('/').pop().replace(/\.png$/i,'').replace(/_/g,' ');
      newlyEquipped.push({label, name});
    }
  }
  Object.assign(equipped, sel);

  function showVeil(){
    // Remove active to reset animations, force reflow, re-add
    veil.classList.remove('active','revealing');
    veil.style.cssText='opacity:1;pointer-events:auto';
    void veil.offsetWidth;
    veil.classList.add('active');
  }
  function hideVeil(){
    veil.style.cssText='opacity:0;pointer-events:none';
    veil.classList.remove('active','revealing');
  }

  showVeil();
  isGenerating=true;
  document.getElementById('status').textContent='casting…';
  const t0=performance.now();

  // Fetch and animation run in parallel
  // Animation is exactly 1.5s — reveal happens at the end
  const ANIM_MS = 1400;
  const animDone = new Promise(r=>setTimeout(r, ANIM_MS));
  const fetchDone = fetch('/generate',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(buildParams())}).then(r=>r.json());

  try{
    const [data] = await Promise.all([fetchDone, animDone]);

    // Animation done — swap image and fade in
    img.style.opacity='0';
    img.src='data:image/png;base64,'+data.image;

    hideVeil();

    img.classList.remove('curse-reveal');
    void img.offsetWidth;
    img.classList.add('curse-reveal');
    img.addEventListener('animationend',()=>{
      img.classList.remove('curse-reveal');
      img.style.opacity='';
    },{once:true});

    newlyEquipped.forEach((item,i)=>{
      setTimeout(()=>showToast(`⛧ ${item.label}: ${item.name} — Bound`,'equipped-toast'), i*180);
    });
    if(placedPins.length>0) showToast(`⛧ ${placedPins.length} Pin${placedPins.length>1?'s':''} — Bound`,'equipped-toast');
    updateEquippedVisuals();
    updateSelectedPanel();
    updateBewitchState();
    hideStagedPanel();
    document.getElementById('status').textContent=`${Math.round(performance.now()-t0)}ms`;
    if(walletConnected && save) await saveToSlot(data.image);
  }catch(e){
    hideVeil();
    document.getElementById('status').textContent='error: '+e.message;
  }
  isGenerating=false;
}

async function saveHQ(){
  if(isGenerating) return;
  document.getElementById('status').textContent='binding…';
  try{
    const params={...buildParams(), preview_size:2048};
    const res=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(params)});
    const data=await res.json();
    document.getElementById('status').textContent='bound: '+data.filename;
    showToast('☽ Sealed: '+data.filename);
    // Save current preview image to slot
    if(walletConnected){
      const previewSrc = document.getElementById('preview-img').src;
      const b64 = previewSrc.includes(',') ? previewSrc.split(',')[1] : previewSrc;
      await saveToSlot(b64);
    }
  }catch(e){
    document.getElementById('status').textContent='error: '+e.message;
  }
}

// Init — first common body only
loadItems().then(()=>{
  const firstBody=document.querySelector('#grid-body .thumb-wrap');
  if(firstBody){ sel.body_file=firstBody.dataset.path; }
  Object.assign(equipped, sel);
  updateEquippedVisuals();
  updateSelectedPanel();
  updateBewitchState();
  document.getElementById('sec-body').classList.add('open');
  initPinOverlay();
  generate();
});
</script>
</body>
</html>"""

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5050))
    print(f"http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
