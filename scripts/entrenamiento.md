# De las correcciones al reentrenamiento

## 1. Qué produce el visor
Cada corrección guardada en el visor (base compartida del artefacto, o el JSON exportado con «Exportar correcciones») es un registro:

```
{mapa, codigo, i, ocr, texto, tipo, veredicto, gacetero, bbox_px, autor, fecha}
```
- `veredicto = correcto`: la lectura automática era buena (muestra positiva tal cual).
- `veredicto = corregido`: `texto` es la transcripción correcta (muestra positiva corregida).
- `veredicto = no-toponimo`: la caja es texto que no es rótulo (cuadro, nota, graticula): negativo para el detector.
- `veredicto = ilegible`: se descarta.

## 2. Construir el conjunto de entrenamiento (aquí mismo)
```
python3 -I make_dataset.py correcciones-toponimos-AAAA-MM-DD.json --out dataset
```
Produce:
- `dataset/recognition/images/*.png` + `labels.json` — recortes enderezados a resolución completa, formato `RecognitionDataset` de docTR.
- `dataset/detection/<mapa>.json` — polígonos validados (y negativos) en el formato `DetectionDataset` de docTR.
- `dataset/gacetero_suplemento.csv` — nombres corregidos que no existen en el gacetero, con la lon/lat estimada por la transformación del mapa.

## 3. Afinar el reconocedor (requiere GPU: Colab / máquina del IGAC o la BNC)
docTR (PyTorch) trae el script de referencia; PARSeq es el mismo modelo que usa OnnxTR aquí.
```
pip install "python-doctr[torch]"
git clone https://github.com/mindee/doctr && cd doctr/references/recognition
python train_pytorch.py parseq --train_path ../../dataset/recognition --val_path ../../dataset_val/recognition \
    --pretrained --epochs 15 --lr 1e-4 --batch_size 64 --vocab latin \
    --name parseq_codazzi
```
- Con **200–300 rótulos corregidos** ya se nota la mejora en la letra cursiva de un mismo autor (Codazzi/Paz); con **1 000–2 000** el modelo generaliza a toda la serie.
- Conviene separar un 10 % como validación y medir la exactitud por mapa, no global.
- Exportar a ONNX para usarlo en esta misma cadena (OnnxTR): `python ../../scripts/export_onnx.py` o, desde Python, `doctr.models.recognition.parseq(...).export_onnx(...)`; luego `reco_arch` apunta al archivo `.onnx` en `spot.py`.

Para el **detector** (DB‑ResNet50) el procedimiento es el mismo con `references/detection/train_pytorch.py` y los JSON de `dataset/detection/`; vale la pena solo si hay muchos rótulos que no reciben caja (en el piloto la detección ya supera el 85 %, el cuello de botella es la lectura).

## 4. Lo que mejora sin entrenar nada
- `gacetero_suplemento.csv` se incorpora al gacetero (`gazetteer.py`) → en la siguiente corrida esos nombres se confirman espacialmente.
- Los pares (`ocr`, `texto`) alimentan una tabla de confusiones (s↔z, rn↔m, cursiva «ſ»…) que se usa como reglas de post‑OCR antes de la comparación difusa.
- Los `no-toponimo` enseñan al filtro a descartar cuadros y notas por zona de la hoja (la posición de las cajas descartadas delimita las áreas de tablas).

## 5. Ciclo
1. Correr el piloto → 2. corregir en el visor (poco: 20–40 rótulos por mapa) → 3. exportar → 4. `make_dataset.py` → 5. afinar en GPU → 6. exportar ONNX → 7. volver a correr con el modelo afinado. Cada vuelta reduce el trabajo de corrección de la siguiente.
