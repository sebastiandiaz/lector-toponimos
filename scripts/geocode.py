"""Post-OCR + geocoding for one spotted map (mapKurator-style, CPU only).

  python3 -I geocode.py out/m01.json m01 --bbox w,s,e,n

1. normalises OCR phrases (accents, abbreviations), fuzzy-matches them against the regional gazetteer (rapidfuzz, accent-insensitive)
2. RANSAC affine fit image(x,y) -> (lon,lat) over point candidates; iterative re-assignment of ambiguous names by spatial consistency
3. attaches line/polygon features (rivers, departments, seas) by proximity to the predicted location
4. writes <stem>.geocoded.json, <stem>.toponimos.csv, <stem>.geojson, <stem>.gcps.csv
"""
import json, re, math, csv, sys, random, argparse, unicodedata
import numpy as np
from rapidfuzz import fuzz, process
from shapely import wkt
from shapely.geometry import Point, Polygon, mapping, MultiPoint, LineString

ap = argparse.ArgumentParser()
ap.add_argument('spot'); ap.add_argument('stem')
ap.add_argument('--bbox', default='', help='inventory bbox w,s,e,n (prior; candidates restricted to a window 2.5x larger)')
ap.add_argument('--gaz', default='./gaz/gazetteer.json')
ap.add_argument('--outdir', default='./out')
ap.add_argument('--tol', type=float, default=6.0, help='inlier tolerance in km for control points')
ap.add_argument('--seed', type=int, default=7)
args = ap.parse_args()
random.seed(args.seed); np.random.seed(args.seed)

def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

ABBR = {'r': 'rio', 'ro': 'rio', 'rio': 'rio', 'q': 'quebrada', 'qa': 'quebrada', 'qda': 'quebrada', 'qbda': 'quebrada', 'queb': 'quebrada',
        's': 'san', 'sn': 'san', 'sta': 'santa', 'sto': 'santo', 'pto': 'puerto', 'po': 'puerto', 'pta': 'punta', 'ba': 'bahia', 'bah': 'bahia',
        'ensa': 'ensenada', 'ens': 'ensenada', 'ia': 'isla', 'is': 'isla', 'lag': 'laguna', 'laga': 'laguna', 'cga': 'cienaga', 'cien': 'cienaga',
        'co': 'cerro', 'cno': 'cano', 'pmo': 'paramo', 'serr': 'serrania', 'sa': 'sierra', 'va': 'villa', 'na': 'nuestra', 'ns': 'nuestra senora',
        'prov': 'provincia', 'prova': 'provincia', 'ter': 'territorio', 'terr': 'territorio', 'dpto': 'departamento', 'est': 'estado', 'edo': 'estado'}
TYPE_WORDS = {'rio', 'quebrada', 'cano', 'cerro', 'cerros', 'alto', 'cuchilla', 'serrania', 'sierra', 'paramo', 'punta', 'puerto', 'bahia',
              'ensenada', 'golfo', 'isla', 'islas', 'laguna', 'cienaga', 'boca', 'bocas', 'mesa', 'pico', 'nevado', 'volcan', 'salto',
              'llano', 'llanos', 'sabana', 'sabanas', 'valle', 'cabo', 'estero', 'mar', 'oceano', 'lago', 'playa', 'morro', 'loma', 'lomas',
              'hato', 'villa', 'pueblo', 'provincia', 'estado', 'departamento', 'territorio', 'canton', 'distrito', 'peninsula', 'cordillera',
              'region', 'arroyo', 'brazo', 'embalse', 'archipielago', 'costa'}
