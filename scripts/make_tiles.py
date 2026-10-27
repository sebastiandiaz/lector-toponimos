"""Full-resolution 1024 px tiles per map (single native zoom), for the viewer's tile layer: tiles/<stem>/<x>_<y>.jpg"""
import os, json, sys
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
S = './'
OUT = './tiles'; T = 1024; PAPER = (233, 228, 216)
meta = json.load(open(S + 'maps_meta.json'))
index = {}
for stem in sorted(meta):
    im = Image.open(S + f'in/{stem}.jpg').convert('RGB'); W, H = im.size
    os.makedirs(f'{OUT}/{stem}', exist_ok=True); n = 0; total = 0
    nx, ny = (W + T - 1) // T, (H + T - 1) // T
    for ty in range(ny):
        for tx in range(nx):
            tile = im.crop((tx*T, ty*T, min((tx+1)*T, W), min((ty+1)*T, H)))
            if tile.size != (T, T):
                pad = Image.new('RGB', (T, T), PAPER); pad.paste(tile, (0, 0)); tile = pad
            fn = f'{OUT}/{stem}/{tx}_{ty}.jpg'; tile.save(fn, 'JPEG', quality=78, optimize=True); n += 1; total += os.path.getsize(fn)
    index[stem] = {'w': W, 'h': H, 'nx': nx, 'ny': ny, 'n': n, 'bytes': total}
    print(stem, W, H, f'{nx}x{ny}={n} tiles', round(total/1e6, 1), 'MB', flush=True)
json.dump(index, open(OUT + '/index.json', 'w'))
print('total files', sum(v['n'] for v in index.values()), 'total MB', round(sum(v['bytes'] for v in index.values())/1e6, 1))
