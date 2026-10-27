"""Build the standalone viewer for the mapKurator-style pilot: one HTML with the ten maps, their recognised labels,
the gazetteer matches and the geocoding result, in the visual system of the Mapoteca Digital.

python3 -I viewer.py  -> ./index.html
"""
import json, base64, io, os, html
from PIL import Image
from shapely.geometry import shape, box, mapping
Image.MAX_IMAGE_PIXELS = None

S = './'
O = S + 'ocrpilot/out/'
meta = json.load(open(S + 'ocrpilot/maps_meta.json'))
evals = json.load(open(S + 'ocrpilot/eval.json')) if os.path.exists(S + 'ocrpilot/eval.json') else {}
MAXDIM = 2000

maps = []
for stem in sorted(meta):
    fn = O + stem + '.geocoded.json'
    if not os.path.exists(fn): continue
    d = json.load(open(fn)); sm = d['summary']
    spot = json.load(open(O + stem + '.json')); words = {w['id']: w for w in spot['words']}
    im = Image.open(S + 'ocrpilot/in/' + stem + '.jpg').convert('RGB')
    W, H = im.size; sc = min(1.0, MAXDIM / max(W, H))
    th = im.resize((round(W*sc), round(H*sc)), Image.LANCZOS)
    buf = io.BytesIO(); th.save(buf, 'JPEG', quality=72, optimize=True)
    uri = 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
    ph = []
    for i, r in enumerate(d['phrases']):
        m = r['match'] or {}
        polys = [[[round(x), round(y)] for (x, y) in words[wid]['poly']] for wid in r['words']]
        ph.append({'i': i, 't': r['text'], 'c': r['conf'], 's': r['status'], 'n': m.get('name', ''), 'ty': m.get('type', ''), 'hint': m.get('tipo_rotulo'), 'sc': round(m['score'], 0) if m.get('score') is not None else None,
                   'r': m.get('residual_km'), 'lon': m.get('lon'), 'lat': m.get('lat'), 'alt': m.get('alternatives', []),
                   'b': [round(v) for v in r['bbox']], 'p': polys, 'a': r['angle'], 'pl': r.get('pred_lon'), 'pt': r.get('pred_lat')})
    tiles_idx = json.load(open('./tiles/index.json')) if os.path.exists('./tiles/index.json') else {}
    maps.append({'stem': stem, 'meta': meta[stem], 'summary': sm, 'img': uri, 'w': W, 'h': H, 'scale': 1.0, 'tiles': tiles_idx.get(stem), 'phrases': ph, 'eval': evals.get(stem)})
    print(stem, 'image', th.size, len(uri)//1024, 'KB', len(ph), 'phrases')

# regional basemap
b = json.load(open(S + 'basemap.json'))
roi = box(-84.5, -5.5, -66, 14.5)
def clip(fc, props=()):
    out = []
    for f in fc['features']:
        try: g = shape(f['geometry'])
        except Exception: continue
        if not g.intersects(roi): continue
        g = g.intersection(roi).simplify(0.015)
        if g.is_empty: continue
        out.append({'type': 'Feature', 'geometry': mapping(g), 'properties': {k: f.get('properties', {}).get(k) for k in props}})
    return {'type': 'FeatureCollection', 'features': out}
base = {'countries': clip(b['countries'], ('n',)), 'depts': clip(b['depts'], ('n',)), 'rivers': clip(b['rivers'], ('n',)), 'lakes': clip(b['lakes'])}
places = [p for p in b['places'] if -84.5 < p[1] < -66 and -5.5 < p[2] < 14.5 and p[3] <= 8]
contours = open(S + 'contours.uri').read().strip()

def esc(s): return json.dumps(s, ensure_ascii=False).replace('</', '<\\/')

page = r'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lector de topónimos (piloto)</title>
<meta name="description" content="Lectura automática de topónimos y geocodificación de diez mapas de la Comisión Corográfica (Mapoteca Digital, BNC)">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=IBM+Plex+Sans:ital,wght@0,300;0,400;0,500;0,600;1,400&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>__LEAFLET_CSS__</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>
:root{--bg:#EDE8DF;--panel:#F4F1EB;--panel-2:#E6E0D5;--ink:#1A1815;--ink-2:#4a4640;--ink-3:#847e76;--line:#d9d3c8;--line-strong:#bdb6aa;--brand:#2B4A7A;--accent:#2B4A7A;--accent-dark:#1f3a63;--accent-soft:#E8EDF5;--accent-text:#2B4A7A;--gold:#C49A1E;--mark:#C49A1E;--sea:#e3e6e4;--land:#F4F1EB;--land-line:#bdb6aa;--river:#9fb3c4;
 --gcp:#2f8a3e;--near:#1f9e9e;--area:#3b6fd1;--lex:#e08a1e;--none:#8292a7;
 --font-display:'Barlow Condensed','Arial Narrow',sans-serif;--font-ui:'IBM Plex Sans',Arial,sans-serif;--font-mono:'IBM Plex Mono',ui-monospace,Menlo,monospace;--radius:6px}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#1A1815;--panel:#242019;--panel-2:#2e2922;--ink:#EDE8DF;--ink-2:#cfc8bc;--ink-3:#9b948a;--line:#3b362f;--line-strong:#4f4941;--brand:#EDE8DF;--accent:#7f9fd0;--accent-dark:#9ab4dd;--accent-soft:#2a3a55;--accent-text:#9fb8e0;--gold:#d9b24a;--mark:#d9b24a;--sea:#15191c;--land:#242019;--land-line:#4f4941;--river:#3f5366;--gcp:#7fd484;--near:#5fd3d3;--area:#86aaf0;--lex:#f3b35a;--none:#9b948a;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#1A1815;--panel:#242019;--panel-2:#2e2922;--ink:#EDE8DF;--ink-2:#cfc8bc;--ink-3:#9b948a;--line:#3b362f;--line-strong:#4f4941;--brand:#EDE8DF;--accent:#7f9fd0;--accent-dark:#9ab4dd;--accent-soft:#2a3a55;--accent-text:#9fb8e0;--gold:#d9b24a;--mark:#d9b24a;--sea:#15191c;--land:#242019;--land-line:#4f4941;--river:#3f5366;--gcp:#7fd484;--near:#5fd3d3;--area:#86aaf0;--lex:#f3b35a;--none:#9b948a;color-scheme:dark}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font-ui);font-size:14px;line-height:1.45;-webkit-font-smoothing:antialiased}
a{color:var(--accent-text)}button,input,select{font:inherit;color:inherit}:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
[hidden]{display:none!important}
.mono{font-family:var(--font-mono);font-variant-numeric:tabular-nums}
.lbl{font-size:10.5px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.mast{position:sticky;top:0;z-index:50;display:flex;align-items:center;gap:20px;padding:0 22px;min-height:66px;color:var(--ink);border-bottom:1px solid var(--line);
 background:linear-gradient(color-mix(in srgb,var(--bg) 93%,transparent),color-mix(in srgb,var(--bg) 93%,transparent)),url("__CCDBG__") center/cover;backdrop-filter:blur(6px)}
.ccd{display:flex;align-items:center;gap:14px;flex-shrink:0;text-decoration:none;color:var(--ink)}
.ccd svg{display:block;height:34px;width:auto;overflow:visible}
.ccd-div{width:1px;height:26px;background:var(--accent);opacity:.5;flex-shrink:0}
.ccd-name{display:flex;flex-direction:column;font-family:var(--font-ui);text-transform:uppercase;font-size:10px;letter-spacing:2px;line-height:1.5}
.ccd-name span:first-child{font-weight:600;color:var(--ink)}.ccd-name span:last-child{font-weight:300;color:var(--ink-3)}
.tool{display:flex;align-items:baseline;gap:12px;flex:1 1 auto;min-width:0;padding-left:20px;border-left:1px solid var(--line)}
.tool h1{font-family:var(--font-display);font-weight:800;font-size:30px;margin:0;line-height:1;letter-spacing:-.01em;white-space:nowrap;color:var(--ink)}
.tool h1 .pil{font-weight:600;color:var(--ink-3);font-size:.72em;letter-spacing:0}
.tool .tagline{font-size:12.5px;color:var(--ink-3);white-space:nowrap;min-width:0;overflow:hidden;text-overflow:ellipsis}
.credits{margin-left:8px;flex-shrink:0;display:flex;flex-direction:column;align-items:flex-end;gap:2px;text-align:right}
.coll{font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:var(--ink-3);text-decoration:none;white-space:nowrap}
.coll:hover{color:var(--accent)}
.dev{font-size:11px;letter-spacing:.4px;color:var(--ink-2);white-space:nowrap}
.dev-k{font-size:9.5px;letter-spacing:1.5px;text-transform:uppercase;color:var(--ink-3);margin-right:6px}
.tabs{display:flex;gap:2px}
.tabs button{border:0;background:none;padding:8px 10px;border-bottom:2px solid transparent;color:var(--ink-3);cursor:pointer;font-family:var(--font-ui);font-size:12px;font-weight:500;letter-spacing:1.5px;text-transform:uppercase;line-height:1.1}
.tabs button:hover{color:var(--accent)}.tabs button[aria-selected="true"]{color:var(--accent);border-bottom-color:var(--accent)}
@media (max-width:1400px){.coll{display:none}}
@media (max-width:980px){.dev{font-size:10.5px}}
@media (max-width:980px){.tool .tagline{display:none}}
@media (max-width:760px){.mast{gap:6px 12px;padding:8px 14px;flex-wrap:wrap}.ccd-name{display:none}.ccd svg{height:28px}.tool{padding-left:12px}.tool h1{font-size:22px}.credits{order:3;margin-left:0;align-items:flex-start;text-align:left}.tabs{margin-left:auto;flex-shrink:0;order:4}.tabs button{padding:6px 8px}}
.mapsel{display:flex;gap:6px;flex-wrap:wrap;padding:10px 22px;background:var(--panel);border-bottom:1px solid var(--line)}
.mapsel button{border:1px solid var(--line-strong);background:var(--panel);border-radius:999px;padding:4px 12px;cursor:pointer;font-size:12.5px;color:var(--ink)}
.mapsel button:hover{border-color:var(--accent)}.mapsel button[aria-pressed="true"]{background:var(--accent);color:var(--panel);border-color:var(--accent)}
.title{padding:14px 22px 6px;background:var(--panel)}
.title h2{font-family:var(--font-display);font-weight:700;font-size:26px;margin:0;color:var(--ink);text-wrap:balance;letter-spacing:-.005em}
.title .sub{color:var(--ink-2);font-size:12.5px;margin-top:4px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;padding:10px 22px 14px;background:var(--panel);border-bottom:1px solid var(--line)}
.stat{background:var(--panel-2);border-radius:var(--radius);padding:8px 10px}
.stat b{display:block;font-family:var(--font-display);font-size:24px;font-weight:700;line-height:1.1;color:var(--brand)}
.stat small{display:block;color:var(--ink-3);font-size:11px;margin-top:2px}
.grid{display:grid;grid-template-columns:minmax(0,1fr) 420px;gap:0;min-height:calc(100vh - 180px)}
@media (max-width:980px){.grid{grid-template-columns:1fr}}
#img{height:calc(100vh - 180px);min-height:520px;background:#e9e4d8}
aside{border-left:1px solid var(--line);background:var(--panel);display:flex;flex-direction:column;min-height:0}
.filters{display:flex;flex-wrap:wrap;gap:4px 10px;padding:10px 14px;border-bottom:1px solid var(--line);font-size:12.5px}
.filters label{display:inline-flex;align-items:center;gap:5px;cursor:pointer}
.sw{display:inline-block;width:12px;height:12px;border-radius:2px;border:2px solid}
.sw.gcp{border-color:var(--gcp);background:color-mix(in srgb,var(--gcp) 25%,transparent)}.sw.near{border-color:var(--near);background:color-mix(in srgb,var(--near) 25%,transparent)}.sw.area{border-color:var(--area);background:color-mix(in srgb,var(--area) 25%,transparent)}.sw.lexical{border-color:var(--lex);background:color-mix(in srgb,var(--lex) 25%,transparent)}.sw.none{border-color:var(--none)}
#geo{height:260px;border-bottom:1px solid var(--line);background:var(--sea)}
.search{padding:8px 14px;border-bottom:1px solid var(--line)}
.search input{width:100%;padding:6px 8px;border:1px solid var(--line-strong);border-radius:var(--radius);background:var(--panel)}
.list{overflow:auto;flex:1;min-height:200px;max-height:48vh}
.list table{width:100%;border-collapse:collapse;font-size:12.5px}
.list th{position:sticky;top:0;background:var(--panel-2);text-align:left;padding:5px 8px;font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3)}
.list td{padding:4px 8px;border-top:1px solid var(--line);vertical-align:top}
.list tr{cursor:pointer}.list tr:hover td{background:var(--panel-2)}
.list tr[aria-selected="true"] td{background:var(--accent-soft)}
.st{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;vertical-align:middle}
.st.gcp{background:var(--gcp)}.st.near{background:var(--near)}.st.area{background:var(--area)}.st.lexical{background:var(--lex)}.st.none{background:var(--none)}
.leaflet-container{font-family:var(--font-ui)}
.leaflet-popup-content{font-size:13px;line-height:1.4;margin:10px 14px}
.leaflet-popup-content .ocr{font-family:var(--font-mono);font-size:13px}
.leaflet-popup-content .k{color:var(--ink-3);font-size:11px;text-transform:uppercase;letter-spacing:.08em}
.leaflet-popup-content-wrapper{border-radius:4px}
.cform{margin-top:10px;padding-top:8px;border-top:1px solid var(--line);display:grid;gap:6px}
.cform input[type=text],.cform select{width:100%;padding:5px 7px;border:1px solid var(--line-strong);border-radius:var(--radius);background:var(--panel);font-size:13px}
.cform .row{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.cform button{border:1px solid var(--accent);background:var(--accent);color:#fff;border-radius:var(--radius);padding:5px 10px;cursor:pointer;font-size:12.5px}
.cform button.ghost{background:none;color:var(--accent-text)}
.cform button:hover{background:var(--accent-dark);color:#fff}
.cform .meta{font-size:11px;color:var(--ink-3)}
.corrbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:8px 14px;border-bottom:1px solid var(--line);font-size:12.5px;background:var(--panel-2)}
.corrbar b{font-family:var(--font-display);font-weight:700;font-size:20px;color:var(--brand)}
.corrbar button{border:1px solid var(--line-strong);background:var(--panel);border-radius:var(--radius);padding:4px 10px;cursor:pointer;font-size:12px}
.corrbar button:hover{border-color:var(--accent)}
.corrbar .note{flex-basis:100%;color:var(--ink-3);font-size:11.5px}
.sw.corr{border-color:#8e44ad;border-style:dashed;background:transparent}.st.corr{background:#8e44ad}
.pencil{color:#8e44ad;font-size:11px;margin-left:4px}
.wrap{max-width:1100px;margin:0 auto;padding:28px 22px 60px}
.wrap h2{font-family:var(--font-display);font-weight:800;font-size:34px;margin:0 0 8px;color:var(--ink);letter-spacing:-.01em}
.wrap h3{font-family:var(--font-display);font-weight:700;font-size:24px;margin:28px 0 6px;color:var(--accent)}
.wrap p{max-width:78ch}
.wrap table{border-collapse:collapse;width:100%;font-size:13px;margin:10px 0 18px}
.wrap th{text-align:left;background:var(--panel-2);padding:6px 8px;font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3)}
.wrap td{padding:6px 8px;border-top:1px solid var(--line);vertical-align:top}
.wrap td.n{text-align:right;font-family:var(--font-mono);font-variant-numeric:tabular-nums}
.ok{color:var(--accent-text)}.bad{color:#c0392b}
.note{background:var(--panel-2);border-left:3px solid var(--accent);padding:10px 14px;border-radius:var(--radius);margin:12px 0}
#img{position:relative}.res-note{position:absolute;left:10px;bottom:10px;z-index:400;background:color-mix(in srgb,var(--panel) 85%,transparent);color:var(--ink-3);font-size:11px;padding:3px 8px;border-radius:var(--radius);pointer-events:none}
.hires-tile{image-rendering:auto}
.legend-geo{position:absolute;right:8px;bottom:8px;z-index:400;background:color-mix(in srgb,var(--panel) 88%,transparent);padding:6px 8px;border-radius:var(--radius);font-size:11px;line-height:1.5}
.legend-geo i{display:inline-block;width:14px;height:0;border-top:2px solid;margin-right:5px;vertical-align:middle}
footer{padding:20px 22px;color:var(--ink-3);font-size:12px;border-top:1px solid var(--line)}
</style>
</head>
<body>
<header class="mast">
  <a class="ccd" href="https://comisioncorograficadigital.github.io/" target="_blank" rel="noopener" aria-label="Comisión Corográfica Digital"><svg viewBox="0 0 200 72" aria-hidden="true" xmlns="http://www.w3.org/2000/svg"><text y="68" font-family="'Barlow Condensed','Arial Narrow',sans-serif" font-weight="800" font-size="80" fill="currentColor">CC<tspan style="fill:var(--accent)">D</tspan></text></svg><span class="ccd-div" aria-hidden="true"></span><span class="ccd-name" aria-hidden="true"><span>Comisión Corográfica</span><span>Digital</span></span></a>
  <div class="tool"><h1>Lector de topónimos <span class="pil">(piloto)</span></h1><span class="tagline">lectura automática y geocodificación · diez mapas de la Comisión Corográfica</span></div>
  <div class="credits"><a class="coll" href="https://www.bibliotecanacional.gov.co/es-co/colecciones/biblioteca-digital/mapoteca/Paginas/index.aspx" target="_blank" rel="noopener">Mapoteca Digital · Biblioteca Nacional de Colombia</a><span class="dev"><span class="dev-k">Desarrollo</span> Sebastián Díaz Ángel</span></div>
  <nav class="tabs" role="tablist"><button role="tab" id="tab-visor" aria-selected="true">Visor</button><button role="tab" id="tab-informe" aria-selected="false">Informe</button></nav>
</header>
<section id="view-visor" class="view">
  <div class="mapsel" id="mapsel"></div>
  <div class="title"><h2 id="t-title"></h2><div class="sub" id="t-sub"></div></div>
  <div class="stats" id="stats"></div>
  <div class="grid">
    <div id="img"><div class="res-note" id="res-note"></div></div>
    <aside>
      <div class="filters" id="filters">
        <label><input type="checkbox" data-s="gcp" checked><span class="sw gcp"></span>punto de control</label>
        <label><input type="checkbox" data-s="near" checked><span class="sw near"></span>confirmado cerca</label>
        <label><input type="checkbox" data-s="area" checked><span class="sw area"></span>río / región</label>
        <label><input type="checkbox" data-s="lexical" checked><span class="sw lexical"></span>solo léxico</label>
        <label><input type="checkbox" data-s="none"><span class="sw none"></span>sin correspondencia</label>
        <label><input type="checkbox" id="only-corr"><span class="sw corr"></span>solo corregidos</label>
      </div>
      <div class="corrbar"><b id="corr-n">0</b><span>correcciones guardadas<br><span id="corr-where" style="color:var(--ink-3)">…</span></span><span style="margin-left:auto"></span><button id="corr-export" type="button">Exportar correcciones</button><span class="note" id="corr-note" hidden></span></div>
      <div style="position:relative"><div id="geo"></div><div class="legend-geo"><div><i style="border-color:#3b6fd1;border-top-style:dashed"></i>bbox del inventario</div><div><i style="border-color:#2f8a3e"></i>extensión estimada de la imagen</div><div><i style="border-color:#fbb03b"></i>envolvente de topónimos</div></div></div>
      <div class="search"><input id="q" type="search" placeholder="Buscar texto OCR o nombre del gacetero…"></div>
      <div class="list"><table><thead><tr><th>Texto OCR</th><th>Gacetero / corrección</th><th>Score</th><th>Δ km</th></tr></thead><tbody id="rows"></tbody></table></div>
    </aside>
  </div>
</section>
<section id="view-informe" class="view wrap" hidden>__REPORT__</section>
<footer>Piloto del proyecto <a href="https://comisioncorograficadigital.github.io/" target="_blank" rel="noopener">Comisión Corográfica Digital</a> sobre mapas de la <a href="https://www.bibliotecanacional.gov.co/es-co/colecciones/biblioteca-digital/mapoteca/Paginas/index.aspx" target="_blank" rel="noopener">Mapoteca Digital de la Biblioteca Nacional de Colombia</a>. Desarrollo: Sebastián Díaz Ángel. Realizado en CPU con OnnxTR (DB‑ResNet50 + PARSeq), rapidfuzz y un gacetero regional (GeoNames/DANE, Natural Earth, nombres históricos). La imagen se muestra a resolución reducida en las vistas generales y a resolución completa (mosaicos de 1 024 px del archivo original) al acercarse; las coordenadas de píxel de los archivos CSV/GeoJSON están en la resolución original.</footer>
<script>
const MAPS = __MAPS__;
const BASE = __BASE__;
const PLACES = __PLACES__;
const COL = {gcp:getComputedStyle(document.documentElement).getPropertyValue('--gcp').trim()||'#2f8a3e', near:'#1f9e9e', area:'#3b6fd1', lexical:'#e08a1e', none:'#8292a7'};
const STATUS_ES = {gcp:'punto de control', near:'confirmado cerca', area:'río / región', lexical:'solo léxico', none:'sin correspondencia'};
let cur = 0, imgMap, geoMap, layers = {}, geoLayers = [], marks = {}, selected = null;
const $ = s => document.querySelector(s);
function fmt(n, d=1){ return n==null ? '—' : Number(n).toLocaleString('es-CO', {maximumFractionDigits:d}); }

// tabs
for (const [id, view] of [['tab-visor','view-visor'],['tab-informe','view-informe']]) {
  document.getElementById(id).addEventListener('click', () => {
    document.querySelectorAll('.tabs button').forEach(b => b.setAttribute('aria-selected', b.id===id));
    document.querySelectorAll('.view').forEach(v => v.hidden = v.id!==view);
    if (view==='view-visor') setTimeout(()=>{imgMap.invalidateSize(); geoMap.invalidateSize();}, 50);
  });
}
// map selector
const sel = $('#mapsel');
MAPS.forEach((m, i) => { const b = document.createElement('button'); b.textContent = m.stem.toUpperCase()+' · '+(m.meta.short||m.meta.title); b.setAttribute('aria-pressed', i===0); b.addEventListener('click', () => show(i)); sel.appendChild(b); });

function initMaps(){
  imgMap = L.map('img', {crs: L.CRS.Simple, minZoom:-5, maxZoom:2, zoomSnap:0.25, attributionControl:false, preferCanvas:true});
  imgMap.createPane('thumb'); imgMap.getPane('thumb').style.zIndex = 150;      // embedded low-resolution image, always present
  imgMap.createPane('hires'); imgMap.getPane('hires').style.zIndex = 250;      // full-resolution 1024 px tiles, loaded from zoom -1.5 up
  imgMap.on('zoomend', () => { const z = imgMap.getZoom(); const el = document.getElementById('res-note'); if (el) el.textContent = z >= -1.5 ? 'resolución completa' : 'vista reducida · acerca para ver la resolución completa'; });
  geoMap = L.map('geo', {attributionControl:false, zoomControl:false, preferCanvas:true});
  L.geoJSON(BASE.countries, {style:{color:'#b9c3cf', weight:1, fillColor:'#f8f7f3', fillOpacity:1}}).addTo(geoMap);
  L.geoJSON(BASE.depts, {style:{color:'#c9d2dc', weight:0.7, fill:false}}).addTo(geoMap);
  L.geoJSON(BASE.rivers, {style:{color:'#9bbad1', weight:0.8}}).addTo(geoMap);
  L.geoJSON(BASE.lakes, {style:{color:'#9bbad1', weight:0.6, fillColor:'#dfe7ee', fillOpacity:1}}).addTo(geoMap);
  geoMap.createPane('pts'); geoMap.getPane('pts').style.zIndex = 450;
  geoMap.setView([6,-75], 5);
}
function show(i){
  cur = i; const m = MAPS[i];
  document.querySelectorAll('.mapsel button').forEach((b,k) => b.setAttribute('aria-pressed', k===i));
  $('#t-title').textContent = m.meta.title;
  const s = m.summary;
  $('#t-sub').innerHTML = `Registro <span class="mono">${m.meta.code}</span> · ${m.meta.kind} · escala ${m.meta.scale||'s. e.'} · imagen ${s.width}×${s.height} px · lectura ${fmt(s.spot_seconds/60,0)} min`;
  const inv = s.inventory_bbox, ext = s.image_extent, top = s.toponym_extent;
  const cards = [[s.n_words,'palabras leídas'],[s.n_phrases,'rótulos (frases)'],[s.n_gcp+s.n_near,'topónimos confirmados'],[s.n_area,'ríos / regiones'],[s.n_lexical_only,'solo léxicos'],[s.n_gcp,'puntos de control'],
    [s.rmse_km!=null?fmt(s.rmse_km,2)+' km':'—','error medio (RMSE)'],[s.m_per_px?fmt(s.m_per_px,0)+' m':'—','metros por píxel'],[s.rotation_deg!=null?fmt(s.rotation_deg,1)+'°':'—','giro del norte']];
  $('#stats').innerHTML = cards.map(([v,l]) => `<div class="stat"><b>${v}</b><small>${l}</small></div>`).join('');
  // image
  Object.values(layers).forEach(g => g.remove()); layers = {}; marks = {};
  if (imgMap._img) imgMap._img.remove();
  const bounds = [[-m.h, 0],[0, m.w]];
  if (imgMap._tiles) { imgMap._tiles.remove(); imgMap._tiles = null; }
  imgMap._img = L.imageOverlay(m.img, bounds, {pane:'thumb'}).addTo(imgMap);
  if (m.tiles) {
    // one native zoom level (0 = one image pixel per screen pixel); Leaflet scales the tiles for zooms between -1.5 and 2
    imgMap._tiles = L.tileLayer('tiles/' + m.stem + '/{x}_{y}.jpg', {pane:'hires', tileSize:1024, minNativeZoom:0, maxNativeZoom:0, minZoom:-1.5, maxZoom:2, bounds, noWrap:true, keepBuffer:1, updateWhenZooming:false, className:'hires-tile'}).addTo(imgMap);
  }
  imgMap.setMaxBounds([[-m.h-m.h*0.05, -m.w*0.05],[m.h*0.05, m.w*1.05]]); imgMap.fitBounds(bounds);
  imgMap.fire('zoomend');
  for (const st of ['none','lexical','area','near','gcp']) layers[st] = L.featureGroup();
  m.phrases.forEach(p => {
    const polys = p.p.map(poly => poly.map(([x,y]) => [-y, x]));
    const lay = L.polygon(polys, {color: COL[p.s], weight: p.s==='none'?0.8:1.6, fillOpacity: p.s==='none'?0:0.12, fillColor: COL[p.s]});
    lay.bindPopup(popup(p, m)); lay.on('click', () => selectRow(p.i, false));
    lay.addTo(layers[p.s]); marks[p.i] = lay;
  });
  document.querySelectorAll('#filters input').forEach(cb => { if (cb.checked) layers[cb.dataset.s].addTo(imgMap); });
  // geo
  geoLayers.forEach(l => l.remove()); geoLayers = [];
  const rect = (bb, color, dash) => bb ? L.rectangle([[bb[1],bb[0]],[bb[3],bb[2]]], {color, weight:2, dashArray: dash, fill:false}) : null;
  const fit = [];
  for (const [bb, c, d] of [[inv,'#3b6fd1','6 4'],[ext,'#2f8a3e',null],[top,'#fbb03b',null]]) { const r = rect(bb, c, d); if (r) { r.addTo(geoMap); geoLayers.push(r); fit.push(r.getBounds()); } }
  m.phrases.filter(p => (p.s==='gcp'||p.s==='near'||p.s==='area') && p.lat!=null).forEach(p => {
    const c = L.circleMarker([p.lat, p.lon], {pane:'pts', radius: p.s==='gcp'?4:3, color: COL[p.s], weight:1, fillColor: COL[p.s], fillOpacity:.85});
    c.bindTooltip(`${p.n} ← <span class="ocr">${esc(p.t)}</span>`, {direction:'top'}); c.on('click', () => selectRow(p.i, true));
    c.addTo(geoMap); geoLayers.push(c);
  });
  if (fit.length) { let b = fit[0]; fit.forEach(x => b = b.extend(x)); geoMap.fitBounds(b.pad(0.4)); }
  applyCorrections();
}
function esc(s){ return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
const TIPOS = [['poblado','lugar poblado'],['rio','río'],['quebrada','quebrada / caño'],['cerro','cerro / alto / páramo'],['region','provincia / cantón / región'],['agua','laguna / ciénaga / golfo / bahía'],['otro','otro']];
const VEREDICTOS = [['correcto','la lectura es correcta'],['corregido','corregido'],['no-toponimo','no es topónimo (cuadro, nota, graticula)'],['ilegible','ilegible']];
function ckey(p){ return MAPS[cur].stem + '-' + p.i; }
function popup(p, m){
  let h = `<div class="k">Texto leído</div><div class="ocr">${esc(p.t)}</div><div class="k" style="margin-top:6px">Estado</div><div><span class="st ${p.s}"></span>${STATUS_ES[p.s]} · confianza OCR ${fmt(p.c*100,0)} %</div>`;
  if (p.n) h += `<div class="k" style="margin-top:6px">Gacetero</div><div><b>${esc(p.n)}</b> <span style="color:var(--ink-3)">(${esc(p.ty)})</span> · similitud ${fmt(p.sc,0)}${p.r!=null?' · desvío '+fmt(p.r,1)+' km':''}</div>`;
  if (p.hint) h += `<div style="color:#b8651b;font-size:12px">⚠ el rótulo nombra un(a) ${esc(p.hint)}; el gacetero solo tiene el poblado homónimo</div>`;
  if (p.alt && p.alt.length) h += `<div style="color:var(--ink-3);font-size:12px">otras opciones: ${p.alt.map(esc).join(', ')}</div>`;
  if (p.pl!=null) h += `<div class="k" style="margin-top:6px">Posición estimada</div><div class="mono">${fmt(p.pt,3)}°, ${fmt(p.pl,3)}°</div>`;
  const key = ckey(p), c = corr[key];
  const guess = c ? c.texto : (p.n && p.ty==='pop' ? p.n : (p.n && p.s!=='lexical' ? p.n : p.t));
  const hintTipo = p.hint ? ({'río':'rio','quebrada':'quebrada','caño':'quebrada','laguna':'agua','ciénaga':'agua','golfo':'agua','bahía':'agua','ensenada':'agua','isla':'otro','punta':'otro','cabo':'otro','boca':'otro','bocas':'otro','volcán':'cerro','cerro':'cerro','páramo':'cerro','alto':'cerro','sierra':'cerro','serranía':'cerro','mina':'otro','minas':'otro'}[p.hint] || 'otro') : null;
  const tipo = c ? c.tipo : (hintTipo || (p.ty==='pop' ? 'poblado' : p.ty==='river' ? 'rio' : (p.ty==='admin1'||p.ty==='region') ? 'region' : (p.ty==='lake'||p.ty==='marine') ? 'agua' : 'poblado'));
  const ver = c ? c.veredicto : 'corregido';
  h += `<form class="cform" data-key="${key}"><div class="k">Corrección</div>
    <input type="text" name="texto" value="${esc(guess)}" placeholder="transcripción correcta" autocomplete="off">
    <div class="row"><select name="tipo">${TIPOS.map(([k,l]) => `<option value="${k}" ${k===tipo?'selected':''}>${l}</option>`).join('')}</select></div>
    <div class="row"><select name="veredicto">${VEREDICTOS.map(([k,l]) => `<option value="${k}" ${k===ver?'selected':''}>${l}</option>`).join('')}</select></div>
    <div class="row"><button type="submit">Guardar</button><button type="button" class="ghost" data-act="ok">✓ Lectura correcta</button>${c ? '<button type="button" class="ghost" data-act="del">Quitar</button>' : ''}</div>
    <div class="meta">${c ? 'Guardado ' + (c.fecha||'').slice(0,16).replace('T',' ') + (c.autor ? ' · ' + esc(String(c.autor)).slice(0,10) + '…' : '') : 'Sin corrección'}</div></form>`;
  return h;
}
// ---- corrections: shared db when the page runs inside claude.ai, this browser otherwise ----
let db = null, dl = null, uid = null, corr = {}, dbNoteShown = false;
function setNote(t){ const n = $('#corr-note'); n.textContent = t; n.hidden = !t; }
function loadLocal(){ try { corr = JSON.parse(localStorage.getItem('piloto-correcciones') || '{}'); } catch(e) { corr = {}; } $('#corr-where').textContent = 'en este navegador (sin base compartida)'; applyCorrections(); }
function saveLocal(){ try { localStorage.setItem('piloto-correcciones', JSON.stringify(corr)); } catch(e) {} }
async function initCaps(){
  if (!window.claude || typeof window.claude.use !== 'function') { loadLocal(); return; }
  try {
    const [d, u, w] = await Promise.all([claude.use('db'), claude.use('user'), claude.use('downloads')]);
    db = d; dl = w; if (u) { try { uid = await u.id(); } catch(e) {} }
  } catch(e) {}
  if (!db) { loadLocal(); return; }
  $('#corr-where').textContent = 'en la base compartida del artefacto';
  db.collection('correcciones').onSnapshot(snap => { const c = {}; snap.docs.forEach(x => { if (x.exists) c[x.id] = x.data(); }); corr = c; applyCorrections(); },
    err => { setNote('Sin acceso a la base compartida (' + (err && err.code || 'error') + '): las correcciones se guardan en este navegador.'); db = null; loadLocal(); });
}
async function saveCorrection(key, body, remove){
  if (remove) delete corr[key]; else corr[key] = body;
  applyCorrections();
  if (db) {
    try { if (remove) await db.doc('correcciones/' + key).delete(); else await db.doc('correcciones/' + key).set(body); }
    catch(e) { setNote('No se pudo guardar en la base compartida (' + (e && e.code || 'error') + '); se guarda en este navegador.'); saveLocal(); }
  } else saveLocal();
}
function applyCorrections(){
  const m = MAPS[cur]; let n = 0;
  for (const k in corr) if (k.startsWith(m.stem + '-')) n++;
  $('#corr-n').textContent = n + ' / ' + Object.keys(corr).length;
  for (const p of m.phrases) { const lay = marks[p.i]; if (!lay) continue; const c = corr[ckey(p)];
    lay.setStyle(c ? {color:'#8e44ad', dashArray:'4 3', weight:2, fillOpacity:0.15, fillColor:'#8e44ad'} : {color: COL[p.s], dashArray:null, weight: p.s==='none'?0.8:1.6, fillOpacity: p.s==='none'?0:0.12, fillColor: COL[p.s]}); }
  renderList();
}
function formBody(f, p, ver){
  return {mapa: MAPS[cur].stem, codigo: MAPS[cur].meta.code, i: p.i, ocr: p.t, texto: f.texto.value.trim(), tipo: f.tipo.value, veredicto: ver || f.veredicto.value,
          gacetero: p.n || '', bbox_px: p.b.map(v => Math.round(v / MAPS[cur].scale)), autor: uid || null, fecha: new Date().toISOString()};
}
function refreshPopup(p){ const lay = marks[p.i]; if (lay && lay.getPopup()) lay.getPopup().setContent(popup(p, MAPS[cur])); }
document.addEventListener('submit', ev => {
  const f = ev.target.closest('form.cform'); if (!f) return; ev.preventDefault();
  const p = MAPS[cur].phrases.find(x => ckey(x) === f.dataset.key); if (!p) return;
  if (!f.texto.value.trim() && f.veredicto.value === 'corregido') { f.texto.focus(); return; }
  saveCorrection(f.dataset.key, formBody(f, p)).then(() => refreshPopup(p));
});
document.addEventListener('click', ev => {
  const b = ev.target.closest('.cform [data-act]'); if (!b) return; const f = b.closest('form.cform');
  const p = MAPS[cur].phrases.find(x => ckey(x) === f.dataset.key); if (!p) return;
  if (b.dataset.act === 'ok') { f.texto.value = p.t; f.veredicto.value = 'correcto'; saveCorrection(f.dataset.key, formBody(f, p, 'correcto')).then(() => refreshPopup(p)); }
  if (b.dataset.act === 'del') saveCorrection(f.dataset.key, null, true).then(() => refreshPopup(p));
});
async function exportCorrections(){
  const rows = Object.values(corr).map(c => Object.assign({}, c));
  const payload = {generado: new Date().toISOString(), n: rows.length, correcciones: rows};
  const text = JSON.stringify(payload, null, 1); const name = 'correcciones-toponimos-' + new Date().toISOString().slice(0,10) + '.json';
  if (dl) { try { await dl.save({filename: name, data: text}); return; } catch(e) { if (e && e.code === 'declined') return; } }
  try { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], {type:'application/json'})); a.download = name; document.body.appendChild(a); a.click(); a.remove(); }
  catch(e) { setNote('No se pudo descargar; copia el JSON desde la consola.'); console.log(text); }
}
function renderList(){
  const m = MAPS[cur]; const q = $('#q').value.trim().toLowerCase();
  const on = new Set([...document.querySelectorAll('#filters input')].filter(c => c.checked).map(c => c.dataset.s));
  const order = {gcp:0, near:1, area:2, lexical:3, none:4};
  const onlyCorr = $('#only-corr').checked;
  const rows = m.phrases.filter(p => (onlyCorr ? !!corr[ckey(p)] : on.has(p.s)) && (!q || p.t.toLowerCase().includes(q) || (p.n||'').toLowerCase().includes(q) || ((corr[ckey(p)]||{}).texto||'').toLowerCase().includes(q)))
    .sort((a,b) => order[a.s]-order[b.s] || (b.sc||0)-(a.sc||0));
  $('#rows').innerHTML = rows.map(p => { const c = corr[ckey(p)]; return `<tr data-i="${p.i}" aria-selected="${selected===p.i}"><td><span class="st ${c?'corr':p.s}"></span><span class="ocr">${esc(p.t)}</span></td><td>${c ? '<span class="pencil">✎</span> ' + esc(c.veredicto==='no-toponimo' ? '— no es topónimo' : c.veredicto==='ilegible' ? '— ilegible' : c.texto) : esc(p.n||'') + (p.hint ? ' <span style="color:#b8651b" title="rótulo de ' + esc(p.hint) + '">(' + esc(p.hint) + ')</span>' : '')}</td><td class="mono">${p.sc!=null?fmt(p.sc,0):''}</td><td class="mono">${p.r!=null?fmt(p.r,1):''}</td></tr>`; }).join('');
  $('#rows').querySelectorAll('tr').forEach(tr => tr.addEventListener('click', () => selectRow(+tr.dataset.i, true)));
}
function selectRow(i, zoom){
  selected = i; document.querySelectorAll('#rows tr').forEach(tr => tr.setAttribute('aria-selected', +tr.dataset.i===i));
  const lay = marks[i]; if (!lay) return;
  if (zoom) { imgMap.fitBounds(lay.getBounds().pad(6), {maxZoom:2}); }
  lay.openPopup();
  const tr = document.querySelector(`#rows tr[data-i="${i}"]`); if (tr) tr.scrollIntoView({block:'nearest'});
}
document.querySelectorAll('#filters input[data-s]').forEach(cb => cb.addEventListener('change', () => { const g = layers[cb.dataset.s]; if (!g) return; cb.checked ? g.addTo(imgMap) : g.remove(); renderList(); }));
$('#only-corr').addEventListener('change', renderList);
$('#q').addEventListener('input', renderList);
$('#corr-export').addEventListener('click', exportCorrections);
initMaps(); show(0); initCaps();
</script>
</body>
</html>'''

# ---------------- report ----------------
def report_html():
    rows = []
    for m in maps:
        s = m['summary']; e = m['eval'] or {}
        inv = s.get('inventory_bbox'); ext = s.get('image_extent'); top = s.get('toponym_extent')
        def bb(b): return '—' if not b else f"{b[0]:.2f}, {b[1]:.2f} → {b[2]:.2f}, {b[3]:.2f}"
        rows.append(f"<tr><td><b>{m['stem'].upper()}</b><br><span style='color:var(--ink-3);font-size:12px'>{html.escape(m['meta']['title'])}</span></td>"
                    f"<td class='n'>{s['n_words']}</td><td class='n'>{s['n_phrases']}</td><td class='n'>{s['n_gcp']+s['n_near']}</td><td class='n'>{s['n_area']}</td><td class='n'>{s['n_lexical_only']}</td>"
                    f"<td class='n'>{s.get('rmse_km','—')}</td><td class='n'>{s.get('m_per_px','—')}</td>"
                    f"<td style='font-size:12px'><span class='mono'>inv.</span> {bb(inv)}<br><span class='mono'>est.</span> {bb(ext)}<br><span class='mono'>top.</span> {bb(top)}</td>"
                    f"<td class='n'>{e.get('precision','—')}</td><td class='n'>{e.get('recall','—')}</td></tr>")
    table = ("<table><thead><tr><th>Mapa</th><th>Palabras</th><th>Rótulos</th><th>Topónimos confirmados</th><th>Ríos / regiones</th><th>Solo léxicos</th><th>RMSE km</th><th>m / px</th><th>Extensión (O, S → E, N)</th><th>Precisión*</th><th>Cobertura*</th></tr></thead><tbody>"
             + ''.join(rows) + "</tbody></table>")
    body = open(S + 'ocrpilot/report_body.html').read() if os.path.exists(S + 'ocrpilot/report_body.html') else '<p>(informe pendiente)</p>'
    ev = ''
    if evals:
        ev = '<h3>Evaluación visual</h3><p>Para cada mapa revisé a ojo (a) una muestra aleatoria de 24 topónimos confirmados —si el nombre asignado es el que dice el rótulo— y (b) una ventana de 1100×1000 px del centro del mapa, contando los rótulos visibles, cuántos recibieron caja y cuántos se leyeron bien sin ayuda del gacetero. Son medidas de piloto, sobre muestras pequeñas, no una evaluación formal.</p><table><thead><tr><th>Mapa</th><th>Precisión (muestra)</th><th>Cobertura (ventana)</th><th>Observaciones</th></tr></thead><tbody>'
        for m in maps:
            e = m['eval']
            if not e: continue
            ev += f"<tr><td><b>{m['stem'].upper()}</b> {html.escape(m['meta'].get('short',''))}</td><td class='n'>{html.escape(e.get('precision','—'))}</td><td class='n' style='text-align:left'>{html.escape(e.get('recall','—'))}</td><td style='font-size:12.5px'>{html.escape(e.get('notes',''))}</td></tr>"
        ev += '</tbody></table>'
    fi = open(S + 'ocrpilot/report_findings.html').read() if os.path.exists(S + 'ocrpilot/report_findings.html') else '<p>(pendiente)</p>'
    return body.replace('__TABLE__', table).replace('__EVAL__', ev).replace('__FINDINGS__', fi)

leaflet_css = open(S + 'package/dist/leaflet.css').read().replace('</', '<\\/')
ccdbg = 'data:image/webp;base64,' + __import__('base64').b64encode(open(S + 'ccd/0001-800.webp', 'rb').read()).decode()
out = page.replace('__LEAFLET_CSS__', leaflet_css).replace('__CCDBG__', ccdbg).replace('__CONTOURS__', contours).replace('__REPORT__', report_html()).replace('__MAPS__', esc(maps)).replace('__BASE__', esc(base)).replace('__PLACES__', esc(places))
open('./index.html', 'w').write(out)
print('written ./index.html', round(len(out)/1e6, 2), 'MB')