ARTICLES = {'de', 'del', 'la', 'el', 'las', 'los'}
GENERIC = {'oriental', 'central', 'occidental', 'norte', 'sur', 'este', 'oeste', 'grande', 'nuevo', 'nueva', 'santa', 'san', 'alto', 'alta', 'bajo', 'baja', 'rios', 'nacional', 'isla', 'valle', 'paramo', 'andes', 'negro', 'blanco', 'verde', 'seco', 'seca', 'salado', 'dulce', 'chico', 'viejo', 'vieja', 'real', 'colombia', 'mar', 'tierra', 'tierras', 'pacifico', 'atlantico', 'antillas', 'meridiano', 'provincia', 'canton', 'territorio', 'distrito', 'estado', 'capital', 'limite', 'limites', 'longitud', 'latitud', 'escala', 'leguas', 'millas', 'varas', 'camino', 'caminos', 'puente', 'hacienda', 'cerro', 'cerros', 'quebrada', 'rio', 'laguna', 'cienaga', 'golfo', 'bahia', 'punta', 'puerto', 'boca', 'bocas', 'sierra', 'cordillera', 'serrania', 'llano', 'llanos', 'sabana', 'sabanas', 'mesa', 'pico', 'nevado', 'volcan', 'salto', 'cabo', 'estero', 'oceano', 'lago', 'playa', 'morro', 'loma', 'lomas', 'hato', 'villa', 'pueblo', 'peninsula', 'region', 'arroyo', 'brazo', 'cano', 'embalse', 'costa', 'indios', 'tabla', 'cuadro', 'poblacion', 'habitantes', 'distancia', 'distancias', 'temperatura', 'altura', 'metros', 'pies', 'grados', 'bogota'}

def expand(n):
    return ' '.join(ABBR.get(t, t) for t in n.split())
def core(n):
    t = n.split()
    while len(t) > 1 and (t[0] in TYPE_WORDS or t[0] in ARTICLES): t = t[1:]
    return ' '.join(t)
def query_variants(text):
    n = norm(text)
    out = []
    for v in (n, expand(n)):
        if v and v not in out: out.append(v)
        c = core(v)
        if len(c) >= 4 and c not in out: out.append(c)
    return [v for v in out if re.search(r'[a-z]{3,}', v) and v not in GENERIC]
def thr_for(L):
    return 100 if L <= 3 else 88 if L == 4 else 80 if L == 5 else 77 if L <= 7 else 72

# ---------------- gazetteer ----------------
gaz = json.load(open(args.gaz))['entries']
geoms = {}
for i, e in enumerate(gaz):
    if 'geom' in e: geoms[i] = wkt.loads(e['geom'])
win = None
if args.bbox:
    w, s, e_, n_ = [float(x) for x in args.bbox.split(',')]
    dx, dy = (e_ - w), (n_ - s)
    win = (w - 1.25*dx, s - 1.25*dy, e_ + 1.25*dx, n_ + 1.25*dy)
def in_window(e):
    if win is None: return True
    if e['type'] in ('pop',) and 'lon' in e:
        return win[0] <= e['lon'] <= win[2] and win[1] <= e['lat'] <= win[3]
    return True   # areas/lines are checked by geometry later
choices, choice_entry = [], []
for i, e in enumerate(gaz):
    if not in_window(e): continue
    for v in e['variants']:
        choices.append(v); choice_entry.append(i)
print(f'gazetteer: {len(gaz)} entries, {len(choices)} variant strings in window', flush=True)

# ---------------- OCR phrases ----------------
spot = json.load(open(args.spot))
W, H = spot['width'], spot['height']
words = {w['id']: w for w in spot['words']}
phrases = spot['phrases']

def match_text(text):
    """return list of candidates [(entry_idx, score, variant, query)] for a text; best per entry."""
    best = {}
    for q in query_variants(text):
        if len(q) < 3: continue
        res = process.extract(q, choices, scorer=fuzz.ratio, limit=12, score_cutoff=70)
        for v, sc, idx in res:
            L = min(len(q), len(v))
            if sc < thr_for(L): continue
            # short query matched to a much longer name (or vice versa) is weak: penalise length mismatch
            if abs(len(q) - len(v)) > max(2, 0.4*max(len(q), len(v))): continue
            ei = choice_entry[idx]
            # a core-only match ('gil' part of 'san gil') is fine but should not outrank full matches
            sc_adj = sc - (6 if (q == core(q) and q != norm(text) and q != expand(norm(text))) else 0)
            if ei not in best or sc_adj > best[ei][1]:
                best[ei] = (ei, sc_adj, v, q)
    return sorted(best.values(), key=lambda t: -t[1])[:8]

