"""Build web icons from the exact supplied bird silhouette.

Run with an optional source image to replace the cropped master. Subsequent runs
use the checked-in master and never need the temporary attachment again.
"""
from pathlib import Path
from PIL import Image, ImageDraw
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'public' / 'icons'
OUT.mkdir(parents=True, exist_ok=True)
MASTER = OUT / 'bird-mark.png'
GREEN = (31, 41, 29, 255)

if len(sys.argv) > 1:
    with Image.open(sys.argv[1]) as source:
        bird = source.convert('RGBA')
        bounds = bird.getchannel('A').getbbox()
        if not bounds:
            raise ValueError('Source has no visible bird')
        bird = bird.crop(bounds)
        bird.thumbnail((960, 960), Image.Resampling.LANCZOS)
        master = Image.new('RGBA', (1024, 1024))
        master.alpha_composite(bird, ((1024-bird.width)//2, (1024-bird.height)//2))
        master.save(MASTER)

if not MASTER.exists():
    raise SystemExit('Pass the supplied image path on the first run')

with Image.open(MASTER) as im:
    master = im.convert('RGBA')

def tile(size, mark_scale=.89, rounded=True):
    bg = Image.new('RGBA', (size, size), GREEN)
    if rounded:
        mask = Image.new('L', (size, size))
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, size-1, size-1), radius=round(size*.19), fill=255)
        bg.putalpha(mask)
    mark_size = round(size*mark_scale)
    mark = master.resize((mark_size, mark_size), Image.Resampling.LANCZOS)
    bg.alpha_composite(mark, ((size-mark_size)//2, (size-mark_size)//2))
    return bg

for size in (16, 32, 48, 192, 512):
    tile(size).save(OUT / f'icon-{size}.png')
tile(180).save(OUT / 'apple-touch-icon.png')
tile(512, mark_scale=.72, rounded=False).save(OUT / 'icon-maskable-512.png')
tile(256).save(OUT / 'favicon.ico', format='ICO', sizes=[(16,16),(32,32),(48,48)])
