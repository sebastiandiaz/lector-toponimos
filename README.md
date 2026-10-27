# Lector de topónimos (piloto)

Lectura automática y geocodificación de topónimos en diez mapas de la Comisión Corográfica (1850–1874) de la
[Mapoteca Digital de la Biblioteca Nacional de Colombia](https://www.bibliotecanacional.gov.co/es-co/colecciones/biblioteca-digital/mapoteca/Paginas/index.aspx),
un piloto del proyecto [Comisión Corográfica Digital](https://comisioncorograficadigital.github.io/).

Desarrollo: Sebastián Díaz Ángel.

## El visor

`index.html` es el visor: cada rótulo detectado sobre la imagen (a resolución completa, servida por mosaicos de 1 024 px desde `tiles/`),
coloreado por estado —punto de control, confirmado cerca, río/región, solo léxico, sin correspondencia—, con ficha, formulario de
corrección, minimapa que compara la caja del inventario con la extensión estimada, y la pestaña **Informe** con resultados, método y evaluación.

### Corregir y añadir topónimos

- **Corregir**: clic en cualquier caja → formulario con la transcripción correcta, el tipo y el veredicto (correcta, corregida, no es topónimo, ilegible).
- **Añadir**: botón «＋ Añadir topónimo», se dibuja un rectángulo sobre un rótulo que el lector no detectó y se escribe su texto
  (tipo, nombre normalizado y nota opcionales). El visor calcula la posición geográfica estimada con la transformación del mapa.
- **Guardar**: en claude.ai las correcciones van a la base compartida del artefacto; en GitHub Pages o como archivo local se guardan
  en el navegador de cada persona. En todos los casos se pueden **exportar en JSON** o **enviar a GitHub** con el botón del mismo
  nombre, que abre un *issue* de este repositorio con los registros ya escritos (solo hay que pulsar «Submit new issue»).
- **Reunir**: `python3 scripts/collect_corrections.py` lee los *issues* con la etiqueta `correcciones`, guarda uno por archivo en
  `correcciones/` y consolida `correcciones/todas.json`; `scripts/make_dataset.py correcciones/todas.json` convierte ese conjunto
  (correcciones y topónimos nuevos) en recortes y etiquetas para afinar el reconocedor, y en un suplemento del gacetero.

## Datos (`datos/`)

- `<mapa>.toponimos.csv` — todas las frases leídas: texto OCR, confianza, posición en píxeles originales, ángulo, estado, nombre del
  gacetero, tipo, lon/lat, similitud, residuo en km y posición estimada.
- `<mapa>.geojson` — topónimos confirmados (puntos) y extensión estimada de la imagen (polígono).
- `<mapa>.gcps.csv` — puntos de control `x, y, lon, lat` listos para importar en Map Warper.
- `toponimos_confirmados.csv` — tabla consolidada de los 287 topónimos confirmados en los diez mapas.
- `maps_meta.json` — correspondencia mapa ↔ registro del inventario (código, título, caja, escala, Map Warper).
- `eval.json` — evaluación visual por mapa. `gazetteer.json` — gacetero regional (2 460 entradas).

Mapas: Vélez 1850, Socorro 1850, Soto 1851 (Codazzi, manuscritos); Cauca 1864, Magdalena 1864, Boyacá 1864, Bolívar 1864
(Paz / Ponce de León); Panamá 1874 y Magdalena 1871 (Ayala); Casanare 1856 (Codazzi).

## Cadena de procesamiento (`scripts/`)

1. `spot.py` — mosaicos de 1 024 px con solape, detección (DB‑ResNet50) y lectura (PARSeq) con OnnxTR en cinco orientaciones,
   fusión de duplicados y agrupación en frases. `--norm` normaliza el fondo (impresos desvaídos); `--scale` amplía escaneos de baja resolución.
2. `gazetteer.py` — gacetero regional: municipios (GeoNames vía dr5hn/countries-states-cities-database; DANE MGN 2018),
   lugares de Panamá, Venezuela y Ecuador, ríos, lagos, golfos y departamentos de Natural Earth, nombres históricos de 1850–1875.
3. `geocode.py` — corrección difusa post‑OCR, RANSAC afín + polinomio de 2.º grado imagen→lon/lat, confirmación espacial, salidas.
4. `viewer.py` — genera el visor. `make_tiles.py` — mosaicos. `evalsheet.py` — hojas de evaluación.
5. `make_dataset.py` + `entrenamiento.md` — de las correcciones exportadas al conjunto de entrenamiento (formato docTR) para afinar el reconocedor.

```
pip install "onnxtr[cpu]" rapidfuzz shapely pillow numpy
python3 scripts/spot.py mapa.jpg salida.json --scale 1.0           # --norm --scale 3.0 para impresos en baja resolución
python3 scripts/geocode.py salida.json mapa --bbox=O,S,E,N
```

## Resultados del piloto

11 214 palabras y 7 854 rótulos leídos; 287 topónimos confirmados (164 puntos de control, 78 cercanos, 45 ríos/regiones);
transformación geográfica para 8 de 10 hojas. Detección de rótulos 85–90 %; lectura exacta 23–38 % en la cursiva de Codazzi y ~50 %
en impresos de alta resolución; precisión de los confirmados 71–92 %. Los cinco mapas en resolución web no son legibles: hacen falta los másteres.
Detalle en la pestaña Informe del visor.

## Licencias y créditos

Código: MIT. Datos derivados: CC BY 4.0. Imágenes: Mapoteca Digital, Biblioteca Nacional de Colombia.
Gacetero: GeoNames (CC BY 4.0) vía [dr5hn/countries-states-cities-database](https://github.com/dr5hn/countries-states-cities-database) (ODbL),
DANE MGN 2018, [Natural Earth](https://www.naturalearthdata.com/) (dominio público).
Modelos: [OnnxTR](https://github.com/felixdittrich92/OnnxTR) (Apache 2.0). Método inspirado en [mapKurator](https://github.com/knowledge-computing/mapkurator-system).