cands = []    # per phrase: list of candidate tuples
for p in phrases:
    txt = p['text']
    digits = sum(c.isdigit() for c in txt); letters = sum(c.isalpha() for c in txt)
    if letters < 3 or digits > letters: cands.append([]); continue
    c = match_text(txt)
    # fall back to sub-spans of multi-word phrases
    if (not c or c[0][1] < 90) and 2 <= len(p['words']) <= 4:
        toks = [words[i]['text'] for i in p['words']]
        for a in range(len(toks)):
            for b in range(a+1, len(toks)+1):
                if b - a == len(toks): continue
                sub = ' '.join(toks[a:b])
                if sum(ch.isalpha() for ch in sub) < 4: continue
                for t in match_text(sub):
                    t = (t[0], t[1] - 3, t[2], t[3])   # slight penalty for partial phrase
                    if not any(x[0] == t[0] and x[1] >= t[1] for x in c): c.append(t)
        c = sorted({x[0]: x for x in sorted(c, key=lambda t: t[1])}.values(), key=lambda t: -t[1])[:8]
    cands.append(c)
n_lex = sum(1 for c in cands if c)
print(f'{len(phrases)} phrases, {n_lex} with a lexical candidate', flush=True)

# ---------------- RANSAC affine ----------------
KM_LAT = 111.32
def km_dist(lon1, lat1, lon2, lat2):
    return np.hypot((lon1 - lon2) * KM_LAT * np.cos(np.radians((lat1 + lat2) / 2)), (lat1 - lat2) * KM_LAT)
def fit_affine(xy, ll):
    A = np.hstack([xy, np.ones((len(xy), 1))])
    M, *_ = np.linalg.lstsq(A, ll, rcond=None)      # 3x2
    return M
def apply(M, xy):
    return np.hstack([xy, np.ones((len(xy), 1))]) @ M
def predict(xy):
    xy = np.asarray(xy, dtype=float)
    if poly_Q is not None:
        x = (xy[:, 0] - W/2) / W; y = (xy[:, 1] - H/2) / H
        return np.column_stack([np.ones_like(x), x, y, x*x, x*y, y*y]) @ poly_Q
    return apply(transform, xy)

# point candidate table
P = []   # rows: (phrase_idx, entry_idx, score, cx, cy, lon, lat)
for pi, c in enumerate(cands):
    for (ei, sc, v, q) in c:
        e = gaz[ei]
        if e['type'] == 'pop' or (e['src'] == 'manual' and e['type'] == 'pop'):
            P.append((pi, ei, sc, phrases[pi]['cx'], phrases[pi]['cy'], e['lon'], e['lat']))
P = np.array(P, dtype=float)
print(f'{len(P)} point (phrase, candidate) pairs from {len(set(P[:,0])) if len(P) else 0} phrases', flush=True)

best = None
if len(P) >= 6:
    xy = P[:, 3:5]; ll = P[:, 5:7]; pidx = P[:, 0].astype(int)
    strong = np.where(P[:, 2] >= 85)[0]
    pool = strong if len(strong) >= 8 else np.arange(len(P))
    uniq_phr = np.unique(pidx[pool])
    iters = 4000
    for it in range(iters):
        phr = np.random.choice(uniq_phr, 3, replace=False)
        rows = [np.random.choice(pool[pidx[pool] == ph]) for ph in phr]
        sxy = xy[rows]; sll = ll[rows]
        # degenerate (collinear) samples
        area = abs((sxy[1,0]-sxy[0,0])*(sxy[2,1]-sxy[0,1]) - (sxy[2,0]-sxy[0,0])*(sxy[1,1]-sxy[0,1]))
        if area < 0.002 * W * H: continue
        try: M = np.linalg.solve(np.hstack([sxy, np.ones((3, 1))]), sll)
        except np.linalg.LinAlgError: continue
        # sanity: degrees per pixel between 1e-5 and 5e-3 and reasonable orientation (north roughly up, not mirrored)
        sx = np.hypot(M[0,0], M[0,1]); sy = np.hypot(M[1,0], M[1,1])
        if not (1e-5 < sx < 5e-3 and 1e-5 < sy < 5e-3): continue
        if M[0,0] <= 0 or M[1,1] >= 0: continue          # x -> east, y(down) -> south
        if not (0.4 < sx / sy < 2.5): continue
        pred = apply(M, xy)
        d = km_dist(pred[:, 0], pred[:, 1], ll[:, 0], ll[:, 1])
        ok = d < args.tol
        # one inlier per phrase (its nearest candidate)
        inl_phr = set(pidx[ok])
        score = len(inl_phr)
        if best is None or score > best[0]:
            best = (score, M, it)
    print('RANSAC: ' + (f'best sample has {best[0]} inlier phrases (iteration {best[2]})' if best else 'no valid sample'), flush=True)

