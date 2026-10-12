#!/usr/bin/env python3
"""Собирает пометки авторов карточек для редакции.

  python3 scripts/collect_notes.py

- cards/review.csv — по строке на каждую запись каталога: решение, источник текста, возраст,
  маркировка, исправленные факты и пометки «сверить»;
- cards/PROGRESS.md — сколько карточек опубликовано, отложено и пропущено, по разделам.
"""
import collections, csv, glob, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    facts = {f['slug']: f for f in json.load(open(os.path.join(ROOT, 'site', 'data', 'titles.json'), encoding='utf-8'))}
    cards = {}
    for path in sorted(glob.glob(os.path.join(ROOT, 'cards', 'batches', '*.json'))):
        for c in json.load(open(path, encoding='utf-8')):
            cards[c['slug']] = dict(c, batch=os.path.basename(path)[:-5])
    for c in json.load(open(os.path.join(ROOT, 'cards', 'pilot.json'), encoding='utf-8')):
        cards[c['slug']] = dict(c, batch='pilot')
    hold = {}
    with open(os.path.join(ROOT, 'fixes', 'hold.csv'), encoding='utf-8') as f:
        for row in csv.DictReader(f):
            hold[row['slug']] = row['reason']

    rows, stats = [], collections.Counter()
    by_kind = collections.Counter()
    for slug, f in facts.items():
        c = cards.get(slug)
        rating = (((c or {}).get('fixes') or {}).get('officialRating') or f.get('officialRating') or {}).get('value', '')
        if not c:
            status = 'нет карточки'
        elif c['decision'] == 'skip':
            status = 'пропущено'
        elif slug in hold:
            status = 'не публикуется по решению издателя'
        else:
            status = 'опубликовано'
            by_kind[(c.get('fixes') or {}).get('kind') or f['kind']] += 1
        stats[status] += 1
        age = ''
        if c and c['decision'] == 'publish':
            # Как на сайте: с маркировкой 16+ и 18+ — не раньше 16 лет.
            lo = max(c['ageMin'], 16) if rating[:2] in ('16', '18') else c['ageMin']
            hi = c['ageMax'] if c['ageMax'] and c['ageMax'] >= lo else None
            age = f'{lo}–{hi}' if hi else f'с {lo}'
        rows.append({
            'slug': slug, 'название': f['title'], 'год': f['year'], 'раздел': f['kind'], 'статус': status,
            'источник текста': (c or {}).get('source', ''), 'возраст НЭН': age, 'маркировка': rating,
            'исправлено': '; '.join(f'{k}: {v}' for k, v in ((c or {}).get('fixes') or {}).items()),
            'причина': (c or {}).get('skipReason') or hold.get(slug, ''),
            'пометки': ' '.join((c or {}).get('editorNotes') or []),
            'партия': (c or {}).get('batch', ''), 'откуда в старой базе': f['origin'],
        })
    with open(os.path.join(ROOT, 'cards', 'review.csv'), 'w', newline='', encoding='utf-8-sig') as out:
        w = csv.DictWriter(out, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r['статус'], r['раздел'], r['название'])))

    names = {'multfilm': 'мультфильмы', 'multserial': 'мультсериалы', 'film': 'фильмы', 'serial': 'сериалы'}
    lines = ['# Ход работы над карточками', '',
             'Собирается командой `python3 scripts/collect_notes.py`. Подробности по каждой записи — в [review.csv](review.csv).', '',
             '| Статус | Записей |', '|---|---|']
    lines += [f'| {k} | {v} |' for k, v in stats.most_common()]
    lines += ['', '**Опубликовано по разделам:** ' + ', '.join(f'{names[k]} — {v}' for k, v in by_kind.most_common()), '']
    open(os.path.join(ROOT, 'cards', 'PROGRESS.md'), 'w', encoding='utf-8').write('\n'.join(lines))
    print(', '.join(f'{k}: {v}' for k, v in stats.most_common()))


if __name__ == '__main__':
    main()
