"""Turn the viewer's corrections into training data and gazetteer supplements.

  python3 -I make_dataset.py correcciones.json  [--out dataset/]

Input: the JSON exported by the viewer ("Exportar correcciones") or the documents of the artifact's `correcciones`
collection (same fields: mapa, codigo, i, ocr, texto, tipo, veredicto, gacetero, bbox_px, autor, fecha).

Outputs:
  dataset/recognition/images/<mapa>-<i>.png  straightened crops of each corrected or confirmed label (full-resolution image)
  dataset/recognition/labels.json            {"<file>": "<text>"}  — the format of doctr/onnxtr recognition datasets (RecognitionDataset)
  dataset/detection/<mapa>.json              word polygons of validated labels, for detection fine-tuning (doctr DetectionDataset format)
  dataset/gacetero_suplemento.csv            names corrected to a form absent from the gazetteer, with the map's predicted lon/lat
Labels with veredicto "no-toponimo" or "ilegible" are kept out of the recognition set (ilegible) or used as negatives (no-toponimo).
"""
import json, sys, os, math, csv, argparse, unicodedata, re
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
S = './'
ap = argparse.ArgumentParser(); ap.add_argument('corr'); ap.add_argument('--out', default=S + 'dataset'); a = ap.parse_args()
raw = json.load(open(a.corr))
rows = raw['correcciones'] if isinstance(raw, dict) and 'correcciones' in raw else (list(raw.values()) if isinstance(raw, dict) else raw)
os.makedirs(a.out + '/recognition/images', exist_ok=True); os.makedirs(a.out + '/detection', exist_ok=True)
labels, det, supp = {}, {}, []
gaz = json.load(open(S + '../gaz/gazetteer.json'))['entries']
def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower(); return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]+', ' ', s)).strip()
gaznorm = {v for e in gaz for v in e['variants']}
cache = {}
for c in rows:
    stem = c['mapa']; i = c['i']
    if stem not in cache:
        cache[stem] = (json.load(open(S + f'out/{stem}.json')), json.load(open(S + f'out/{stem}.geocoded.json')), Image.open(S + f'in/{stem}.jpg').convert('RGB'))
    spot, geo, im = cache[stem]
    words = {w['id']: w for w in spot['words']}
    if c['veredicto'] == 'ilegible': continue
    text = c['ocr'] if c['veredicto'] == 'correcto' else c['texto']
    if not text: continue
    if c.get('nuevo'):      # a label the reader missed: axis-aligned box drawn by the user, no word polygons
        x0, y0, x1, y1 = c['bbox_px']
        ph = {'bbox': [x0, y0, x1, y1], 'angle': 0, 'h': max(8, y1 - y0), 'words': [], 'pred_lon': c.get('lon_pred'), 'pred_lat': c.get('lat_pred')}
        words['_n'] = {'poly': [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]}; ph['words'] = ['_n']
    else:
        ph = geo['phrases'][int(i)]
    # straightened crop along the phrase direction: rotate the full-res region around the phrase centre by its angle
    x0, y0, x1, y1 = ph['bbox']; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ang = ph.get('angle', 0) or 0; ar = math.radians(ang)
    ux, uy = math.cos(ar), -math.sin(ar); nx, ny = math.sin(ar), math.cos(ar)      # reading axis and its normal, image coords (y down)
    pts = [p for w in ph['words'] for p in words[w]['poly']]
    ss = [(px - cx) * ux + (py - cy) * uy for px, py in pts]; ts = [(px - cx) * nx + (py - cy) * ny for px, py in pts]
    h = max(ts) - min(ts); m = max(4, 0.25 * h)
    pad = int(math.hypot(max(abs(min(ss)), abs(max(ss))) + m, max(abs(min(ts)), abs(max(ts))) + m) + 6)
    region = im.crop((int(cx - pad), int(cy - pad), int(cx + pad), int(cy + pad)))
    if abs(ang) > 1.5: region = region.rotate(-ang, resample=Image.BICUBIC, expand=False, fillcolor=(235, 225, 200))
    rc = region.size[0] / 2
    crop = region.crop((int(rc + min(ss) - m), int(rc + min(ts) - m), int(rc + max(ss) + m), int(rc + max(ts) + m)))
    fn = f'{stem}-{i}.png'
    if c['veredicto'] in ('correcto', 'corregido'):
        crop.save(a.out + '/recognition/images/' + fn); labels[fn] = text
    det.setdefault(stem, {'img_dimensions': [spot['width'], spot['height']], 'polygons': [], 'negatives': []})
    polys = [words[w]['poly'] for w in ph['words']]
    (det[stem]['negatives'] if c['veredicto'] == 'no-toponimo' else det[stem]['polygons']).extend(polys)
    if c['veredicto'] == 'corregido' and c.get('tipo') in ('poblado', 'rio', 'quebrada', 'cerro', 'agua', 'region') and norm(text) not in gaznorm:
        supp.append([text, c.get('tipo'), ph.get('pred_lon'), ph.get('pred_lat'), stem, c.get('codigo'), c.get('ocr')])
json.dump(labels, open(a.out + '/recognition/labels.json', 'w'), ensure_ascii=False, indent=1)
for stem, d in det.items():
    json.dump({stem + '.jpg': {'img_dimensions': d['img_dimensions'], 'polygons': d['polygons']}}, open(a.out + f'/detection/{stem}.json', 'w'))
with open(a.out + '/gacetero_suplemento.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['nombre', 'tipo', 'lon_estimada', 'lat_estimada', 'mapa', 'codigo', 'texto_ocr']); w.writerows(supp)
print(f'{len(labels)} recognition samples, {sum(len(d["polygons"]) for d in det.values())} detection polygons, {len(supp)} gazetteer supplements -> {a.out}')