transform = None; gcps = []; poly_Q = None
tol_km = args.tol
if best and best[0] >= 5:
    M = best[1]
    # tolerance in km scaled to the map: at least args.tol, or 120 px of the sheet (so 1:810 000 sheets are not judged like 1:340 000 ones)
    tol_km = min(15.0, max(args.tol, 120 * float(np.hypot(M[1,0], M[1,1]) * KM_LAT)))
    print(f'tolerance: {tol_km:.1f} km', flush=True)
    for rnd, tol in enumerate([tol_km, tol_km * 0.8, tol_km * 0.6]):
        pred = apply(M, P[:, 3:5]); d = km_dist(pred[:, 0], pred[:, 1], P[:, 5], P[:, 6])
        chosen = {}
        for r in range(len(P)):
            if d[r] < tol:
                ph = int(P[r, 0])
                if ph not in chosen or d[r] < chosen[ph][1]: chosen[ph] = (r, d[r])
        rows = [v[0] for v in chosen.values()]
        if len(rows) < 4: break
        M = fit_affine(P[rows, 3:5], P[rows, 5:7])
        pred = apply(M, P[rows, 3:5]); res = km_dist(pred[:, 0], pred[:, 1], P[rows, 5], P[rows, 6])
        print(f'  round {rnd}: tol {tol:.1f} km -> {len(rows)} control points, RMSE {np.sqrt(np.mean(res**2)):.2f} km', flush=True)
    transform = M
    gcps = [(int(P[r, 0]), int(P[r, 1]), float(P[r, 2]), float(res[k])) for k, r in enumerate(rows)]
    # --- degree-2 polynomial refinement: absorbs the smooth distortions of compiled 19th-century maps ---
    def poly_feats(xy):
        x = (xy[:, 0] - W/2) / W; y = (xy[:, 1] - H/2) / H
        return np.column_stack([np.ones_like(x), x, y, x*x, x*y, y*y])
    pred = apply(M, P[:, 3:5]); d = km_dist(pred[:, 0], pred[:, 1], P[:, 5], P[:, 6])
    chosen = {}
    for r in range(len(P)):
        if d[r] < tol_km * 2.5:
            ph = int(P[r, 0])
            if ph not in chosen or d[r] < chosen[ph][1]: chosen[ph] = (r, d[r])
    rows2 = [v[0] for v in chosen.values()]
    if len(rows2) >= 14:
        Q, *_ = np.linalg.lstsq(poly_feats(P[rows2, 3:5]), P[rows2, 5:7], rcond=None)
        for rnd in range(2):
            predq = poly_feats(P[:, 3:5]) @ Q; dq = km_dist(predq[:, 0], predq[:, 1], P[:, 5], P[:, 6])
            chosen = {}
            for r in range(len(P)):
                if dq[r] < tol_km:
                    ph = int(P[r, 0])
                    if ph not in chosen or dq[r] < chosen[ph][1]: chosen[ph] = (r, dq[r])
            rows3 = [v[0] for v in chosen.values()]
            if len(rows3) < 14: break
            Q, *_ = np.linalg.lstsq(poly_feats(P[rows3, 3:5]), P[rows3, 5:7], rcond=None)
            predq = poly_feats(P[rows3, 3:5]) @ Q; resq = km_dist(predq[:, 0], predq[:, 1], P[rows3, 5], P[rows3, 6])
            print(f'  poly2 round {rnd}: {len(rows3)} control points, RMSE {np.sqrt(np.mean(resq**2)):.2f} km', flush=True)
        if len(rows3) >= 14 and len(rows3) >= len(rows):
            gcps = [(int(P[r, 0]), int(P[r, 1]), float(P[r, 2]), float(resq[k])) for k, r in enumerate(rows3)]
            poly_Q = Q

