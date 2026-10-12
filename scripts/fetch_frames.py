#!/usr/bin/env python3
"""Скачивает кадры из старой базы и готовит их для сайта.

  python3 scripts/fetch_frames.py              # только те, которых ещё нет
  python3 scripts/fetch_frames.py --slug fiksiki

Для каждого фильма из site/data/titles.json (поле frameSource):
- site/frames/<slug>.webp — кадр 720×405 для страницы и карточек;
- site/frames/og/<slug>.jpg — 600×316 для превью ссылки в соцсетях.
Кадр обрезается по центру до 16:9. Что не скачалось — в work/frames-failed.json.

Права на кадры не подтверждены: см. раздел «Кадры» в TZ.md.
"""
import concurrent.futures as cf, io, json, os, sys, time

import requests
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'site', 'frames')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/130.0 Safari/537.36')
VERIFY = '/root/.ccr/ca-bundle.crt' if os.path.exists('/root/.ccr/ca-bundle.crt') else True
SIZE, OG = (720, 405), (600, 316)


def fit(img, size):
    return ImageOps.fit(img, size, Image.LANCZOS, centering=(0.5, 0.45))


def fetch(item):
    slug, src = item['slug'], item['frameSource']
    for attempt in range(3):
        try:
            r = requests.get(src, headers={'User-Agent': UA, 'Accept': 'image/avif,image/webp,image/*,*/*;q=0.8'},
                             timeout=30, verify=VERIFY)
            if r.status_code != 200:
                return slug, f'HTTP {r.status_code}'
            img = Image.open(io.BytesIO(r.content))
            img = ImageOps.exif_transpose(img).convert('RGB')
            if img.width < 400:
                return slug, f'слишком маленький кадр: {img.width}×{img.height}'
            fit(img, SIZE).save(os.path.join(OUT, f'{slug}.webp'), 'WEBP', quality=72, method=6)
            fit(img, OG).save(os.path.join(OUT, 'og', f'{slug}.jpg'), 'JPEG', quality=70, optimize=True, progressive=True)
            return slug, None
        except Exception as exc:          # сеть и битые файлы: пробуем ещё раз
            err = f'{type(exc).__name__}: {str(exc)[:100]}'
            time.sleep(2 * (attempt + 1))
    return slug, err


def main():
    os.makedirs(os.path.join(OUT, 'og'), exist_ok=True)
    titles = json.load(open(os.path.join(ROOT, 'site', 'data', 'titles.json'), encoding='utf-8'))
    only = sys.argv[sys.argv.index('--slug') + 1] if '--slug' in sys.argv else None
    todo = [t for t in titles if t.get('frameSource') and (t['slug'] == only if only else
            not os.path.exists(os.path.join(OUT, f'{t["slug"]}.webp')))]
    failed = {}
    with cf.ThreadPoolExecutor(12) as ex:
        for slug, err in ex.map(fetch, todo):
            if err:
                failed[slug] = err
    os.makedirs(os.path.join(ROOT, 'work'), exist_ok=True)
    json.dump(failed, open(os.path.join(ROOT, 'work', 'frames-failed.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'скачано: {len(todo) - len(failed)}, не вышло: {len(failed)}')


if __name__ == '__main__':
    main()
