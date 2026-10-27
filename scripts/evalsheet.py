"""Visual evaluation aids.
  python3 -I evalsheet.py m01 sample 24 [statuses]   -> out/m01.sample.jpg : crops of random matched phrases with OCR text and gazetteer name
  python3 -I evalsheet.py m01 window X Y W H         -> out/m01.window.jpg : an annotated window with every detected phrase (box + text)
"""
import sys, json, random
from PIL import Image, ImageDraw, ImageFont
Image.MAX_IMAGE_PIXELS = None
S = './'
stem, mode = sys.argv[1], sys.argv[2]
d = json.load(open(S + f'out/{stem}.geocoded.json')); ph = d['phrases']
im = Image.open(S + f'in/{stem}.jpg').convert('RGB')
try: font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14); fontb = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 14)
except Exception: font = fontb = ImageFont.load_default()
COL = {'gcp': (47, 138, 62), 'near': (31, 158, 158), 'area': (59, 111, 209), 'lexical': (224, 138, 30), 'none': (130, 146, 167)}

if mode == 'sample':
    n = int(sys.argv[3]); statuses = sys.argv[4].split(',') if len(sys.argv) > 4 else ['gcp', 'near', 'area']
    random.seed(int(sys.argv[5]) if len(sys.argv) > 5 else 1)
    pool = [(i, p) for i, p in enumerate(ph) if p['status'] in statuses]
    smp = random.sample(pool, min(n, len(pool)))
    CW, CH, cols = 420, 150, 3
    rows = (len(smp) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * CW, rows * CH), 'white'); dr = ImageDraw.Draw(sheet)
    for k, (i, p) in enumerate(smp):
        x0, y0, x1, y1 = p['bbox']; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        hw = max((x1 - x0) / 2 + 40, 150); hh = max((y1 - y0) / 2 + 30, 50)
        crop = im.crop((int(cx - hw), int(cy - hh), int(cx + hw), int(cy + hh)))
        crop.thumbnail((CW - 10, CH - 42))
        ox, oy = (k % cols) * CW, (k // cols) * CH
        sheet.paste(crop, (ox + 5, oy + 5))
        m = p['match'] or {}
        dr.text((ox + 5, oy + CH - 36), f"#{i} OCR: {p['text']}", fill=(20, 20, 20), font=fontb)
        dr.text((ox + 5, oy + CH - 19), f"→ {m.get('name','')} ({m.get('type','')}) s={m.get('score',0):.0f} Δ={m.get('residual_km','')}", fill=COL[p['status']], font=font)
    sheet.save(S + f'out/{stem}.sample.jpg', quality=85)
    print('sample of', len(smp), '->', S + f'out/{stem}.sample.jpg')
    for k, (i, p) in enumerate(smp): print(k, i, p['status'], '|', p['text'], '->', (p['match'] or {}).get('name'))
else:
    X, Y, Wd, Hd = [int(v) for v in sys.argv[3:7]]
    crop = im.crop((X, Y, X + Wd, Y + Hd)); dr = ImageDraw.Draw(crop)
    inside = [(i, p) for i, p in enumerate(ph) if X <= p['cx'] <= X + Wd and Y <= p['cy'] <= Y + Hd]
    for i, p in inside:
        x0, y0, x1, y1 = p['bbox']
        dr.rectangle((x0 - X, y0 - Y, x1 - X, y1 - Y), outline=COL[p['status']], width=2)
        dr.text((x0 - X, y0 - Y - 15), f"{i}:{p['text']}", fill=(200, 0, 0), font=fontb)
    crop.save(S + f'out/{stem}.window.jpg', quality=85)
    print(len(inside), 'phrases in window ->', S + f'out/{stem}.window.jpg')
    for i, p in inside: print(i, p['status'], '|', p['text'], '->', (p['match'] or {}).get('name'))