# ---------------- assign matches ----------------
results = []
gcp_by_phrase = {ph: (ei, sc, rs) for ph, ei, sc, rs in gcps}
for pi, p in enumerate(phrases):
    r = {'text': p['text'], 'conf': p['conf'], 'cx': p['cx'], 'cy': p['cy'], 'bbox': p['bbox'], 'angle': p['angle'], 'h': p['h'], 'words': p['words'],
         'status': 'none', 'match': None}
    if pi in gcp_by_phrase:
        ei, sc, rs = gcp_by_phrase[pi]; e = gaz[ei]
        r['status'] = 'gcp'; r['match'] = {'name': e['name'], 'type': e['type'], 'lon': e['lon'], 'lat': e['lat'], 'score': sc, 'residual_km': round(rs, 2), 'src': e['src']}
    elif cands[pi]:
        # try area / line features by proximity to the predicted location; else best lexical only
        chosen = None
        if transform is not None:
            lon, lat = predict([[p['cx'], p['cy']]])[0]
            pt = Point(lon, lat)
            TYPE_RANK = {'pop': 0, 'river': 1, 'lake': 2, 'marine': 2, 'region': 3, 'admin1': 4}
            for (ei, sc, v, q) in sorted(cands[pi], key=lambda t: (-t[1], TYPE_RANK.get(gaz[t[0]]['type'], 5))):
                e = gaz[ei]
                if e['type'] == 'pop':
                    dkm = km_dist(lon, lat, e['lon'], e['lat'])
                    lim = min(30.0, tol_km * 2.5)
                    if dkm < lim: chosen = (e, sc, 'near', float(dkm)); break
                else:
                    typed = re.match(r'^(r|rio|q|quebrada|cano|golfo|bahia|laguna|cienaga|lago|mar|oceano|sierra|serrania|cordillera|paramo|provincia|estado|territorio|canton|isla|cabo|punta)\b', expand(norm(p['text'])))
                    if sc < (80 if typed else 88): continue
                    g = geoms.get(ei)
                    if g is not None:
                        dd = g.distance(pt) * KM_LAT    # rough km
                        lim = 12 if e['type'] == 'river' else 25 if e['type'] in ('lake', 'marine') else 40
                        if dd < lim: chosen = (e, sc, 'area', float(dd)); break
                    elif 'lon' in e:
                        dkm = km_dist(lon, lat, e['lon'], e['lat'])
                        lim = 40 if e['type'] in ('river', 'region', 'marine', 'lake') else 80
                        if dkm < lim: chosen = (e, sc, 'area', float(dkm)); break
        if chosen:
            e, sc, st, dkm = chosen
            r['status'] = st
            r['match'] = {'name': e['name'], 'type': e['type'], 'lon': e.get('lon'), 'lat': e.get('lat'), 'score': sc, 'residual_km': round(dkm, 2), 'src': e['src']}
        else:
            ei, sc, v, q = cands[pi][0]; e = gaz[ei]
            r['status'] = 'lexical'
            r['match'] = {'name': e['name'], 'type': e['type'], 'lon': e.get('lon'), 'lat': e.get('lat'), 'score': sc, 'src': e['src'],
                          'alternatives': [gaz[c[0]]['name'] for c in cands[pi][1:4]]}
    if transform is not None:
        lon, lat = predict([[p['cx'], p['cy']]])[0]
        r['pred_lon'] = round(float(lon), 5); r['pred_lat'] = round(float(lat), 5)
    results.append(r)

