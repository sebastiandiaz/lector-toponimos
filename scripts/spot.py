"""Text spotting on a historical map image, CPU-only (OnnxTR: DB-ResNet50 detector + PARSeq recognizer).

Tiles the image with overlap, runs the spotter on several rotations of each tile (map labels are often rotated),
maps every detected polygon back to original image pixels, merges duplicates and groups words into phrases.

usage: python3 -I spot.py IMAGE OUT.json [--scale 1.0] [--tile 1024] [--overlap 160] [--rot 0,90,-90,45,-45] [--minconf 0.45]
"""
import sys, json, math, time, argparse
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

ap = argparse.ArgumentParser()
ap.add_argument('image'); ap.add_argument('out')
ap.add_argument('--scale', type=float, default=1.0, help='upscale factor before spotting (for low-resolution scans)')
ap.add_argument('--tile', type=int, default=1024); ap.add_argument('--overlap', type=int, default=160)
ap.add_argument('--rot', default='0,90,-90,45,-45'); ap.add_argument('--minconf', type=float, default=0.3)
ap.add_argument('--batch', type=int, default=6)
ap.add_argument('--norm', action='store_true', help='background normalisation (grayscale, divide by blurred background, autocontrast): helps faint, low-contrast prints')
args = ap.parse_args()

from onnxtr.models import ocr_predictor
predictor = ocr_predictor(det_arch='db_resnet50', reco_arch='parseq', assume_straight_pages=False, detect_orientation=False, straighten_pages=False)

im = Image.open(args.image).convert('RGB')
W0, H0 = im.size
if args.norm:
    from PIL import ImageOps, ImageFilter
    g = ImageOps.grayscale(im)
    a = np.asarray(g).astype(np.float32); bg = np.asarray(g.filter(ImageFilter.GaussianBlur(25))).astype(np.float32)
    n = np.clip((a / (bg + 1)) * 200, 0, 255).astype(np.uint8)
    im = ImageOps.autocontrast(Image.fromarray(n), cutoff=1).convert('RGB'); del a, bg, n, g
if args.scale != 1.0:
    im = im.resize((round(W0*args.scale), round(H0*args.scale)), Image.BICUBIC)
W, H = im.size
rots = [float(r) for r in args.rot.split(',')]
T, OV = args.tile, args.overlap
stride = T - OV
xs = list(range(0, max(1, W - T) + 1, stride)); ys = list(range(0, max(1, H - T) + 1, stride))
if xs[-1] + T < W: xs.append(W - T)
if ys[-1] + T < H: ys.append(H - T)
xs = sorted(set(max(0, x) for x in xs)); ys = sorted(set(max(0, y) for y in ys))
tiles = [(x, y) for y in ys for x in xs]
print(f'image {W0}x{H0} scale {args.scale} -> {W}x{H}; {len(tiles)} tiles x {len(rots)} rotations', flush=True)

def unrotate(px, py, ang, tw, th, rw, rh):
    """point in the rotated tile (PIL rotate(ang, expand=True)) -> point in the unrotated tile."""
    a = math.radians(ang)
    x = px - rw/2; y = py - rh/2
    # PIL rotates counter-clockwise on screen (y down): inverse mapping rotates by -ang in the y-down frame
    xi = x*math.cos(a) - y*math.sin(a)
    yi = x*math.sin(a) + y*math.cos(a)
    return xi + tw/2, yi + th/2

words = []
t0 = time.time()
for ang in rots:
    batch, meta = [], []
    def flush():
        global batch, meta
        if not batch: return
        try:
            res = predictor(batch)
        except IndexError:          # OnnxTR fails on a tile with no detections at all (empty crop list): run tiles one by one and skip the empty ones
            pages = []
            for b in batch:
                try: pages.append(predictor([b]).pages[0])
                except IndexError: pages.append(None)
            class _R: pass
            res = _R(); res.pages = pages
        for page, (x0, y0, tw, th, rw, rh) in zip(res.pages, meta):
            if page is None: continue
            for block in page.blocks:
                for line in block.lines:
                    for w in line.words:
                        if w.confidence < args.minconf or len(w.value.strip()) < 2: continue
                        g = w.geometry
                        if len(g) == 2:   # straight box -> 4 points
                            (xa, ya), (xb, yb) = g; pts = [(xa, ya), (xb, ya), (xb, yb), (xa, yb)]
                        else: pts = list(g)
                        poly = []
                        for (rx, ry) in pts:
                            ux, uy = unrotate(rx*rw, ry*rh, ang, tw, th, rw, rh)
                            poly.append((round((x0 + ux)/args.scale, 1), round((y0 + uy)/args.scale, 1)))
                        words.append({'text': w.value, 'conf': round(float(w.confidence), 3), 'poly': poly, 'rot': ang})
        batch, meta = [], []
    for (x0, y0) in tiles:
        tile = im.crop((x0, y0, min(x0+T, W), min(y0+T, H)))
        tw, th = tile.size
        rt = tile.rotate(ang, expand=True, resample=Image.BICUBIC, fillcolor=(235, 225, 200)) if ang else tile
        batch.append(np.array(rt)); meta.append((x0, y0, tw, th, rt.size[0], rt.size[1]))
        if len(batch) >= args.batch: flush()
    flush()
    print(f'  rotation {ang:+.0f}: {len(words)} raw words so far, {time.time()-t0:.0f}s', flush=True)

