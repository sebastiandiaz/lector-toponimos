"""Reúne las correcciones enviadas como issues de GitHub (etiqueta «correcciones») en la carpeta correcciones/.

  python3 scripts/collect_corrections.py [--repo sebastiandiaz/lector-toponimos] [--out correcciones]

Cada issue creado con el botón «Enviar a GitHub» del visor trae un bloque ```json``` con una lista de registros
({mapa, codigo, i, ocr, texto, tipo, veredicto, gacetero, bbox_px, …}; los topónimos nuevos llevan nuevo: true,
lon_pred y lat_pred). El script guarda un archivo por issue (correcciones/issue-<n>.json), consolida todo en
correcciones/todas.json (la versión más reciente de cada clave mapa-i gana) y escribe un resumen por mapa.
Requiere el cliente `gh` autenticado (gh auth login) o la variable GITHUB_TOKEN.
"""
import json, os, re, subprocess, argparse, collections
ap = argparse.ArgumentParser(); ap.add_argument('--repo', default='sebastiandiaz/lector-toponimos'); ap.add_argument('--out', default='correcciones'); a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
issues = json.loads(subprocess.check_output(['gh', 'api', '--paginate', f'repos/{a.repo}/issues?labels=correcciones&state=all&per_page=100']))
todas = {}
if os.path.exists(a.out + '/todas.json'):
    for r in json.load(open(a.out + '/todas.json')).get('correcciones', []): todas[f"{r['mapa']}-{r['i']}"] = r
n_new = 0
for it in issues:
    body = it.get('body') or ''
    m = re.search(r'```json\s*(.*?)```', body, re.S)
    if not m: continue
    try: rows = json.loads(m.group(1))
    except json.JSONDecodeError: print('issue', it['number'], 'JSON ilegible'); continue
    for r in rows:
        r['issue'] = it['number']; r['issue_autor'] = (it.get('user') or {}).get('login'); r['issue_fecha'] = it.get('created_at')
    json.dump({'issue': it['number'], 'titulo': it['title'], 'correcciones': rows}, open(f"{a.out}/issue-{it['number']}.json", 'w'), ensure_ascii=False, indent=1)
    for r in rows:
        k = f"{r['mapa']}-{r['i']}"
        if k not in todas or (r.get('fecha') or '') >= (todas[k].get('fecha') or ''): todas[k] = r; n_new += 1
json.dump({'n': len(todas), 'correcciones': list(todas.values())}, open(a.out + '/todas.json', 'w'), ensure_ascii=False, indent=1)
por_mapa = collections.Counter(r['mapa'] for r in todas.values()); nuevos = sum(1 for r in todas.values() if r.get('nuevo'))
print(f'{len(issues)} issues, {n_new} registros leídos, {len(todas)} correcciones en total ({nuevos} topónimos nuevos):', dict(por_mapa))
