"""Build a regional gazetteer (Colombia, Panamá and neighbours) for post-OCR matching and geocoding.

Sources (all fetched from GitHub mirrors):
  - dr5hn/countries-states-cities-database (GeoNames-derived seats of municipalities): CO, PA, VE, EC
  - DANE MGN 2018 municipality polygons (caticoa3/colombia_mapa): names + representative points for anything missing
  - Natural Earth 10m: populated places, rivers (lines), lakes, marine polys, geographic regions, admin-1 (polygons)
  - a short manual list of historical provinces/states and water bodies of the 1850s–1870s
Output: gaz/gazetteer.json with entries {name, norm, variants, type, country, lon, lat, geom (WKT for line/polygon), src}
"""
import json, re, unicodedata
from shapely.geometry import shape, box, Point
from shapely import wkt

G = './gaz/'
ROI = box(-84, -5, -66, 14)

def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

TYPE_WORDS = {'rio', 'quebrada', 'cano', 'cerro', 'cerros', 'alto', 'cuchilla', 'serrania', 'sierra', 'paramo', 'punta', 'puerto', 'bahia',
              'ensenada', 'golfo', 'isla', 'islas', 'laguna', 'cienaga', 'boca', 'bocas', 'mesa', 'pico', 'nevado', 'volcan', 'salto',
              'llano', 'llanos', 'sabana', 'sabanas', 'valle', 'cabo', 'estero', 'mar', 'oceano', 'lago', 'playa', 'morro', 'loma', 'lomas',
              'hato', 'villa', 'pueblo', 'provincia', 'estado', 'departamento', 'territorio', 'canton', 'distrito', 'peninsula', 'cordillera',
              'region', 'arroyo', 'brazo', 'cano', 'embalse', 'cienega', 'cienaga', 'archipielago', 'costa'}
ARTICLES = {'de', 'del', 'la', 'el', 'las', 'los', 'the', 'of'}
GENERIC = {'oriental', 'central', 'occidental', 'norte', 'sur', 'este', 'oeste', 'grande', 'nuevo', 'nueva', 'santa', 'san', 'alto', 'alta', 'bajo', 'baja', 'rios', 'nacional', 'isla', 'valle', 'paramo', 'andes', 'negro', 'blanco', 'verde', 'seco', 'seca', 'salado', 'dulce', 'chico', 'viejo', 'vieja', 'real', 'nueva granada', 'colombia', 'mar', 'tierra', 'tierras', 'tierras altas de guinea', 'pacifico', 'atlantico', 'antillas', 'meridiano', 'provincia', 'canton', 'territorio', 'distrito', 'estado', 'capital', 'limite', 'limites'}

def core(n):
    """drop leading generic/type words and articles: 'golfo de uraba' -> 'uraba'; 'san gil' stays."""
    t = n.split()
    while len(t) > 1 and (t[0] in TYPE_WORDS or t[0] in ARTICLES): t = t[1:]
    return ' '.join(t)

entries = []
seen = set()
def add(name, typ, country, lon=None, lat=None, geom=None, src='', extra_variants=(), rank=0):
    n = norm(name)
    if not n or len(n) < 3: return
    key = (n, typ, round(lon or 0, 2), round(lat or 0, 2))
    if key in seen: return
    seen.add(key)
    variants = {n}
    c = core(n)
    if c != n and len(c) >= 4 and c not in GENERIC: variants.add(c)
    for v in extra_variants:
        v = norm(v)
        if len(v) >= 3: variants.add(v)
    e = {'name': name, 'norm': n, 'variants': sorted(variants), 'type': typ, 'country': country, 'src': src, 'rank': rank}
    if lon is not None: e['lon'] = round(lon, 5); e['lat'] = round(lat, 5)
    if geom is not None: e['geom'] = geom.wkt
    entries.append(e)

