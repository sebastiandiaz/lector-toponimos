"""Build the standalone viewer for the mapKurator-style pilot: one HTML with the ten maps, their recognised labels,
the gazetteer matches and the geocoding result, in the visual system of the Mapoteca Digital.

python3 -I viewer.py  -> /home/claude/piloto-toponimos-bnc.html
"""
import json, base64, io, os, html
from PIL import Image
from shapely.geometry import shape, box, mapping
Image.MAX_IMAGE_PIXELS = None

S = '/tmp/claude-0/-home-claude/132c8f7b-456b-57d4-9103-6cd2bdc34e88/scratchpad/'
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
    tiles_idx = json.load(open('/home/claude/tiles/index.json')) if os.path.exists('/home/claude/tiles/index.json') else {}
    model = {'affine': sm.get('transform'), 'poly2': sm.get('poly2')} if sm.get('transform') else None
    maps.append({'stem': stem, 'meta': meta[stem], 'summary': {k: v_ for k, v_ in sm.items() if k not in ('transform', 'poly2')}, 'model': model, 'img': uri, 'w': W, 'h': H, 'scale': 1.0, 'tiles': tiles_idx.get(stem), 'phrases': ph, 'eval': evals.get(stem)})
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
<title>Nomenclátor (piloto): lector de topónimos en mapas antiguos</title>
<meta name="description" content="Nomenclátor (piloto): lector de topónimos en mapas antiguos — lectura automática y geocodificación, proyecto Comisión Corográfica Digital">
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
.tool h1{font-family:var(--font-display);font-weight:800;font-size:30px;margin:0;line-height:1;letter-spacing:-.01em;white-space:nowrap;color:var(--ink);flex-shrink:0}
.tool h1 .pil{font-weight:600;color:var(--ink-3);font-size:.72em;letter-spacing:0}
.tool .tagline{font-size:12.5px;color:var(--ink-3);white-space:nowrap;min-width:0;max-width:100%;overflow:hidden;text-overflow:ellipsis}
.credits{margin-left:8px;flex-shrink:0;display:flex;flex-direction:column;align-items:flex-end;gap:2px;text-align:right}
.coll{font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:var(--ink-3);text-decoration:none;white-space:nowrap}
.coll:hover{color:var(--accent)}
.dev{display:flex;flex-direction:column;align-items:flex-end;font-size:11px;letter-spacing:.4px;line-height:1.25;color:var(--ink-2);white-space:nowrap}
.dev-k{font-size:9px;letter-spacing:1.4px;text-transform:uppercase;color:var(--ink-3)}
.dev-ai{color:var(--ink-3)}
@media (max-width:1180px){.dev-ai{display:none}}
.tabs{display:flex;gap:2px}
.tabs button{border:0;background:none;padding:8px 10px;border-bottom:2px solid transparent;color:var(--ink-3);cursor:pointer;font-family:var(--font-ui);font-size:12px;font-weight:500;letter-spacing:1.5px;text-transform:uppercase;line-height:1.1}
.tabs button:hover{color:var(--accent)}.tabs button[aria-selected="true"]{color:var(--accent);border-bottom-color:var(--accent)}
@media (max-width:1400px){.coll{display:none}}
@media (max-width:980px){.dev{font-size:10.5px}}
@media (max-width:1250px){.tool .tagline{display:none}}
@media (max-width:760px){.mast{gap:6px 12px;padding:8px 14px;flex-wrap:wrap}.ccd-name{display:none}.ccd svg{height:28px}.tool{padding-left:12px}.tool h1{font-size:22px}.credits{order:3;margin-left:0;align-items:flex-start;text-align:left;max-width:100%}.dev{align-items:flex-start;white-space:normal}.dev-k{font-size:8.5px;letter-spacing:1.1px}.tabs{margin-left:auto;flex-shrink:0;order:4}.tabs button{padding:6px 8px}}
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
.cform,.nform{margin-top:10px;padding-top:8px;border-top:1px solid var(--line);display:grid;gap:6px}
.cform input[type=text],.cform select,.nform input[type=text],.nform select{width:100%;padding:5px 7px;border:1px solid var(--line-strong);border-radius:var(--radius);background:var(--panel);font-size:13px}
.cform .row,.nform .row{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.cform button,.nform button{border:1px solid var(--accent);background:var(--accent);color:#fff;border-radius:var(--radius);padding:5px 10px;cursor:pointer;font-size:12.5px}
.cform button.ghost,.nform button.ghost{background:none;color:var(--accent-text)}
.cform button:hover,.nform button:hover{background:var(--accent-dark);color:#fff}
.cform .meta,.nform .meta{font-size:11px;color:var(--ink-3)}
.corrbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:8px 14px;border-bottom:1px solid var(--line);font-size:12.5px;background:var(--panel-2)}
.corrbar b{font-family:var(--font-display);font-weight:700;font-size:20px;color:var(--brand)}
.corrbar button{border:1px solid var(--line-strong);background:var(--panel);border-radius:var(--radius);padding:4px 10px;cursor:pointer;font-size:12px}
.corrbar button:hover{border-color:var(--accent)}
.corrbar .note{flex-basis:100%;color:var(--ink-3);font-size:11.5px}
.corrbar .note a{display:inline-block;margin:2px 6px 0 0;padding:2px 8px;border:1px solid var(--accent);border-radius:999px;text-decoration:none;font-size:11.5px}
.corrbar button.on{background:var(--accent);color:var(--panel);border-color:var(--accent)}
#img.adding .leaflet-container, #img.adding{cursor:crosshair!important}
#img.adding .leaflet-interactive{pointer-events:none}
#img.moving .leaflet-container{cursor:move!important}
.hdl{box-sizing:border-box;border:2px solid #8e44ad;background:#fff;border-radius:50%;box-shadow:0 1px 3px rgba(0,0,0,.35);cursor:grab}
.hdl.rot::after{content:'↻';display:block;font-size:11px;line-height:14px;text-align:center;color:#8e44ad;font-weight:700}
.hdl.end,.hdl.hgt{border-radius:2px;cursor:move}
.nform .ang{display:flex;gap:6px;align-items:center;font-size:12px;color:var(--ink-3)}
.nform .ang input[type=range]{flex:1;min-width:70px;margin:0;accent-color:#8e44ad}
.nform .ang input[type=number]{width:66px;padding:3px 5px;border:1px solid var(--line-strong);border-radius:var(--radius);background:var(--panel);font-size:12.5px}
.sw.nuevo{border-color:#8e44ad;background:color-mix(in srgb,#8e44ad 25%,transparent)}
.badge-new{display:inline-block;font-size:9.5px;letter-spacing:1px;text-transform:uppercase;color:#8e44ad;border:1px solid #8e44ad;border-radius:999px;padding:0 6px;margin-left:4px;vertical-align:middle}
.cform textarea,.nform textarea{width:100%;padding:5px 7px;border:1px solid var(--line-strong);border-radius:var(--radius);background:var(--panel);font-size:12.5px;font-family:inherit;resize:vertical}
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
  <div class="tool"><h1>Nomenclátor <span class="pil">(piloto)</span></h1><span class="tagline">lector de topónimos en mapas antiguos</span></div>
  <div class="credits"><a class="coll" href="https://comisioncorograficadigital.github.io/" target="_blank" rel="noopener">Comisión Corográfica Digital · entidades aliadas</a><span class="dev" title="Concepción, diseño, fuentes y validación: Sebastián Díaz Ángel; desarrollo asistido por IA (Claude)"><span class="dev-k">Concepción, diseño, fuentes y validación</span> Sebastián Díaz Ángel <span class="dev-ai">· desarrollo asistido por IA (Claude)</span></span></div>
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
      <div class="corrbar"><b id="corr-n">0</b><span>correcciones guardadas<br><span id="corr-where" style="color:var(--ink-3)">…</span></span><span style="margin-left:auto"></span><button id="add-topo" type="button" title="Dibuja un rectángulo sobre un rótulo que el lector no detectó y escribe su nombre">＋ Añadir topónimo</button><button id="corr-export" type="button">Exportar JSON</button><button id="corr-issue" type="button" title="Abre un issue en GitHub con las correcciones, para reunirlas en el repositorio">Enviar a GitHub</button><span class="note" id="corr-note" hidden></span></div>
      <div style="position:relative"><div id="geo"></div><div class="legend-geo"><div><i style="border-color:#3b6fd1;border-top-style:dashed"></i>bbox del inventario</div><div><i style="border-color:#2f8a3e"></i>extensión estimada de la imagen</div><div><i style="border-color:#fbb03b"></i>envolvente de topónimos</div></div></div>
      <div class="search"><input id="q" type="search" placeholder="Buscar texto OCR o nombre del gacetero…"></div>
      <div class="list"><table><thead><tr><th>Texto OCR</th><th>Gacetero / corrección</th><th>Score</th><th>Δ km</th></tr></thead><tbody id="rows"></tbody></table></div>
    </aside>
  </div>
</section>
<section id="view-informe" class="view wrap" hidden>__REPORT__</section>
<footer>Nomenclátor, lector de topónimos en mapas antiguos: piloto del proyecto <a href="https://comisioncorograficadigital.github.io/" target="_blank" rel="noopener">Comisión Corográfica Digital</a> con mapas de las entidades aliadas; en esta fase, diez hojas de la <a href="https://www.bibliotecanacional.gov.co/es-co/colecciones/biblioteca-digital/mapoteca/Paginas/index.aspx" target="_blank" rel="noopener">Mapoteca Digital de la Biblioteca Nacional de Colombia</a>. Concepción, diseño, fuentes y validación: Sebastián Díaz Ángel; desarrollo asistido por IA (Claude). Realizado en CPU con OnnxTR (DB‑ResNet50 + PARSeq), rapidfuzz y un gacetero regional (GeoNames/DANE, Natural Earth, nombres históricos). La imagen se muestra a resolución reducida en las vistas generales y a resolución completa (mosaicos de 1 024 px del archivo original) al acercarse; las coordenadas de píxel de los archivos CSV/GeoJSON están en la resolución original.</footer>
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
  if (typeof closeEditor === 'function' && editor) { editor.c = null; closeEditor(); }
  cur = i; const m = MAPS[i];
  document.querySelectorAll('.mapsel button').forEach((b,k) => b.setAttribute('aria-pressed', k===i));
  $('#t-title').textContent = m.meta.title;
  const s = m.summary;
  $('#t-sub').innerHTML = `${esc(m.meta.fuente||'Mapoteca Digital, Biblioteca Nacional de Colombia')} · registro <span class="mono">${m.meta.code}</span> · ${m.meta.kind} · escala ${m.meta.scale||'s. e.'} · imagen ${s.width}×${s.height} px · lectura ${fmt(s.spot_seconds/60,0)} min`;
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
const GITHUB_REPO = '__GITHUB_REPO__';
function predictLL(m, x, y){
  if (!m.model) return null;
  if (m.model.poly2) { const Q = m.model.poly2, nx = (x - m.w/2) / m.w, ny = (y - m.h/2) / m.h, f = [1, nx, ny, nx*nx, nx*ny, ny*ny];
    return [f.reduce((s, fi, k) => s + fi*Q[k][0], 0), f.reduce((s, fi, k) => s + fi*Q[k][1], 0)]; }
  const M = m.model.affine; return [x*M[0][0] + y*M[1][0] + M[2][0], x*M[0][1] + y*M[1][1] + M[2][1]];
}
// ---- adding toponyms the reader missed: draw a box over the label, orient it, then name it ----
let adding = false, dragStart = null, dragRect = null, dragShift = false, newMarks = {}, editor = null, moving = null, snapDown = false;
function trackMods(ev){ snapDown = !!(ev.ctrlKey || ev.metaKey); }   // Ctrl (Cmd) while dragging the round handle snaps the angle to 5° steps (Shift is reserved by Leaflet)
document.addEventListener('keydown', trackMods); document.addEventListener('keyup', trackMods);
const toLL = ([x, y]) => [-y, x];
function px(latlng){ return [latlng.lng, -latlng.lat]; }
function norm180(a){ return ((a + 180) % 360 + 360) % 360 - 180; }
// box geometry in image pixels (y down): centre, length along the text, height, angle in degrees counter-clockwise (same convention as the reader's phrases)
function axes(g){ const a = g.ang * Math.PI / 180; return {ux: Math.cos(a), uy: -Math.sin(a), nx: -Math.sin(a), ny: -Math.cos(a)}; }   // u: reading direction; n: towards the top of the letters
function boxCorners(g){ const {ux, uy, nx, ny} = axes(g), hw = g.w / 2, hh = g.h / 2, P = (s, t) => [g.cx + ux*s + nx*t, g.cy + uy*s + ny*t]; return [P(-hw, hh), P(hw, hh), P(hw, -hh), P(-hw, -hh)]; }   // start-top, end-top, end-bottom, start-bottom
function envelope(C){ const xs = C.map(p => p[0]), ys = C.map(p => p[1]); return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]; }
function geomFromPoly(P){ const [p0, p1, , p3] = P; return {cx: (P[0][0]+P[1][0]+P[2][0]+P[3][0])/4, cy: (P[0][1]+P[1][1]+P[2][1]+P[3][1])/4, w: Math.hypot(p1[0]-p0[0], p1[1]-p0[1]), h: Math.hypot(p3[0]-p0[0], p3[1]-p0[1]), ang: Math.atan2(-(p1[1]-p0[1]), p1[0]-p0[0]) * 180 / Math.PI}; }
function geomFromBbox(bb){ return {cx: (bb[0]+bb[2])/2, cy: (bb[1]+bb[3])/2, w: bb[2]-bb[0], h: bb[3]-bb[1], ang: 0}; }
function setAdding(on){
  adding = on; $('#add-topo').classList.toggle('on', on); $('#img').classList.toggle('adding', on);
  if (on) { closeEditor(); imgMap.dragging.disable(); imgMap.boxZoom.disable(); imgMap.closePopup(); setNote('Dibuja un rectángulo sobre el rótulo (clic y arrastrar). Con Shift, arrastra a lo largo del rótulo y la caja sale ya girada. Esc para salir.'); }
  else { imgMap.dragging.enable(); imgMap.boxZoom.enable(); if (dragRect) { dragRect.remove(); dragRect = null; } dragStart = null; setNote(''); }
}
function newForm(key, c, editing){
  c = c || {}; const ang = c.angulo != null ? c.angulo : 0;
  const geo = c.lon_pred != null ? 'posición estimada ' + fmt(c.lat_pred,3) + '°, ' + fmt(c.lon_pred,3) + '°' : '';
  return `<form class="nform" data-key="${key}"><div class="k">${c.fecha ? 'Topónimo añadido' : 'Nuevo topónimo'}</div>
    <input type="text" name="texto" value="${esc(c.texto||'')}" placeholder="texto del rótulo, tal como está escrito" autocomplete="off" required>
    <div class="row"><select name="tipo">${TIPOS.map(([k,l]) => `<option value="${k}" ${k===(c.tipo||'poblado')?'selected':''}>${l}</option>`).join('')}</select></div>
    <input type="text" name="gacetero" value="${esc(c.gacetero||'')}" placeholder="nombre actual o normalizado (opcional)" autocomplete="off">
    <textarea name="nota" rows="2" placeholder="nota (opcional)">${esc(c.nota||'')}</textarea>
    ${editing ? `<div class="ang"><label>Ángulo</label><input type="range" name="angulo" min="-180" max="180" step="0.5" value="${ang}"><input type="number" name="angn" min="-180" max="180" step="0.5" value="${ang}"><span>°</span></div>
    <div class="meta">Asa redonda: girar (con Ctrl, de 5 en 5°) · asas cuadradas: largo y alto · arrastra la caja para moverla</div>` : ''}
    <div class="row"><button type="submit">Guardar</button><button type="button" class="ghost" data-act="cancel">${editing || !c.fecha ? 'Cancelar' : 'Cerrar'}</button>${c.fecha && !editing ? '<button type="button" class="ghost" data-act="geom">Ajustar caja</button><button type="button" class="ghost" data-act="del">Quitar</button>' : ''}</div>
    <div class="meta"><span class="geo">${geo}${!editing && c.angulo ? ' · ángulo ' + fmt(c.angulo,1) + '°' : ''}</span>${c.fecha ? (geo ? ' · ' : '') + 'guardado ' + (c.fecha||'').slice(0,16).replace('T',' ') : ''}</div></form>`;
}
// the box editor: dashed polygon, a round handle to rotate, two square handles for length and height; drag the box to move it
function openEditor(key, g, c){
  closeEditor(); const m = MAPS[cur]; if (newMarks[key]) newMarks[key].remove();
  g.cx = Math.max(0, Math.min(m.w, g.cx)); g.cy = Math.max(0, Math.min(m.h, g.cy)); g.w = Math.max(12, g.w); g.h = Math.max(8, g.h); g.ang = norm180(g.ang || 0);
  const mk = (cls, size, title) => L.marker([0, 0], {draggable: true, keyboard: false, title, zIndexOffset: 1000, icon: L.divIcon({className: 'hdl ' + cls, iconSize: [size, size], iconAnchor: [size/2, size/2]})}).addTo(imgMap);
  const ed = editor = {key, g, c, poly: L.polygon(boxCorners(g).map(toLL), {color:'#8e44ad', weight:2, dashArray:'4 3', fillOpacity:.1, fillColor:'#8e44ad'}).addTo(imgMap),
    link: L.polyline([toLL([g.cx, g.cy]), toLL([g.cx, g.cy])], {color:'#8e44ad', weight:1, dashArray:'2 3', interactive:false}).addTo(imgMap),
    hRot: mk('rot', 18, 'Girar la caja (con Ctrl, de 5 en 5°)'), hEnd: mk('end', 12, 'Largo de la caja'), hHgt: mk('hgt', 12, 'Alto de la caja'), popup: null};
  ed.hRot.on('drag', () => { const [x, y] = px(ed.hRot.getLatLng()); let a = Math.atan2(-(x - g.cx), -(y - g.cy)) * 180 / Math.PI; if (snapDown) a = Math.round(a / 5) * 5; g.ang = norm180(a); placeEditor('rot'); });
  ed.hEnd.on('drag', () => { const [x, y] = px(ed.hEnd.getLatLng()), {ux, uy} = axes(g), sx = g.cx - ux*g.w/2, sy = g.cy - uy*g.w/2; g.w = Math.max(12, (x - sx)*ux + (y - sy)*uy); g.cx = sx + ux*g.w/2; g.cy = sy + uy*g.w/2; placeEditor('end'); });
  ed.hHgt.on('drag', () => { const [x, y] = px(ed.hHgt.getLatLng()), {nx, ny} = axes(g), tx = g.cx + nx*g.h/2, ty = g.cy + ny*g.h/2; g.h = Math.max(8, -((x - tx)*nx + (y - ty)*ny)); g.cx = tx - nx*g.h/2; g.cy = ty - ny*g.h/2; placeEditor('hgt'); });
  [ed.hRot, ed.hEnd, ed.hHgt].forEach(h => h.on('dragend', () => placeEditor(null, true)));
  ed.poly.on('mousedown', e => { L.DomEvent.stop(e.originalEvent); const [x, y] = px(e.latlng); moving = {x, y, cx: g.cx, cy: g.cy}; imgMap.dragging.disable(); $('#img').classList.add('moving'); });
  const bb = envelope(boxCorners(g));
  ed.popup = L.popup({closeOnClick: false, autoClose: false, offset: [0, -36], maxWidth: 320}).setLatLng(toLL([(bb[0] + bb[2]) / 2, bb[1]])).setContent(newForm(key, c, true)).openOn(imgMap);
  ed.popup.on('remove', () => { if (editor === ed) closeEditor(); });
  placeEditor();
}
function closeEditor(){
  const ed = editor; if (!ed) return; editor = null; moving = null; imgMap.dragging.enable(); $('#img').classList.remove('moving');
  [ed.poly, ed.link, ed.hRot, ed.hEnd, ed.hHgt].forEach(l => l.remove()); if (ed.popup) ed.popup.remove();
  if (ed.c && ed.c.fecha) applyCorrections();     // a saved toponym was being adjusted: put its mark back
}
function placeEditor(skip, reanchor){
  const ed = editor; if (!ed) return; const g = ed.g, m = MAPS[cur], {ux, uy, nx, ny} = axes(g);
  const C = boxCorners(g); ed.poly.setLatLngs(C.map(toLL));
  const d = 28 / Math.pow(2, imgMap.getZoom());      // the rotation handle sits 28 screen pixels above the top edge
  const topMid = [g.cx + nx*g.h/2, g.cy + ny*g.h/2], rotP = [topMid[0] + nx*d, topMid[1] + ny*d];
  if (skip !== 'rot') ed.hRot.setLatLng(toLL(rotP)); if (skip !== 'end') ed.hEnd.setLatLng(toLL([g.cx + ux*g.w/2, g.cy + uy*g.w/2])); if (skip !== 'hgt') ed.hHgt.setLatLng(toLL([g.cx - nx*g.h/2, g.cy - ny*g.h/2]));
  ed.link.setLatLngs([toLL(topMid), skip === 'rot' ? ed.hRot.getLatLng() : toLL(rotP)]);
  if (reanchor && ed.popup) { const bb = envelope(C); ed.popup.setLatLng(toLL([(bb[0] + bb[2]) / 2, bb[1]])); }
  const el = ed.popup && ed.popup.getElement(), f = el && el.querySelector('form.nform');     // the editor's own form (a closing popup of the same key may still be fading out)
  if (f) { const av = Math.round(g.ang * 2) / 2; if (f.angulo) f.angulo.value = av; if (f.angn && document.activeElement !== f.angn) f.angn.value = av;
    const ll = predictLL(m, g.cx, g.cy), geo = f.querySelector('.geo'); if (geo) geo.textContent = (ll ? 'posición estimada ' + fmt(ll[1],3) + '°, ' + fmt(ll[0],3) + '° · ' : '') + Math.round(g.w) + '×' + Math.round(g.h) + ' px'; }
}
function dragGeom(a, b, shift){
  const [x0, y0] = px(a), [x1, y1] = px(b);
  if (shift) { const len = Math.hypot(x1 - x0, y1 - y0); let ang = Math.atan2(-(y1 - y0), x1 - x0) * 180 / Math.PI; if (Math.abs(ang) > 90) ang = norm180(ang + 180);   // dragged from the end of the word: keep the text upright
    return {cx: (x0 + x1)/2, cy: (y0 + y1)/2, w: len, h: Math.max(16, Math.min(0.25 * len, 160)), ang}; }
  return {cx: (x0 + x1)/2, cy: (y0 + y1)/2, w: Math.abs(x1 - x0), h: Math.abs(y1 - y0), ang: 0};
}
function startDrag(e){ if (!adding) return; dragStart = e.latlng; dragShift = !!(e.originalEvent && e.originalEvent.shiftKey); if (dragRect) dragRect.remove(); dragRect = L.polygon([e.latlng, e.latlng, e.latlng, e.latlng], {color:'#8e44ad', weight:2, dashArray:'4 3', fillOpacity:.1, interactive:false}).addTo(imgMap); L.DomEvent.stop(e.originalEvent); }
function moveDrag(e){ if (!adding || !dragStart || !dragRect) return; dragShift = dragShift || !!(e.originalEvent && e.originalEvent.shiftKey); const g = dragGeom(dragStart, e.latlng, dragShift); if (g.w > 0 || g.h > 0) dragRect.setLatLngs(boxCorners(g).map(toLL)); }
function endDrag(e){
  if (!adding || !dragStart) return;
  const m = MAPS[cur]; let g = dragGeom(dragStart, e.latlng, dragShift);
  if (dragShift ? g.w < 20 : (g.w < 20 || g.h < 12)) g = {cx: g.cx, cy: g.cy, w: 240, h: 60, ang: 0};   // a click: default box
  const key = m.stem + '-n' + Date.now().toString(36);
  dragStart = null; if (dragRect) { dragRect.remove(); dragRect = null; } adding = false; $('#add-topo').classList.remove('on'); $('#img').classList.remove('adding'); imgMap.dragging.enable(); imgMap.boxZoom.enable(); setNote('');
  openEditor(key, g, null);
  setTimeout(() => { const f = document.querySelector('form.nform input[name=texto]'); if (f) f.focus(); }, 50);
}
function moveBox(e){ if (!moving || !editor) return; const [x, y] = px(e.latlng); editor.g.cx = moving.cx + x - moving.x; editor.g.cy = moving.cy + y - moving.y; placeEditor(); }
function endMove(e){ if (!moving) return; if (e && e.latlng && editor) moveBox(e);   /* the canvas throttles mousemove; the release position is exact */ moving = null; imgMap.dragging.enable(); $('#img').classList.remove('moving'); placeEditor(null, true); }
document.addEventListener('input', ev => {
  const f = ev.target.closest('form.nform'); if (!f || !editor || editor.key !== f.dataset.key) return; const n = ev.target.name; if (n !== 'angulo' && n !== 'angn') return;
  const v = parseFloat(ev.target.value); if (isNaN(v)) return; editor.g.ang = norm180(v); if (n === 'angulo' && f.angn) f.angn.value = v; if (n === 'angn' && f.angulo) f.angulo.value = v; placeEditor();
});
document.addEventListener('submit', ev => {
  const f = ev.target.closest('form.nform'); if (!f) return; ev.preventDefault();
  const key = f.dataset.key; const m = MAPS[cur]; const prev = corr[key] || {}; const ed = (editor && editor.key === key) ? editor : null;
  if (!f.texto.value.trim()) { f.texto.focus(); return; }
  let geo = {bbox_px: prev.bbox_px || null, poly_px: prev.poly_px || null, angulo: prev.angulo ?? 0, lon_pred: prev.lon_pred ?? null, lat_pred: prev.lat_pred ?? null};
  if (ed) { const g = ed.g, poly = boxCorners(g).map(p => [Math.round(p[0]), Math.round(p[1])]), bb = envelope(poly), ll = predictLL(m, g.cx, g.cy);
    geo = {bbox_px: [Math.max(0, bb[0]), Math.max(0, bb[1]), Math.min(m.w, bb[2]), Math.min(m.h, bb[3])], poly_px: poly, angulo: Math.round(g.ang * 10) / 10, lon_pred: ll ? +ll[0].toFixed(5) : null, lat_pred: ll ? +ll[1].toFixed(5) : null}; }
  const body = Object.assign({mapa: m.stem, codigo: m.meta.code, i: key.slice(m.stem.length + 1), nuevo: true, ocr: '', texto: f.texto.value.trim(), tipo: f.tipo.value, veredicto: 'nuevo',
                gacetero: f.gacetero.value.trim(), nota: f.nota.value.trim()}, geo, {autor: uid || null, fecha: new Date().toISOString()});
  if (ed) { ed.c = null; closeEditor(); }
  saveCorrection(key, body).then(() => { const lay = newMarks[key]; if (lay) lay.openPopup(); });
});
document.addEventListener('click', ev => {
  const b = ev.target.closest('.nform [data-act]'); if (!b) return; const f = b.closest('form.nform'); const key = f.dataset.key;
  if (b.dataset.act === 'cancel') { if (editor && editor.key === key) closeEditor(); else imgMap.closePopup(); }
  if (b.dataset.act === 'del') { imgMap.closePopup(); saveCorrection(key, null, true); }
  if (b.dataset.act === 'geom') { const c = corr[key]; if (!c) return; openEditor(key, c.poly_px ? geomFromPoly(c.poly_px) : geomFromBbox(c.bbox_px), c); }
});
document.addEventListener('keydown', ev => { if (ev.key === 'Escape') { if (editor) closeEditor(); else if (adding) setAdding(false); } });
async function sendToGitHub(){
  if (!GITHUB_REPO) { setNote('No hay repositorio configurado.'); return; }
  const rows = Object.values(corr); if (!rows.length) { setNote('No hay correcciones que enviar.'); return; }
  const chunks = []; let cur_ = [];
  for (const r of rows) { cur_.push(r); if (JSON.stringify(cur_).length > 5200) { chunks.push(cur_); cur_ = []; } }
  if (cur_.length) chunks.push(cur_);
  const links = chunks.map((ch, k) => {
    const title = `Correcciones de topónimos (${ch.length}) · ${new Date().toISOString().slice(0,10)}` + (chunks.length > 1 ? ` · lote ${k+1}/${chunks.length}` : '');
    const body = `Correcciones y topónimos nuevos exportados desde el Nomenclátor.\n\n\`\`\`json\n${JSON.stringify(ch)}\n\`\`\``;
    return `<a href="https://github.com/${GITHUB_REPO}/issues/new?title=${encodeURIComponent(title)}&labels=correcciones&body=${encodeURIComponent(body)}" target="_blank" rel="noopener">${chunks.length > 1 ? 'Lote ' + (k+1) : 'Abrir el issue'} (${ch.length})</a>`;
  });
  const n = $('#corr-note'); n.innerHTML = `Se abre GitHub con el texto listo; solo hay que pulsar «Submit new issue»${chunks.length > 1 ? ' en cada lote' : ''}: ` + links.join(' '); n.hidden = false;
}
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
  // new toponyms of this map
  Object.values(newMarks).forEach(l => l.remove()); newMarks = {};
  for (const [k, c] of Object.entries(corr)) {
    if (!c.nuevo || c.mapa !== m.stem || !(c.poly_px || c.bbox_px)) continue;
    if (editor && editor.key === k) continue;      // being adjusted: the editor draws it
    const P = c.poly_px || boxCorners(geomFromBbox(c.bbox_px));
    const lay = L.polygon(P.map(toLL), {color:'#8e44ad', weight:2, fillOpacity:.12, fillColor:'#8e44ad'});
    lay.bindPopup(() => newForm(k, corr[k] || c, false), {closeOnClick:false, autoClose:false, maxWidth:320});
    lay.addTo(imgMap); newMarks[k] = lay;
  }
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
  const nuevos = Object.entries(corr).filter(([k, c]) => c.nuevo && c.mapa === m.stem && (!q || (c.texto||'').toLowerCase().includes(q) || (c.gacetero||'').toLowerCase().includes(q)));
  const newRows = nuevos.map(([k, c]) => `<tr data-k="${k}"><td><span class="st corr"></span><span class="ocr">${esc(c.texto)}</span><span class="badge-new">nuevo</span></td><td>${esc(c.gacetero||'')}</td><td class="mono"></td><td class="mono"></td></tr>`).join('');
  $('#rows').innerHTML = newRows + rows.map(p => { const c = corr[ckey(p)]; return `<tr data-i="${p.i}" aria-selected="${selected===p.i}"><td><span class="st ${c?'corr':p.s}"></span><span class="ocr">${esc(p.t)}</span></td><td>${c ? '<span class="pencil">✎</span> ' + esc(c.veredicto==='no-toponimo' ? '— no es topónimo' : c.veredicto==='ilegible' ? '— ilegible' : c.texto) : esc(p.n||'') + (p.hint ? ' <span style="color:#b8651b" title="rótulo de ' + esc(p.hint) + '">(' + esc(p.hint) + ')</span>' : '')}</td><td class="mono">${p.sc!=null?fmt(p.sc,0):''}</td><td class="mono">${p.r!=null?fmt(p.r,1):''}</td></tr>`; }).join('');
  $('#rows').querySelectorAll('tr[data-i]').forEach(tr => tr.addEventListener('click', () => selectRow(+tr.dataset.i, true)));
  $('#rows').querySelectorAll('tr[data-k]').forEach(tr => tr.addEventListener('click', () => { const lay = newMarks[tr.dataset.k]; if (lay) { imgMap.fitBounds(lay.getBounds().pad(6), {maxZoom:1}); lay.openPopup(); } }));
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
$('#corr-issue').addEventListener('click', sendToGitHub);
$('#add-topo').addEventListener('click', () => setAdding(!adding));
initMaps(); imgMap.on('mousedown', startDrag); imgMap.on('mousemove', moveDrag); imgMap.on('mouseup', endDrag);
imgMap.on('mousemove', moveBox); imgMap.on('mouseup', endMove); imgMap.on('mouseout', endMove); imgMap.on('zoomend', () => placeEditor());
show(0); initCaps();
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
out = page.replace('__GITHUB_REPO__', 'sebastiandiaz/lector-toponimos').replace('__LEAFLET_CSS__', leaflet_css).replace('__CCDBG__', ccdbg).replace('__CONTOURS__', contours).replace('__REPORT__', report_html()).replace('__MAPS__', esc(maps)).replace('__BASE__', esc(base)).replace('__PLACES__', esc(places))
open('/home/claude/piloto-toponimos-bnc.html', 'w').write(out)
print('written /home/claude/piloto-toponimos-bnc.html', round(len(out)/1e6, 2), 'MB')