# ---------------- second pass: spatially primed matching of misread labels ----------------
# with the transform known, a label that was read badly can still be matched if a place with a similar name lies where the label sits
n_spatial = 0
if transform is not None:
    pts = [(i, e) for i, e in enumerate(gaz) if e['type'] == 'pop' and 'lon' in e]
    from shapely.strtree import STRtree
    ptree = STRtree([Point(e['lon'], e['lat']) for i, e in pts])
    for pi, r in enumerate(results):
        if r['status'] in ('gcp', 'near', 'area'): continue
        qv = query_variants(r['text'])
        if not qv or max(len(v) for v in qv) < 5: continue
        lon, lat = predict([[r['cx'], r['cy']]])[0]
        rad = max(10.0, tol_km * 1.7)
        dlon = rad / (KM_LAT * math.cos(math.radians(lat))); dlat = rad / KM_LAT
        hits = ptree.query(Point(lon, lat).buffer(max(dlon, dlat)))
        bestc = None
        for j in hits:
            e = pts[int(j)][1]
            dkm = km_dist(lon, lat, e['lon'], e['lat'])
            if dkm > rad: continue
            for q in qv:
                for v in e['variants']:
                    if len(v) < 4: continue
                    sc = fuzz.ratio(q, v)
                    thr = 75 if min(len(q), len(v)) <= 5 else 68
                    if sc >= thr and (bestc is None or sc - 20*dkm/rad > bestc[0] - 20*bestc[2]/rad):
                        bestc = (sc, e, dkm)
        if bestc:
            sc, e, dkm = bestc
            r['status'] = 'near'; n_spatial += 1
            r['match'] = {'name': e['name'], 'type': e['type'], 'lon': e['lon'], 'lat': e['lat'], 'score': round(float(sc), 1), 'residual_km': round(float(dkm), 2), 'src': e['src'], 'via': 'espacial'}
    print(f'spatially primed matching: {n_spatial} more labels', flush=True)

# ---------------- feature hints: a label that names a river/lake/island/peak matched to a homonymous town ----------------
HINT = {'rio': 'río', 'quebrada': 'quebrada', 'cano': 'caño', 'laguna': 'laguna', 'cienaga': 'ciénaga', 'isla': 'isla', 'punta': 'punta', 'volcan': 'volcán',
        'cerro': 'cerro', 'golfo': 'golfo', 'bahia': 'bahía', 'ensenada': 'ensenada', 'cabo': 'cabo', 'paramo': 'páramo', 'alto': 'alto', 'sierra': 'sierra', 'serrania': 'serranía', 'boca': 'boca', 'bocas': 'bocas', 'puerto': 'puerto', 'hato': 'hato', 'mina': 'mina', 'minas': 'minas'}
for r in results:
    m = r['match']
    if not m: continue
    t = expand(norm(r['text'])).split()
    if t and t[0] in HINT and m['type'] == 'pop' and t[0] not in ('puerto', 'hato'):
        m['tipo_rotulo'] = HINT[t[0]]
n_hint = sum(1 for r in results if r['match'] and r['match'].get('tipo_rotulo'))

# ---------------- footprint estimates ----------------
summary = {'stem': args.stem, 'image': spot['image'], 'width': W, 'height': H, 'spot_seconds': spot.get('seconds'), 'n_words': len(spot['words']),
           'n_phrases': len(phrases), 'n_lexical_candidates': n_lex,
           'n_gcp': sum(1 for r in results if r['status'] == 'gcp'), 'n_near': sum(1 for r in results if r['status'] == 'near'),
           'n_area': sum(1 for r in results if r['status'] == 'area'), 'n_lexical_only': sum(1 for r in results if r['status'] == 'lexical'), 'n_spatial': n_spatial, 'n_tipo_rotulo': n_hint}