# 1. municipality seats / cities (GeoNames via dr5hn)
rows = json.load(open(G + 'json-cities.json'))
for r in rows:
    if r.get('country_code') not in ('CO', 'PA', 'VE', 'EC'): continue
    lon, lat = float(r['longitude']), float(r['latitude'])
    if not ROI.contains(Point(lon, lat)): continue
    add(r['name'], 'pop', r['country_code'], lon, lat, src='geonames/dr5hn', rank=int(r.get('population') or 0))

# 2. DANE municipalities (polygons): add any name missing among the seats; also keep polygons for area context
dane = json.load(open(G + 'co_2018_MGN_MPIO_POLITICO.geojson'))
have = {(e['norm'], e['country']) for e in entries}
dane_polys = []
for f in dane['features']:
    p = f['properties']; name = p['MPIO_CNMBR'].title(); geom = shape(f['geometry'])
    dane_polys.append((norm(name), norm(p['DPTO_CNMBR']), geom))
    if (norm(name), 'CO') not in have:
        rp = geom.representative_point()
        add(name, 'pop', 'CO', rp.x, rp.y, src='dane-mgn-2018 (centroide)', rank=0)

# 3. Natural Earth populated places
ne = json.load(open(G + 'ne_10m_populated_places_simple.geojson'))
for f in ne['features']:
    p = f['properties']; lon, lat = f['geometry']['coordinates']
    if not ROI.contains(Point(lon, lat)): continue
    extra = [p['namealt']] if p.get('namealt') else []
    add(p['name'], 'pop', p.get('iso_a2') or '', lon, lat, src='ne-places', extra_variants=extra, rank=int(p.get('pop_max') or 0))

# 4. Natural Earth rivers (lines)
riv = json.load(open(G + 'ne_10m_rivers_lake_centerlines.geojson'))
for f in riv['features']:
    p = f['properties']
    if not f['geometry'] or not f['geometry'].get('coordinates') or not p.get('name'): continue
    s = shape(f['geometry'])
    if not s.intersects(ROI): continue
    s = s.intersection(ROI).simplify(0.01)
    if s.is_empty: continue
    nm = p['name']
    add('Río ' + nm, 'river', '', s.centroid.x, s.centroid.y, geom=s, src='ne-rivers', extra_variants=[nm, 'r ' + nm])

# 5. lakes, marine polys, regions, admin-1 (polygons)
def add_polys(fn, typ, namekey, altkeys=(), country_key=None, filt=None):
    g = json.load(open(G + fn))
    for f in g['features']:
        p = f['properties']
        if not f['geometry'] or not f['geometry'].get('coordinates'): continue
        if filt and not filt(p): continue
        nm = p.get(namekey)
        if not nm: continue
        try: s = shape(f['geometry'])
        except Exception: continue
        if s.is_empty or not s.intersects(ROI): continue
        s = s.intersection(ROI).simplify(0.01)
        if s.is_empty: continue
        extra = [p.get(k) for k in altkeys if p.get(k)]
        rp = s.representative_point()
        add(nm, typ, (p.get(country_key) or '') if country_key else '', rp.x, rp.y, geom=s, src=fn.split('.')[0], extra_variants=extra)
add_polys('ne_10m_lakes.geojson', 'lake', 'name', ('name_es', 'name_alt'))
add_polys('ne_10m_geography_marine_polys.geojson', 'marine', 'name', ('name_es', 'namealt'))
add_polys('ne_10m_geography_regions_polys.geojson', 'region', 'NAME', ('NAME_ES', 'NAMEALT'))
add_polys('ne_10m_admin_1_states_provinces.geojson', 'admin1', 'name', ('name_es', 'name_alt', 'name_local'), country_key='iso_a2',
          filt=lambda p: p.get('iso_a2') in ('CO', 'PA', 'VE', 'EC', 'CR', 'BR', 'PE'))

