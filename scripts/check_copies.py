#!/usr/bin/env python3
"""Ищет в карточках фразы, переписанные из описаний старой базы (часть из них — с kino.mail.ru).

  python3 scripts/check_copies.py work/old-catalog.json

Сравнивает «О чём фильм» и «Почему советуем» с описанием из старой базы по совпадающим
цепочкам из пяти слов. Тексты редакции (origin = editorial) не проверяет: их можно брать за основу.
"""
import glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def words(s):
    return re.findall(r'[а-яёa-z0-9]+', (s or '').lower().replace('ё', 'е'))


def shingles(ws, n=5):
    return {tuple(ws[i:i + n]) for i in range(len(ws) - n + 1)}


def main(old_path):
    old = {x['slug']: x for x in json.load(open(old_path, encoding='utf-8'))}
    facts = {f['slug']: f for f in json.load(open(os.path.join(ROOT, 'site', 'data', 'titles.json'), encoding='utf-8'))}
    found = []
    for path in sorted(glob.glob(os.path.join(ROOT, 'cards', 'batches', '*.json'))):
        for c in json.load(open(path, encoding='utf-8')):
            f = facts.get(c['slug'])
            if c.get('decision') != 'publish' or not f or f['origin'] in ('editorial', 'new'):
                continue
            src = shingles(words(old[f['oldSlug']]['shortDescription']))
            common = src & shingles(words(c['about'] + ' ' + c['whyRecommended']))
            if src and len(common) >= 3 and len(common) / len(src) >= 0.3:
                found.append((c['slug'], os.path.basename(path), len(common), round(len(common) / len(src), 2)))
    for row in found:
        print(*row)
    print(f'карточек с заимствованиями: {len(found)}')
    return found


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(1 if main(sys.argv[1]) else 0)
