#!/usr/bin/env python3
"""Готовит каталог из старой базы приложения nen_app (data/generated/watch.json).

  python3 site/prepare_data.py work/old-catalog.json

Что делает:
- чистит названия от пометок Википедии: «Лесной разбойник (фильм, 1974)» → «Лесной разбойник»;
- делает читаемые адреса страниц из русского названия: moy-sosed-totoro, cheburashka-2023;
- сводит семь старых типов к четырем разделам сервиса: мультфильм, мультсериал, фильм, сериал;
- убирает записи, которые редакция исключила (fixes/removed.csv);
- пишет факты в site/data/titles.json, а входные партии для авторов карточек — в work/in/.

Тексты старой базы в каталог не попадают: часть из них скопирована с kino.mail.ru,
часть собрана по шаблону. Авторы карточек получают их только как справку.
"""
import csv, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BATCH = 40

TRANSLIT = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
                    ['a', 'b', 'v', 'g', 'd', 'e', 'e', 'zh', 'z', 'i', 'y', 'k', 'l', 'm', 'n', 'o', 'p', 'r', 's', 't',
                     'u', 'f', 'h', 'ts', 'ch', 'sh', 'shch', '', 'y', '', 'e', 'yu', 'ya']))

# Тип в старой базе → раздел сервиса и уточнение формата
KIND = {
    'animated-feature': ('multfilm', 'feature'),
    'animated-short': ('multfilm', 'short'),
    'animated-series': ('multserial', 'series'),
    'movie': ('film', 'feature'),
    'short-film': ('film', 'short'),
    'documentary': ('film', 'documentary'),
    'series': ('serial', 'series'),
}
# Откуда запись в старой базе: по ней видно, насколько можно доверять текстам
ORIGIN_GROUPS = [
    (re.compile(r'^mail-'), 'kino-mail'),        # описания скопированы с kino.mail.ru
    (re.compile(r'^wikidata-'), 'wikidata'),     # автоимпорт из Википедии, описания по шаблону
    (re.compile(r'^work-|-\d{4}-\d+$'), 'import'),  # автоимпорт, часть описаний по шаблону
]
WIKI_PAREN = re.compile(r'\s*\((?:(?:фильм|мультфильм|сериал|мультсериал)(?:,\s*\d{4})?|\d{4})\)\s*$')
TEMPLATE_DESC = re.compile(r'страна производства|Формат и хронометраж|Хронометраж —|создано в стране|Продолжительность —|'
                           r'которым предстоит принимать решения')


def slugify(s):
    s = ''.join(TRANSLIT.get(ch, ch) for ch in s.lower())
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', s)).strip('-')


def origin_group(old_slug):
    for rx, name in ORIGIN_GROUPS:
        if rx.search(old_slug):
            return name
    return 'editorial'


def removed():
    path = os.path.join(ROOT, 'fixes', 'removed.csv')
    if not os.path.exists(path):
        return set()
    with open(path, encoding='utf-8') as f:
        return {row['oldId'] for row in csv.DictReader(f)}


def main(src):
    old = json.load(open(src, encoding='utf-8'))
    skip = removed()
    titles = []
    for x in old:
        if x['id'] in skip:
            continue
        kind, fmt = KIND[x['kind']]
        title = WIKI_PAREN.sub('', x['title']).strip()
        original = WIKI_PAREN.sub('', re.sub(r'\s*\((?:\d{4} )?(?:film|TV series)\)$', '', x.get('originalTitle') or '')).strip()
        dur = x['duration']
        item = {
            'id': x['id'],
            'title': title,
            'originalTitle': original if original and original != title else None,
            'year': x['year'],
            'kind': kind,
            'format': fmt,
            'country': x['country'],
            'minutes': dur.get('minutes'),
            'episodeMinutes': dur.get('episodeMinutes'),
            'seasons': dur.get('seasonCount'),
            'episodes': dur.get('episodeCount'),
            'officialRating': ({'value': x['officialRating']['value'], 'sourceUrl': x['officialRating']['sourceUrl']}
                               if x.get('officialRating') else None),
            'frameSource': (x.get('frame') or {}).get('url'),
            'oldSlug': x['slug'],
            'origin': origin_group(x['slug']),
        }
        titles.append((item, x))

    # Адрес страницы — по названию; одинаковые названия различаем годом, потом разделом
    base = {}
    for item, _ in titles:
        base.setdefault(slugify(item['title']), []).append(item)
    for s, items in base.items():
        for item in items:
            item['slug'] = s if len(items) == 1 else f'{s}-{item["year"]}'
    seen = {}
    for item, _ in titles:
        seen.setdefault(item['slug'], []).append(item)
    for s, items in seen.items():
        if len(items) > 1:
            for item in items:
                item['slug'] = f'{s}-{item["kind"]}'

    facts = [item for item, _ in titles]
    os.makedirs(os.path.join(ROOT, 'site', 'data'), exist_ok=True)
    json.dump(facts, open(os.path.join(ROOT, 'site', 'data', 'titles.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # Входные партии для авторов карточек: сначала записи с текстами редакции
    order = {'editorial': 0, 'kino-mail': 1, 'import': 2, 'wikidata': 3}
    work = []
    for item, x in sorted(titles, key=lambda t: (order[t[0]['origin']], t[0]['kind'], t[0]['title'])):
        desc = x['shortDescription']
        ref = {
            'oldDescription': None if TEMPLATE_DESC.search(desc) else desc,
            'oldAge': {k: v for k, v in x['nenAgeRecommendation'].items() if k in ('minAge', 'maxAge')},
            'oldSensitive': x['sensitiveTopics'],
            'oldGenres': x['genres'],
        }
        if item['origin'] == 'editorial':
            ref['oldAgeReason'] = x['nenAgeRecommendation']['rationale']
            ref['oldQuestions'] = x['discussionTopics']
        work.append({k: item[k] for k in ('slug', 'title', 'originalTitle', 'year', 'kind', 'format', 'country',
                                          'minutes', 'episodeMinutes', 'officialRating', 'origin')} | {'reference': ref})
    out_dir = os.path.join(ROOT, 'work', 'in')
    os.makedirs(out_dir, exist_ok=True)
    for i in range(0, len(work), BATCH):
        n = i // BATCH + 1
        json.dump(work[i:i + BATCH], open(os.path.join(out_dir, f'batch-{n:03d}.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    print(f'записей: {len(facts)}, убрано редакцией: {len(skip)}, партий: {(len(work) + BATCH - 1) // BATCH}')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