if transform is not None:
    M = transform
    res = np.array([g[3] for g in gcps])
    summary['rmse_km'] = round(float(np.sqrt(np.mean(res**2))), 2); summary['tol_km'] = round(float(tol_km), 1)
    summary['deg_per_px'] = [round(float(np.hypot(M[0,0], M[0,1])), 7), round(float(np.hypot(M[1,0], M[1,1])), 7)]
    summary['m_per_px'] = round(float(np.hypot(M[1,0], M[1,1]) * KM_LAT * 1000), 1)
    summary['rotation_deg'] = round(float(math.degrees(math.atan2(M[0,1], M[0,0]))), 2)
    corners = predict(np.array([[0, 0], [W, 0], [W, H], [0, H]], dtype=float))
    summary['image_extent'] = [round(float(corners[:,0].min()), 4), round(float(corners[:,1].min()), 4), round(float(corners[:,0].max()), 4), round(float(corners[:,1].max()), 4)]
    pts = [(r['match']['lon'], r['match']['lat']) for r in results if r['status'] in ('gcp', 'near')]
    if pts:
        a = np.array(pts); summary['toponym_extent'] = [round(float(a[:,0].min()), 4), round(float(a[:,1].min()), 4), round(float(a[:,0].max()), 4), round(float(a[:,1].max()), 4)]
    summary['transform'] = M.tolist(); summary['model'] = 'poly2' if poly_Q is not None else 'affine'
    if poly_Q is not None: summary['poly2'] = poly_Q.tolist()
if args.bbox: summary['inventory_bbox'] = [float(x) for x in args.bbox.split(',')]
print(json.dumps({k: v for k, v in summary.items() if k != 'transform'}, ensure_ascii=False), flush=True)

out = args.outdir + '/' + args.stem
json.dump({'summary': summary, 'phrases': results}, open(out + '.geocoded.json', 'w'), ensure_ascii=False)
with open(out + '.toponimos.csv', 'w', newline='') as f:
    wr = csv.writer(f); wr.writerow(['texto_ocr', 'confianza', 'x', 'y', 'angulo', 'estado', 'nombre_gacetero', 'tipo', 'lon', 'lat', 'score', 'residuo_km', 'fuente', 'lon_pred', 'lat_pred'])
    for r in results:
        m = r['match'] or {}
        wr.writerow([r['text'], r['conf'], r['cx'], r['cy'], r['angle'], r['status'], m.get('name', ''), m.get('type', ''), m.get('lon', ''), m.get('lat', ''), m.get('score', ''), m.get('residual_km', ''), m.get('src', ''), r.get('pred_lon', ''), r.get('pred_lat', '')])
feats = []
for r in results:
    if r['status'] in ('gcp', 'near', 'area') and r['match'] and r['match'].get('lon') is not None:
        feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [r['match']['lon'], r['match']['lat']]},
                      'properties': {'texto_ocr': r['text'], 'nombre': r['match']['name'], 'tipo': r['match']['type'], 'estado': r['status'], 'score': r['match']['score'], 'residuo_km': r['match'].get('residual_km'), 'x': r['cx'], 'y': r['cy']}})
if transform is not None:
    corners = predict(np.array([[0, 0], [W, 0], [W, H], [0, H], [0, 0]], dtype=float)).tolist()
    feats.append({'type': 'Feature', 'geometry': {'type': 'Polygon', 'coordinates': [corners]}, 'properties': {'tipo': 'extension_imagen_estimada'}})
with open(out + '.geojson', 'w') as f: json.dump({'type': 'FeatureCollection', 'features': feats}, f, ensure_ascii=False)
with open(out + '.gcps.csv', 'w', newline='') as f:
    wr = csv.writer(f); wr.writerow(['x', 'y', 'lon', 'lat', 'nombre', 'texto_ocr', 'residuo_km'])
    for r in results:
        if r['status'] == 'gcp': wr.writerow([r['cx'], r['cy'], r['match']['lon'], r['match']['lat'], r['match']['name'], r['text'], r['match']['residual_km']])
print('written', out + '.{geocoded.json,toponimos.csv,geojson,gcps.csv}', flush=True)