# ---- merge duplicates (same label seen in overlapping tiles / several rotations): greedy NMS with a spatial index ----
from shapely.geometry import Polygon
from shapely.strtree import STRtree
def score(w): return w['conf'] * (1 + 0.15*min(len(w['text']), 12)) * (1.2 if any(c.isalpha() for c in w['text']) else 0.6)
words = [w for w in words if Polygon(w['poly']).is_valid and Polygon(w['poly']).area >= 4]
words.sort(key=score, reverse=True)
geoms = [Polygon(w['poly']) for w in words]
tree = STRtree(geoms)
suppressed = [False]*len(words)
kept = []
for i, (w, P) in enumerate(zip(words, geoms)):
    if suppressed[i]: continue
    kept.append(w)
    for j in tree.query(P, predicate='intersects'):
        j = int(j)
        if j <= i or suppressed[j]: continue
        Q = geoms[j]
        try: inter = P.intersection(Q).area
        except Exception: inter = 0
        if inter > 0.35 * min(P.area, Q.area): suppressed[j] = True
print(f'{len(words)} raw -> {len(kept)} merged words', flush=True)

# ---- group words into phrases along their reading direction ----
def axis(w):
    (x1,y1),(x2,y2),(x3,y3),(x4,y4) = w['poly']
    cx = (x1+x2+x3+x4)/4; cy = (y1+y2+y3+y4)/4
    ex, ey = (x2-x1+x3-x4)/2, (y2-y1+y3-y4)/2        # reading direction (top edge / bottom edge average)
    L = math.hypot(ex, ey) or 1; h = Polygon(w['poly']).area / L
    return cx, cy, ex/L, ey/L, L, h
for i, w in enumerate(kept): w['id'] = i; w.update(dict(zip(['cx','cy','dx','dy','len','h'], axis(w))))
kgeoms = [Polygon(w['poly']) for w in kept]
ktree = STRtree(kgeoms)
links = {}
for a in kept:
    best, bestd = None, 1e9
    cand = ktree.query(kgeoms[a['id']].buffer(a['len'] + 4*max(a['h'], 8) + 40))
    for j in cand:
        b = kept[int(j)]
        if a is b: continue
        # b must lie ahead of a along a's direction, roughly on the same baseline, with similar height
        vx, vy = b['cx'] - a['cx'], b['cy'] - a['cy']
        along = vx*a['dx'] + vy*a['dy']; across = abs(-vx*a['dy'] + vy*a['dx'])
        gap = along - (a['len'] + b['len'])/2
        if along <= 0 or gap > 1.6*max(a['h'], 8) or across > 0.6*max(a['h'], b['h']): continue
        if a['dx']*b['dx'] + a['dy']*b['dy'] < 0.9: continue   # same reading direction only (anti-parallel pairs would create cycles)
        if not (0.55 < (a['h']/(b['h'] or 1)) < 1.8): continue
        if gap < bestd: best, bestd = b, gap
    if best is not None: links[a['id']] = best['id']
# chains
# keep a single predecessor per word (the nearest one)
byb = {}
for k, v in links.items(): byb.setdefault(v, []).append(k)
for v, ks in byb.items():
    if len(ks) > 1:
        ks.sort(key=lambda k: math.hypot(kept[k]['cx'] - kept[v]['cx'], kept[k]['cy'] - kept[v]['cy']))
        for k in ks[1:]: links.pop(k, None)
nxt = links; prev = {v: k for k, v in links.items()}
phrases = []
seen = set()
for w in kept:
    if w['id'] in prev or w['id'] in seen: continue
    chain = [w]; cur = w; guard = {w['id']}
    while cur['id'] in nxt and nxt[cur['id']] not in guard and len(chain) < 12:
        cur = kept[nxt[cur['id']]]; chain.append(cur); guard.add(cur['id'])
    for c in chain: seen.add(c['id'])
    xs_ = [p[0] for c in chain for p in c['poly']]; ys_ = [p[1] for c in chain for p in c['poly']]
    phrases.append({'text': ' '.join(c['text'] for c in chain), 'conf': round(min(c['conf'] for c in chain), 3), 'words': [c['id'] for c in chain],
                    'bbox': [min(xs_), min(ys_), max(xs_), max(ys_)], 'cx': round(sum(c['cx'] for c in chain)/len(chain), 1), 'cy': round(sum(c['cy'] for c in chain)/len(chain), 1),
                    'angle': round(math.degrees(math.atan2(-chain[0]['dy'], chain[0]['dx'])), 1), 'h': round(sum(c['h'] for c in chain)/len(chain), 1)})
for w in kept:
    for k in ['dx','dy','len']: w.pop(k, None)
    w['cx'] = round(w['cx'],1); w['cy'] = round(w['cy'],1); w['h'] = round(w['h'],1)
json.dump({'image': args.image, 'width': W0, 'height': H0, 'scale': args.scale, 'rotations': rots, 'seconds': round(time.time()-t0, 1),
           'words': kept, 'phrases': phrases}, open(args.out, 'w'), ensure_ascii=False)
print(f'done: {len(kept)} words, {len(phrases)} phrases in {time.time()-t0:.0f}s -> {args.out}', flush=True)