# 6. manual: historical provinces / states (1850s–1870s), water bodies and features often labelled on these maps
MANUAL = [
    # name, type, lon, lat, variants
    ('Provincia de Vélez', 'admin1', -73.67, 6.0, ['velez']), ('Provincia del Socorro', 'admin1', -73.26, 6.46, ['socorro']),
    ('Provincia de Soto', 'admin1', -73.1, 7.1, ['soto']), ('Provincia de Pamplona', 'admin1', -72.65, 7.37, ['pamplona']),
    ('Provincia de Ocaña', 'admin1', -73.35, 8.24, ['ocana']), ('Provincia de Tunja', 'admin1', -73.37, 5.53, ['tunja']),
    ('Provincia de Tundama', 'admin1', -72.9, 5.85, ['tundama']), ('Provincia de Casanare', 'admin1', -71.5, 5.3, ['casanare']),
    ('Provincia de Bogotá', 'admin1', -74.1, 4.6, ['bogota']), ('Provincia de Mariquita', 'admin1', -74.9, 5.2, ['mariquita']),
    ('Provincia de Antioquia', 'admin1', -75.6, 6.5, ['antioquia']), ('Provincia de Córdova', 'admin1', -75.4, 6.1, ['cordova']),
    ('Provincia de Medellín', 'admin1', -75.57, 6.25, ['medellin']), ('Provincia de Mompós', 'admin1', -74.4, 9.1, ['mompos', 'mompox']),
    ('Provincia de Cartagena', 'admin1', -75.5, 10.0, ['cartagena']), ('Provincia de Sabanilla', 'admin1', -74.9, 10.8, ['sabanilla']),
    ('Provincia de Santa Marta', 'admin1', -74.0, 10.8, ['santa marta']), ('Provincia de Riohacha', 'admin1', -72.9, 11.3, ['riohacha', 'rio hacha', 'rio de la hacha']),
    ('Provincia de Valledupar', 'admin1', -73.25, 10.3, ['valledupar', 'valle dupar', 'valle de upar']), ('Provincia de Panamá', 'admin1', -79.5, 9.0, ['panama']),
    ('Provincia de Veraguas', 'admin1', -81.0, 8.3, ['veraguas']), ('Provincia de Azuero', 'admin1', -80.4, 7.8, ['azuero']),
    ('Provincia de Chiriquí', 'admin1', -82.4, 8.4, ['chiriqui']), ('Estado de Santander', 'admin1', -73.3, 7.0, ['santander']),
    ('Estado de Boyacá', 'admin1', -73.0, 5.6, ['boyaca']), ('Estado de Cundinamarca', 'admin1', -74.0, 4.8, ['cundinamarca']),
    ('Estado del Tolima', 'admin1', -75.2, 4.0, ['tolima']), ('Estado del Cauca', 'admin1', -76.6, 3.0, ['cauca']),
    ('Estado del Magdalena', 'admin1', -73.5, 10.5, ['magdalena']), ('Estado de Bolívar', 'admin1', -75.2, 9.3, ['bolivar']),
    ('Estado de Antioquia', 'admin1', -75.5, 6.8, ['antioquia']), ('Estado de Panamá', 'admin1', -80.0, 8.5, ['panama']),
    ('Territorio de Casanare', 'admin1', -71.5, 5.3, ['casanare']), ('Territorio del Caquetá', 'admin1', -73.0, 0.5, ['caqueta']),
    ('Nueva Granada', 'admin1', -74.0, 5.0, []), ('Venezuela', 'admin1', -67.0, 7.0, []), ('Ecuador', 'admin1', -78.0, -1.0, []),
    ('Costa Rica', 'admin1', -84.0, 10.0, []), ('Brasil', 'admin1', -68.0, -2.0, ['brasil', 'brazil']), ('Perú', 'admin1', -75.0, -4.0, []),
    ('Ciénaga Grande de Santa Marta', 'lake', -74.4, 10.85, ['cienaga grande']), ('Laguna de Tota', 'lake', -72.93, 5.55, ['tota']),
    ('Laguna de Fúquene', 'lake', -73.75, 5.46, ['fuquene']), ('Ciénaga de Zapatosa', 'lake', -73.8, 9.1, ['zapatosa']),
    ('Golfo de Morrosquillo', 'marine', -75.75, 9.55, ['morrosquillo']), ('Golfo del Darién', 'marine', -76.9, 8.8, ['darien']),
    ('Bahía de Cartagena', 'marine', -75.55, 10.35, []), ('Golfo de Venezuela', 'marine', -71.3, 11.5, []),
    ('Golfo de San Miguel', 'marine', -78.3, 8.3, ['san miguel']), ('Bahía de Buenaventura', 'marine', -77.1, 3.85, []),
    ('Mar Caribe', 'marine', -76.0, 12.5, ['mar de las antillas', 'antillas', 'mar caribe']), ('Océano Pacífico', 'marine', -79.5, 5.0, ['pacifico', 'oceano pacifico', 'mar del sur', 'mar pacifico']),
    ('Océano Atlántico', 'marine', -74.0, 12.8, ['atlantico', 'oceano atlantico']),
    ('Río Magdalena', 'river', -74.7, 7.5, ['magdalena']), ('Río Sogamoso', 'river', -73.5, 7.1, ['sogamoso']), ('Río Suárez', 'river', -73.5, 6.2, ['suarez', 'sarabita']),
    ('Río Chicamocha', 'river', -73.0, 6.6, ['chicamocha']), ('Río Lebrija', 'river', -73.5, 7.6, ['lebrija']), ('Río Fonce', 'river', -73.15, 6.55, ['fonce']),
    ('Río Opón', 'river', -73.75, 6.55, ['opon']), ('Río Carare', 'river', -74.0, 6.4, ['carare']), ('Río Minero', 'river', -74.0, 5.75, ['minero']),
    ('Río Ermitaño', 'river', -74.0, 5.9, ['ermitano']), ('Río Horta', 'river', -73.9, 6.0, ['horta']), ('Río Guayabito', 'river', -73.9, 6.3, ['guayabito']),
    ('Río Cesar', 'river', -73.5, 9.8, ['cesar']), ('Río Ariguaní', 'river', -74.0, 9.9, ['ariguani']), ('Río Ranchería', 'river', -72.9, 11.3, ['rancheria']),
    ('Río Sinú', 'river', -75.85, 8.8, ['sinu']), ('Río San Jorge', 'river', -75.1, 8.8, ['san jorge']), ('Río Nechí', 'river', -74.9, 7.7, ['nechi']),
    ('Río Cauca', 'river', -75.5, 7.5, ['cauca']), ('Río Atrato', 'river', -76.9, 7.5, ['atrato']), ('Río San Juan', 'river', -77.0, 4.4, ['san juan']),
    ('Río Patía', 'river', -77.8, 2.1, ['patia']), ('Río Mira', 'river', -78.5, 1.3, ['mira']), ('Río Baudó', 'river', -77.3, 5.1, ['baudo']),
    ('Río Dagua', 'river', -77.0, 3.7, ['dagua']), ('Río Caquetá', 'river', -73.0, 0.5, ['caqueta']), ('Río Putumayo', 'river', -74.0, -0.5, ['putumayo']),
    ('Río Meta', 'river', -71.0, 5.5, ['meta']), ('Río Casanare', 'river', -70.5, 6.0, ['casanare']), ('Río Cravo Norte', 'river', -70.8, 6.2, ['cravo norte', 'cravo']),
    ('Río Cravo Sur', 'river', -71.8, 5.1, ['cravo sur', 'cravo']), ('Río Pauto', 'river', -71.8, 5.4, ['pauto']), ('Río Ariporo', 'river', -70.9, 5.9, ['ariporo']),
    ('Río Cusiana', 'river', -72.4, 4.9, ['cusiana']), ('Río Upía', 'river', -72.7, 4.5, ['upia']), ('Río Tua', 'river', -72.2, 5.2, ['tua']),
    ('Río Arauca', 'river', -70.5, 7.0, ['arauca']), ('Río Guaviare', 'river', -70.0, 3.5, ['guaviare']), ('Río Vichada', 'river', -69.0, 4.9, ['vichada']),
    ('Río Tuira', 'river', -77.8, 8.1, ['tuira']), ('Río Chagres', 'river', -79.7, 9.2, ['chagres']), ('Río Chepo', 'river', -78.9, 9.1, ['chepo', 'bayano']),
    ('Río Chucunaque', 'river', -77.7, 8.3, ['chucunaque']), ('Río Catatumbo', 'river', -72.3, 9.0, ['catatumbo']), ('Río Zulia', 'river', -72.5, 8.2, ['zulia']),
    ('Río Bogotá', 'river', -74.3, 4.6, ['bogota', 'funza']), ('Río Negro', 'river', -74.5, 5.3, ['negro']), ('Río Saldaña', 'river', -75.2, 3.9, ['saldana']),
    ('Río Guatapurí', 'river', -73.3, 10.5, ['guatapuri']), ('Río Fundación', 'river', -74.1, 10.5, ['fundacion']), ('Río Tocuyo', 'river', -69.5, 11.0, ['tocuyo']),
    ('Sierra Nevada de Santa Marta', 'region', -73.8, 10.8, ['sierra nevada', 'nevada de santa marta']), ('Serranía de Perijá', 'region', -73.0, 10.0, ['perija']),
    ('Cordillera Oriental', 'region', -73.5, 5.5, ['oriental']), ('Cordillera Central', 'region', -75.5, 5.0, ['central']), ('Cordillera Occidental', 'region', -76.5, 5.0, ['occidental']),
    ('Nevado del Cocuy', 'region', -72.3, 6.4, ['cocuy']), ('Páramo de Pisba', 'region', -72.5, 5.9, ['pisba']), ('Istmo de Panamá', 'region', -79.8, 9.0, ['istmo']),
    ('Península de la Guajira', 'region', -71.8, 11.9, ['guajira', 'goajira']), ('Cabo de la Vela', 'region', -72.17, 12.2, ['cabo de la vela', 'vela']),
    ('Isla de San Andrés', 'region', -81.7, 12.55, ['san andres']), ('Isla de Providencia', 'region', -81.37, 13.35, ['providencia']),
    ('Archipiélago de las Perlas', 'region', -79.05, 8.4, ['las perlas', 'perlas']), ('Isla de Coiba', 'region', -81.75, 7.45, ['coiba']),
    ('Punta Gallinas', 'region', -71.67, 12.46, ['gallinas']), ('Cabo Corrientes', 'region', -77.55, 5.5, ['corrientes']),
    ('Boca del Opón', 'pop', -73.86, 6.6, ['boca del opon']), ('Puerto Nacional', 'pop', -73.86, 6.6, []), ('Aspinwall', 'pop', -79.9, 9.36, ['colon', 'aspinwall']),
    ('Nuestra Señora del Rosario de Cúcuta', 'pop', -72.5, 7.89, ['rosario de cucuta', 'cucuta']), ('San José de Cúcuta', 'pop', -72.5, 7.89, ['cucuta']),
    ('Villa de Leiva', 'pop', -73.52, 5.63, ['leiva', 'villa de leiva', 'villa de leyva']), ('Mompós', 'pop', -74.43, 9.24, ['mompos', 'mompox']),
    ('Santa Fe de Bogotá', 'pop', -74.08, 4.6, ['santafe', 'santa fe', 'bogota']), ('Panamá', 'pop', -79.53, 8.98, ['panama']),
]
for name, typ, lon, lat, variants in MANUAL:
    add(name, typ, 'HIST', lon, lat, src='manual', extra_variants=variants)

json.dump({'entries': entries}, open(G + 'gazetteer.json', 'w'), ensure_ascii=False)
import collections
print(len(entries), collections.Counter(e['type'] for e in entries), collections.Counter(e['src'] for e in entries))
