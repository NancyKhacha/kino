#!/usr/bin/env python3
"""Генератор сервиса «Что посмотреть с детьми» (n-e-n.ru/kino/) в виде готового HTML.

  python3 site/build.py                            # рабочая версия: noindex, папка docs/
  NEN_PREVIEW=0 python3 site/build.py --out dist   # сборка для боевого сайта

Каждая страница содержит весь текст, ссылки и разметку schema.org прямо в HTML —
JavaScript только улучшает работу (фильтры каталога, подбор, избранное, «Поделиться»).

Данные:
- site/data/titles.json — факты о фильмах (см. site/prepare_data.py);
- cards/pilot.json, cards/batches/*.json — карточки редакции; на сайт попадают только decision = publish;
- site/content/*.json — словари, подборки, вступления посадочных страниц, статьи НЭН;
- site/frames/ — кадры (см. scripts/fetch_frames.py).
"""
import datetime, glob, html, json, os, re, shutil, sys
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREVIEW = os.environ.get('NEN_PREVIEW', '1') != '0'
BASE = '/kino'                          # путь сервиса на сайте; совпадает с путем на GitHub Pages
ORIGIN = 'https://n-e-n.ru'             # для canonical, og:url и разметки
# Полный адрес сайта со своими картинками: в превью — GitHub Pages, на боевом — n-e-n.ru
SITE_ABS = os.environ.get('NEN_SITE_ABS') or ('https://nancykhacha.github.io/kino' if PREVIEW else ORIGIN + BASE)
OG_DEFAULT = (SITE_ABS + '/assets/og.jpg', 1200, 630, 'Семья выбирает фильм перед телевизором — иллюстрация НЭН')
NO_YO = os.environ.get('NEN_YO', '0') != '1'   # в статьях НЭН пишут без «ё»
PER_PAGE = 48
OUT = os.path.join(ROOT, sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else 'docs')
TODAY = datetime.date.today().isoformat()

KINDS = {
    'multfilm': dict(section='multfilmy', one='Мультфильм', gen='мультфильма', plural='Мультфильмы',
                     h1='Мультфильмы для детей', forms=('мультфильм', 'мультфильма', 'мультфильмов'), ld='Movie'),
    'multserial': dict(section='multserialy', one='Мультсериал', gen='мультсериала', plural='Мультсериалы',
                       h1='Мультсериалы для детей', forms=('мультсериал', 'мультсериала', 'мультсериалов'), ld='TVSeries'),
    'film': dict(section='filmy', one='Фильм', gen='фильма', plural='Фильмы',
                 h1='Фильмы для детей', forms=('фильм', 'фильма', 'фильмов'), ld='Movie'),
    'serial': dict(section='serialy', one='Сериал', gen='сериала', plural='Сериалы',
                   h1='Сериалы для детей и подростков', forms=('сериал', 'сериала', 'сериалов'), ld='TVSeries'),
}
FORMAT_LABEL = {('multfilm', 'short'): 'Короткометражный мультфильм', ('film', 'short'): 'Короткометражный фильм',
                ('film', 'documentary'): 'Документальный фильм'}
# Возрастные страницы: «Что посмотреть с ребёнком 5 лет». Подростки — отдельная страница.
AGES = list(range(2, 18))
# Раздел × возраст: «Мультфильмы для детей 3 лет». Только там, где есть поисковый спрос и хватает фильмов.
SECTION_AGES = {'multfilm': range(2, 18), 'multserial': range(2, 18), 'film': range(5, 18), 'serial': range(8, 18)}
MIN_LIST = 6          # меньше — страницу не делаем: тонкий список вредит поиску

TRANSLIT = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
                    ['a', 'b', 'v', 'g', 'd', 'e', 'e', 'zh', 'z', 'i', 'y', 'k', 'l', 'm', 'n', 'o', 'p', 'r', 's', 't',
                     'u', 'f', 'h', 'ts', 'ch', 'sh', 'shch', '', 'y', '', 'e', 'yu', 'ya']))


# ── Текст ────────────────────────────────────────────────────────────────────

def yo(s):
    return s.replace('ё', 'е').replace('Ё', 'Е') if NO_YO and isinstance(s, str) else s


# Неразрывные пробелы: короткие слова не висят в конце строки, тире не переносится в начало,
# число не отрывается от слова («5 лет»).
NBSP = ' '
SHORT_WORDS = re.compile(r'(?<![^\s («„"—])([А-Яа-яЁёA-Za-z]{1,2}|(?i:для|без|под|над|про|при|обо|изо|или|что|как|это|все|его|еще|уже))'
                         r' (?=\S)')
TYPO_RULES = [
    (re.compile(r' (?=[—–] )'), NBSP),
    (re.compile(r'(?<=\d) (?=[А-Яа-яЁё%])'), NBSP),
    (re.compile(r'(?<=\b[А-ЯЁA-Z]\.) (?=[А-ЯЁA-Z])'), NBSP),
    (re.compile(r' (?=(?:ли|же|бы|ль)\b)'), NBSP),
    (re.compile(r'(?<=\d)–(?=\d)'), '\u2060–\u2060'),            # «4–10 лет» не разрывается на тире
]


def typo(text):
    if not isinstance(text, str):
        return text
    text = SHORT_WORDS.sub(lambda m: m.group(1) + NBSP, text)
    for rx, rep in TYPO_RULES:
        text = rx.sub(rep, text)
    return text


def typo_html(doc):
    """Типографика для текста страницы: только <body>, мимо тегов, скриптов и стилей."""
    head, sep, body = doc.partition('<body')
    parts = re.split(r'(<[^>]+>)', body)
    skip = False
    for i, part in enumerate(parts):
        if part.startswith('<'):
            tag = part[1:].split(None, 1)[0].lower().rstrip('>') if len(part) > 2 else ''
            if tag in ('script', 'style', 'textarea'):
                skip = True
            elif tag in ('/script', '/style', '/textarea'):
                skip = False
        elif part and not skip and i:
            parts[i] = typo(part)
    return head + sep + ''.join(parts)


def e(s):
    return html.escape(yo(str(s)), quote=True)


def slugify(s):
    s = ''.join(TRANSLIT.get(ch, ch) for ch in s.lower())
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', s)).strip('-')


def plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return few
    return many


def age_word(n):
    return plural(n, 'год', 'года', 'лет')


def age_gen(n):
    """«для детей 1 года», «для детей 5 лет», «с 3 лет»."""
    return f'{n} года' if n % 10 == 1 and n % 100 != 11 else f'{n} лет'


def kid(n, case='gen'):
    """С 13 лет говорим «подросток»: «для подростков 14 лет», «с подростком 14 лет»."""
    if case == 'gen':
        return 'детей' if n < 13 else 'подростков'
    return 'ребёнком' if n < 13 else 'подростком'


def age_slug(n):
    return f'{n}-' + {'год': 'god', 'года': 'goda', 'лет': 'let'}[age_word(n)]


def count_word(n, kind=None):
    forms = KINDS[kind]['forms'] if kind else ('фильм', 'фильма', 'фильмов')
    return f'{n} {plural(n, *forms)}'


def short(text, limit):
    text = re.sub(r'\s+', ' ', text or '').strip().rstrip('…')
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(' ', 1)[0].rstrip(',;:—-') + '…'


def first_sentences(text, limit=150):
    text = re.sub(r'\s+', ' ', text or '').strip()
    out = ''
    for sent in re.split(r'(?<=[.!?…])\s+', text):
        if out and len(out) + len(sent) > limit:
            break
        out = (out + ' ' + sent).strip()
    return short(out, limit + 40)


def url(path):
    return f'{BASE}{path}'


MONTHS = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']


def ru_date(iso):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', iso or '')
    return f'{int(m.group(3))} {MONTHS[int(m.group(2)) - 1]} {m.group(1)}' if m else ''


def frame_src(t):
    return url(f'/frames/{t["key"]}.webp')


# ── Данные ───────────────────────────────────────────────────────────────────

def load_cards():
    cards = {}
    for path in sorted(glob.glob(os.path.join(ROOT, 'cards', 'batches', '*.json'))):
        for c in json.load(open(path, encoding='utf-8')):
            cards[c['slug']] = c
    for c in json.load(open(os.path.join(ROOT, 'cards', 'pilot.json'), encoding='utf-8')):
        cards[c['slug']] = c          # образцы редакции главнее
    return cards


def content(name, default=None):
    path = os.path.join(ROOT, 'site', 'content', name)
    return json.load(open(path, encoding='utf-8')) if os.path.exists(path) else default


def age_label(lo, hi):
    if hi is None:
        return f'с {age_gen(lo)}'
    return f'{lo}–{hi} {age_word(hi)}'


def duration_label(t):
    if t['kind'] in ('multserial', 'serial'):
        return f'серии по {t["episodeMinutes"]} мин' if t.get('episodeMinutes') else 'сериал'
    m = t.get('minutes')
    if not m:
        return ''
    return f'{m} мин' if m < 60 else f'{m // 60} ч {m % 60:02d} мин' if m % 60 else f'{m // 60} ч'


def rating_age(f):
    m = re.match(r'(\d+)', (f.get('officialRating') or {}).get('value', ''))
    return int(m.group(1)) if m else 0


def held():
    """Карточки, которые ждут решения редакции (fixes/hold.csv): на сайт не попадают."""
    import csv
    path = os.path.join(ROOT, 'fixes', 'hold.csv')
    if not os.path.exists(path):
        return set()
    with open(path, encoding='utf-8') as f:
        return {row['slug'] for row in csv.DictReader(f)}


def load():
    vocab = content('vocab.json')
    hold = held()
    facts = json.load(open(os.path.join(ROOT, 'site', 'data', 'titles.json'), encoding='utf-8'))
    cards = load_cards()
    frames = {os.path.basename(p)[:-5] for p in glob.glob(os.path.join(ROOT, 'site', 'frames', '*.webp'))}
    titles = []
    for f in facts:
        c = cards.get(f['slug'])
        if not c or c.get('decision') != 'publish' or f['slug'] in hold:
            continue
        # Взрослое кино (маркировка 16+ и 18+) — в подростковой части каталога, не раньше 16 лет.
        # Решение издателя: в НЭН подростки — это до 20 лет, как в книжном сервисе.
        t = dict(f)
        t.update({k: v for k, v in (c.get('fixes') or {}).items() if v not in (None, '', [])})
        if t.get('originalTitle') == t['title']:
            t['originalTitle'] = None
        k = KINDS[t['kind']]
        t['key'] = f['slug']          # ключ карточки, кадра, подборок и статей НЭН
        t['slug'] = slugify(t['title'])       # адрес — по названию (исправленному, если автор его поправил)
        age_min = max(c['ageMin'], 16) if rating_age(t) >= 16 else c['ageMin']
        age_max = c['ageMax'] if c['ageMax'] is None or c['ageMax'] >= age_min else None
        t.update(card=c, ageMin=age_min, ageMax=age_max, ageLabel=age_label(age_min, age_max),
                 themes=[x for x in c['themes'] if x in vocab['themes']], moods=[x for x in c['mood'] if x in vocab['moods']],
                 sensitive=[x for x in c['sensitiveTopics'] if x in vocab['sensitive']],
                 frame=t['key'] in frames,
                 typeLabel=FORMAT_LABEL.get((t['kind'], t.get('format')), k['one']))
        t['snippet'] = first_sentences(c['about'], 140)
        t['draft'] = False
        t['duration'] = duration_label(t)
        # Порядок в списках: сначала карточки, написанные по знанию фильма и с кадром, потом остальные
        t['rank'] = {'knowledge': 0, 'research': 1}.get(c['source'], 2) + (0 if t['frame'] else 1)
        titles.append(t)
    # Адреса уникальны внутри раздела: одинаковые названия различаем годом
    seen = {}
    for t in titles:
        seen.setdefault((t['kind'], t['slug']), []).append(t)
    for group in seen.values():
        if len(group) > 1:
            for t in group:
                t['slug'] = f'{t["slug"]}-{t["year"]}'
    seen = {}
    for t in titles:
        seen.setdefault((t['kind'], t['slug']), []).append(t)
    for group in seen.values():
        if len(group) > 1:                    # тот же год — последняя надежда на старый ключ
            for t in group:
                t['slug'] = t['key']
    for t in titles:
        t['path'] = f'/{t["kind"]}/{t["slug"]}/'
        t['url'] = url(t['path'])
    titles.sort(key=lambda t: (t['rank'], 0 if t['origin'] == 'editorial' else 1, -t['year'], t['title']))
    return vocab, titles


def similar(titles):
    """Похожие: общие темы, тот же раздел, близкий возраст."""
    by_theme = {}
    for t in titles:
        for th in t['themes']:
            by_theme.setdefault(th, []).append(t)
    for t in titles:
        scores = {}
        for th in t['themes']:
            for o in by_theme[th]:
                if o is not t:
                    scores[o['slug']] = scores.get(o['slug'], 0) + 2
        pool = {o['slug']: o for th in t['themes'] for o in by_theme[th]}
        ranked = []
        for slug, s in scores.items():
            o = pool[slug]
            s += 1.5 if o['kind'] == t['kind'] else 0
            s -= abs(o['ageMin'] - t['ageMin']) * 0.6
            s -= o['rank'] * 0.5
            ranked.append((s, o['title'], o))
        ranked.sort(key=lambda x: (-x[0], x[1]))
        t['similar'] = [o for _, _, o in ranked[:8]]


# ── Разметка ────────────────────────────────────────────────────────────────

def ld(obj):
    return '<script type="application/ld+json">' + yo(json.dumps(obj, ensure_ascii=False)).replace('</', '<\\/') + '</script>'


def breadcrumbs(items):
    lis = ''.join(f'<li><a href="{url(p)}">{e(n)}</a></li>' if p else f'<li aria-current="page">{e(n)}</li>' for n, p in items)
    data = {'@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': i + 1, 'name': n, **({'item': ORIGIN + url(p)} if p else {})}
        for i, (n, p) in enumerate(items)]}
    return f'<nav class="crumbs wrap" aria-label="Навигация"><ol>{lis}</ol></nav>', data


def item_list(titles, name):
    return {'@type': 'ItemList', 'name': name, 'numberOfItems': len(titles), 'itemListElement': [
        {'@type': 'ListItem', 'position': i + 1, 'url': ORIGIN + t['url'], 'name': t['title']} for i, t in enumerate(titles)]}


def faq_ld(faq):
    return {'@type': 'FAQPage', 'mainEntity': [{'@type': 'Question', 'name': q,
            'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in faq]}


def faq_html(faq):
    if not faq:
        return ''
    items = ''.join(f'<details><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q, a in faq)
    return f'<section class="section"><h2 class="h2" style="margin-bottom:20px">Вопросы и ответы</h2><div class="faq">{items}</div></section>'


NEN_LINKS = [('Журнал «Нет, это нормально»', 'https://n-e-n.ru/'), ('Что почитать с детьми', 'https://n-e-n.ru/knigi/'),
             ('Развитие ребенка', 'https://n-e-n.ru/razvitie/'), ('Эксперты НЭН', 'https://n-e-n.ru/eksperty/'),
             ('Тесты', 'https://n-e-n.ru/quizes/')]
NEN_SOCIAL = [('Телеграм', 'https://t.me/net_etonorm'), ('ВКонтакте', 'https://vk.com/net_eto_normalno'),
              ('Дзен', 'https://dzen.ru/nenru'), ('YouTube', 'https://www.youtube.com/@netetonorm'),
              ('Одноклассники', 'https://ok.ru/netetonorm')]
NEN_ORG = {'@type': 'Organization', '@id': 'https://n-e-n.ru/#organization', 'name': 'Нет, это нормально', 'alternateName': 'НЭН',
           'url': 'https://n-e-n.ru/', 'logo': {'@type': 'ImageObject', 'url': 'https://n-e-n.ru/img/nen_logo.png', 'width': 162, 'height': 74},
           'sameAs': [h for _, h in NEN_SOCIAL]}

TABBAR = [('Каталог', '/katalog/'), ('Возраст', '/vozrast/'), ('Темы', '/tema/'), ('Подборки', '/podborki/'), ('Подобрать', '/podobrat/')]
NAV = [('Мультфильмы', '/multfilmy/'), ('Мультсериалы', '/multserialy/'), ('Фильмы', '/filmy/'), ('По возрасту', '/vozrast/'),
       ('Темы', '/tema/'), ('Подборки', '/podborki/'), ('Подобрать', '/podobrat/')]
ASSET_VERSION = '1'


def page(path, title, description, body, *, schema=(), og_type='website', image=None, active=None, noindex=False, canonical=None,
         draft=False):
    """draft — карточка по описанию фильма, ещё не сверенная редакцией: страница есть, но закрыта от поиска."""
    canonical = ORIGIN + url(canonical or path)
    noindex = noindex or draft
    robots = 'noindex, nofollow' if PREVIEW or noindex else 'index, follow, max-image-preview:large, max-snippet:-1'
    nav = ''.join(f'<a href="{url(p)}"{" aria-current=page" if p == active else ""}>{e(n)}</a>' for n, p in NAV)
    tabbar = ''.join(f'<a href="{url(p)}"{" aria-current=page" if p == active else ""}>{e(n)}</a>' for n, p in TABBAR)
    src, w, h, alt = image or OG_DEFAULT
    og_image = (f'<meta property="og:image" content="{e(src)}">\n<meta property="og:image:width" content="{w}">\n'
                f'<meta property="og:image:height" content="{h}">\n<meta property="og:image:alt" content="{e(alt)}">\n'
                f'<meta name="twitter:image" content="{e(src)}">')
    preview = ('<div class="preview-bar">Рабочая версия для разработки. Сервис будет жить на '
               '<a href="https://n-e-n.ru/kino/">n-e-n.ru/kino</a></div>') if PREVIEW else ''
    graph = [s for s in schema if s]
    schema_html = ld({'@context': 'https://schema.org', '@graph': graph}) if graph else ''
    doc = f'''<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{e(canonical)}">
<meta name="robots" content="{robots}">{'<meta name="nen-status" content="draft">' if draft else ''}
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="НЭН">
<meta property="og:locale" content="ru_RU">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{e(canonical)}">
{og_image}
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(description)}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;600;700&family=Unbounded:wght@500;600;700&display=swap">
<link rel="stylesheet" href="{url('/assets/nen.css')}?v={ASSET_VERSION}">
<link rel="icon" href="https://n-e-n.ru/img/favicons/favicon.svg" type="image/svg+xml">
{schema_html}
</head>
<body data-base="{BASE}">
{preview}
<header class="header"><div class="wrap">
<a class="wordmark" href="{url('/')}">НЭН<small>{e('Что посмотреть с детьми')}</small></a>
<nav class="nav" aria-label="Разделы сервиса">{nav}</nav>
<a class="header-fav" href="{url('/izbrannoe/')}">Избранное</a>
</div></header>
<nav class="tabbar" aria-label="Разделы сервиса">{tabbar}</nav>
<main>
{body}
</main>
<footer class="footer"><div class="wrap">
<div><h2>{e('Что посмотреть с детьми')}</h2><p>{e('Фильмы, мультфильмы и сериалы, которые советует редакция НЭН: для каждого объясняем, с какого возраста смотреть, что важно знать родителям и о чём поговорить после просмотра.')}</p></div>
<div><h2>Разделы</h2><ul>{''.join(f'<li><a href="{url(p)}">{e(n)}</a></li>' for n, p in NAV)}<li><a href="{url('/izbrannoe/')}">Избранное</a></li></ul></div>
<div><h2>НЭН</h2><ul>{''.join(f'<li><a href="{h}">{e(n)}</a></li>' for n, h in NEN_LINKS)}</ul></div>
<div><h2>{e('НЭН в соцсетях')}</h2><ul>{''.join(f'<li><a href="{h}" rel="noopener">{e(n)}</a></li>' for n, h in NEN_SOCIAL)}</ul></div>
</div></footer>
<script src="{url('/assets/app.js')}?v={ASSET_VERSION}" defer></script>
</body>
</html>
'''
    return typo_html(doc)


def frame_img(t, cls='frame', eager=False, size=(720, 405)):
    if not t['frame']:
        return f'<div class="{cls} frame-empty" aria-hidden="true"><span>{e(t["title"])}</span></div>'
    loading = ' fetchpriority="high"' if eager else ' loading="lazy"'
    alt = f'Кадр из {KINDS[t["kind"]]["gen"]} «{t["title"]}»'
    return (f'<div class="{cls}"><img src="{e(frame_src(t))}" alt="{e(alt)}" '
            f'width="{size[0]}" height="{size[1]}"{loading} decoding="async"></div>')


def share_html(path, text):
    """Кнопка «Поделиться»: без JavaScript — список ссылок, с JavaScript на телефоне — системное меню."""
    u, t = quote(ORIGIN + url(path), safe=''), quote(yo(text), safe='')
    links = [('Телеграм', f'https://t.me/share/url?url={u}&text={t}'), ('ВКонтакте', f'https://vk.com/share.php?url={u}&title={t}'),
             ('WhatsApp', f'https://wa.me/?text={t}%20{u}'), ('Одноклассники', f'https://connect.ok.ru/offer?url={u}&title={t}')]
    items = ''.join(f'<a href="{e(h)}" target="_blank" rel="noopener" data-net="{n}">{e(n)}</a>' for n, h in links)
    return (f'<details class="share" data-share-text="{e(text)}"><summary>Поделиться</summary>'
            f'<div class="share-menu">{items}<button type="button" data-copy>Скопировать ссылку</button></div></details>')


def title_tags(t):
    out = [f'<span class="tag tag-blue">{e(t["ageLabel"])}</span>']
    if t['duration']:
        out.append(f'<span class="tag tag-pink">{e(t["duration"])}</span>')
    if t['moods']:
        out.append(f'<span class="tag tag-yellow">{e(t["moods"][0])}</span>')
    return '<div class="tags">' + ''.join(out) + '</div>'


def title_card(t):
    meta = f'{t["typeLabel"]} · {t["year"]}'
    return (f'<article class="card film-card">{frame_img(t, "cover")}'
            f'<h3 class="title"><a href="{t["url"]}">{e(t["title"])}</a></h3>'
            f'<p class="author">{e(meta)}</p>'
            f'<p class="snippet">{e(t["snippet"])}</p>{title_tags(t)}</article>')


def title_grid(titles):
    return '<div class="grid grid-4">' + ''.join(title_card(t) for t in titles) + '</div>'


def pager(base_path, n_pages, current):
    if n_pages < 2:
        return ''
    links = []
    for p in range(1, n_pages + 1):
        href = url(base_path if p == 1 else f'{base_path}{p}/')
        links.append(f'<span aria-current="page">{p}</span>' if p == current else f'<a href="{href}">{p}</a>')
    return '<nav class="pager" aria-label="Страницы">' + ''.join(links) + '</nav>'


def write(path, doc):
    target = os.path.join(OUT, path.strip('/'), 'index.html') if path.endswith('/') else os.path.join(OUT, path.lstrip('/'))
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, 'w', encoding='utf-8') as f:
        f.write(doc)


# ── Страница фильма ─────────────────────────────────────────────────────────

def film_ld(t):
    c = t['card']
    k = KINDS[t['kind']]
    data = {'@type': k['ld'], '@id': ORIGIN + t['url'] + '#film', 'name': t['title'], 'url': ORIGIN + t['url'],
            'description': c['about'], 'countryOfOrigin': [{'@type': 'Country', 'name': x} for x in t['country']],
            'typicalAgeRange': f'{t["ageMin"]}-' + (str(t['ageMax']) if t['ageMax'] else ''),
            'inLanguage': 'ru'}
    data['datePublished' if k['ld'] == 'Movie' else 'startDate'] = str(t['year'])
    if t.get('originalTitle'):
        data['alternateName'] = t['originalTitle']
    if k['ld'] == 'Movie' and t.get('minutes'):
        data['duration'] = f'PT{t["minutes"]}M'
    if t['frame']:
        data['image'] = SITE_ABS + f'/frames/og/{t["key"]}.jpg'
    if t.get('officialRating'):
        data['contentRating'] = t['officialRating']['value']
    if t['kind'].startswith('mult'):
        data['genre'] = 'мультфильм'
    return data


def render_title(t, in_collections, articles):
    c = t['card']
    k = KINDS[t['kind']]
    word = k['one'].lower()
    crumbs, crumbs_ld = breadcrumbs([('Главная', '/'), (k['plural'], f'/{k["section"]}/'), (t['title'], None)])
    facts = [('Год', str(t['year'])), ('Страна', ', '.join(t['country'])), ('Формат', t['typeLabel'])]
    if t['duration']:
        facts.append(('Длительность', t['duration']))
    if t.get('originalTitle'):
        facts.append(('В оригинале', t['originalTitle']))
    facts.append(('Возраст', f'НЭН советует {t["ageLabel"]}'))
    if t.get('officialRating'):
        facts.append(('Маркировка', t['officialRating']['value']))
    facts_html = ''.join(f'<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>' for a, b in facts)
    sens = ''
    if t['sensitive']:
        sens = ('<div class="sensitive"><p class="meta">Сложные темы</p><div class="tags">' +
                ''.join(f'<span class="tag tag-warn">{e(s)}</span>' for s in t['sensitive']) + '</div></div>')
    rating = ''
    if t.get('officialRating'):
        rating = f'<p class="meta">Маркировка в России — {e(t["officialRating"]["value"])}. Возраст НЭН — это совет редакции, а не запрет.</p>'
    questions = ''.join(f'<li>{e(q)}</li>' for q in c['discussionQuestions'])
    vocab_themes = VOCAB['themes']
    theme_links = ''.join(f'<a class="chip" href="{url("/tema/" + vocab_themes[th][0] + "/")}">{e(vocab_themes[th][1])}</a>'
                          for th in t['themes'] if vocab_themes[th][0] in THEME_PAGES)
    cols = ''
    if in_collections:
        cols = ('<section class="block"><h2 class="h3">Есть в подборках</h2><ul class="reads">' +
                ''.join(f'<li><a href="{url("/podborki/" + col["slug"] + "/")}">{e(col["title"])}</a></li>' for col in in_collections) +
                '</ul></section>')
    reads = ''
    if articles:
        reads = ('<section class="block"><h2 class="h3">Читайте в журнале НЭН</h2><ul class="reads">' +
                 ''.join(f'<li><a href="{e(a["url"])}">{e(a["title"])}</a><span class="meta">{e(ru_date(a.get("date")))}</span></li>' for a in articles[:5]) +
                 '</ul></section>')
    sim = ''
    if t['similar']:
        sim = f'<section class="section"><div class="section-head"><h2 class="h2">Похожие</h2></div>{title_grid(t["similar"][:4])}</section>'
    note = ''
    if t['draft']:
        note = '<p class="meta">Карточка составлена по описанию фильма и ждёт проверки редакцией.</p>'
    credit = f'<p class="cover-credit">Кадр из {k["gen"]} «{e(t["title"])}»</p>' if t['frame'] else ''
    share_text = f'«{t["title"]}» — {word} для детей {"с " + age_gen(t["ageMin"]) if t["ageMax"] is None else t["ageLabel"].replace(" года", " лет")}. Совет НЭН'
    body = f'''{crumbs}
<article class="wrap film page-end">
<header class="film-head">
<p class="eyebrow">{e(t["typeLabel"])} · {t["year"]} · {e(", ".join(t["country"]))}</p>
<h1 class="h1">{e(t["title"])}</h1>
{f'<p class="original">{e(t["originalTitle"])}</p>' if t.get("originalTitle") else ''}
{title_tags(t)}
<div class="actions"><button class="fav" type="button" data-fav="{e(t["slug"])}">Сохранить в избранное</button>{share_html(t["path"], share_text)}</div>
</header>
<div class="film-grid">
<div class="film-main">
{frame_img(t, "film-frame", eager=True) if t['frame'] else ''}{credit}
<section class="block"><h2 class="h2">О чём {word}</h2><div class="prose"><p>{e(c["about"])}</p></div></section>
<section class="block"><h2 class="h2">Почему советуем</h2><div class="prose"><p>{e(c["whyRecommended"])}</p></div>{note}</section>
<section class="plate plate-care"><h2 class="h3">Что важно знать родителям</h2><p>{e(c["parentsNote"])}</p>{sens}</section>
<section class="block"><h2 class="h2">С какого возраста</h2><p class="age-big">{e(t["ageLabel"])}</p><div class="prose"><p>{e(c["ageReason"])}</p></div>{rating}</section>
<section class="plate plate-community"><h2 class="h3">О чём поговорить после просмотра</h2><ol class="questions">{questions}</ol></section>
{f'<section class="block"><h2 class="h3">Темы</h2><div class="chips">{theme_links}</div></section>' if theme_links else ''}
{cols}
{reads}
</div>
<aside class="film-aside"><dl class="facts">{facts_html}</dl></aside>
</div>
{sim}
</article>'''
    image = (SITE_ABS + f'/frames/og/{t["key"]}.jpg', 600, 316, f'Кадр из {k["gen"]} «{t["title"]}»') if t['frame'] else None
    seo_title = f'«{t["title"]}» ({t["year"]}) — {word} для детей {"с " + age_gen(t["ageMin"]) if t["ageMax"] is None else age_range_gen(t)} | НЭН'
    if len(seo_title) > 70:
        seo_title = f'«{t["title"]}» ({t["year"]}) — {word} | НЭН'
    if len(seo_title) > 70:
        seo_title = f'«{short(t["title"], 50)}» ({t["year"]}) | НЭН'
    return page(t['path'], seo_title, c['seoDescription'], body, schema=[film_ld(t), crumbs_ld], og_type='video.movie'
                if k['ld'] == 'Movie' else 'video.tv_show', image=image, draft=t['draft'])


def age_range_gen(t):
    """«для детей 4–9 лет» — родительный падеж всегда «лет», кроме «до 1 года»."""
    return f'{t["ageMin"]}–{age_gen(t["ageMax"])}'


# ── Списки ───────────────────────────────────────────────────────────────────

def intro_html(text):
    if not text:
        return ''
    paras = [p for p in (text if isinstance(text, list) else [text]) if p]
    return '<div class="intro">' + ''.join(f'<p>{e(p)}</p>' for p in paras) + '</div>'


def render_list(path, crumbs_items, h1, title, description, intro, titles, *, faq=None, extra_top='', extra_bottom='',
                active=None, eyebrow=''):
    """Список с постраничной навигацией настоящими адресами: /multfilmy/, /multfilmy/2/…"""
    n_pages = max(1, (len(titles) + PER_PAGE - 1) // PER_PAGE)
    for p in range(1, n_pages + 1):
        chunk = titles[(p - 1) * PER_PAGE:p * PER_PAGE]
        page_path = path if p == 1 else f'{path}{p}/'
        items = list(crumbs_items[:-1]) + ([(crumbs_items[-1][0], None)] if p == 1 else [(crumbs_items[-1][0], path), (f'Страница {p}', None)])
        crumbs, crumbs_ld = breadcrumbs(items)
        head_h1 = h1 if p == 1 else f'{h1} — страница {p}'
        page_title = title if p == 1 else f'{h1} — страница {p} | НЭН'
        page_desc = description if p == 1 else f'{description.rstrip(".")}. Страница {p}.'
        if len(page_desc) > 160:   # на дальних страницах длинному описанию хватит первой фразы
            page_desc = f'{description.split(". ")[0].rstrip(".")}. Страница {p}.'
        body = f'''{crumbs}
<div class="wrap page-end">
<header class="list-head">{f'<p class="eyebrow">{e(eyebrow)}</p>' if eyebrow else ''}<h1 class="h1">{e(head_h1)}</h1>{intro_html(intro) if p == 1 else ''}</header>
{extra_top if p == 1 else ''}
<div class="results-meta"><span class="meta">{e(count_word(len(titles)))}{f", страница {p} из {n_pages}" if n_pages > 1 else ""}</span></div>
{title_grid(chunk)}
{pager(path, n_pages, p)}
{extra_bottom if p == 1 else ''}
{faq_html(faq) if p == 1 else ''}
</div>'''
        schema = [crumbs_ld, {'@type': 'CollectionPage', 'name': head_h1, 'url': ORIGIN + url(page_path),
                              'isPartOf': {'@id': 'https://n-e-n.ru/#organization'}, 'mainEntity': item_list(chunk, head_h1)}]
        if faq and p == 1:
            schema.append(faq_ld(faq))
        write(page_path, page(page_path, page_title, page_desc, body, schema=schema, active=active))
        SITEMAP.append(page_path)


def chips_links(items):
    return '<div class="related-links">' + ''.join(f'<a class="chip" href="{url(p)}">{e(n)}<span class="count">{c}</span></a>'
                                                   for n, p, c in items) + '</div>'


# ── Сборка ───────────────────────────────────────────────────────────────────

SITEMAP = []
VOCAB = {}
THEME_PAGES = set()


def fits_age(t, n):
    return t['ageMin'] <= n and (t['ageMax'] is None or t['ageMax'] >= n)


def main():
    global VOCAB
    VOCAB, titles = load()
    similar(titles)
    landings = content('landings.json', {})
    collections = content('collections.json', [])
    articles = content('nen-articles.json', {})
    home_cfg = content('home.json', {})
    by_slug = {t['key']: t for t in titles}

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    shutil.copytree(os.path.join(ROOT, 'site', 'assets'), os.path.join(OUT, 'assets'))
    frames_out = os.path.join(OUT, 'frames')
    os.makedirs(os.path.join(frames_out, 'og'))
    for t in titles:
        if t['frame']:
            shutil.copy(os.path.join(ROOT, 'site', 'frames', f'{t["key"]}.webp'), frames_out)
            og = os.path.join(ROOT, 'site', 'frames', 'og', f'{t["key"]}.jpg')
            if os.path.exists(og):
                shutil.copy(og, os.path.join(frames_out, 'og'))

    # Темы: страница есть только у тем, где хватает фильмов
    theme_titles = {th: [t for t in titles if th in t['themes']] for th in VOCAB['themes']}
    for th, lst in theme_titles.items():
        if len(lst) >= MIN_LIST:
            THEME_PAGES.add(VOCAB['themes'][th][0])

    cols = []
    for col in collections:
        picks = [by_slug[s] for s in col['titles'] if s in by_slug]
        if len(picks) >= 3:
            cols.append(dict(col, picks=picks))
    in_cols = {}
    for col in cols:
        for t in col['picks']:
            in_cols.setdefault(t['key'], []).append(col)

    # Карточки фильмов
    for t in titles:
        write(t['path'], render_title(t, in_cols.get(t['key'], []), articles.get(t['key'], [])))
        if not t['draft']:
            SITEMAP.append(t['path'])

    by_kind = {k: [t for t in titles if t['kind'] == k] for k in KINDS}

    # Разделы
    for kind, cfg in KINDS.items():
        lst = by_kind[kind]
        if not lst:
            continue
        land = landings.get(f'section:{cfg["section"]}', {})
        ages = [(f'{n} {age_word(n)}', f'/{cfg["section"]}/{age_slug(n)}/', sum(fits_age(t, n) for t in lst))
                for n in SECTION_AGES.get(kind, []) if sum(fits_age(t, n) for t in lst) >= MIN_LIST]
        top = f'<section class="section"><h2 class="h3" style="margin-bottom:12px">По возрасту</h2>{chips_links(ages)}</section>' if ages else ''
        render_list(f'/{cfg["section"]}/', [('Главная', '/'), (cfg['plural'], None)], cfg['h1'],
                    land.get('title') or f'{cfg["h1"]}: что посмотреть с ребёнком | НЭН',
                    land.get('description') or f'{cfg["h1"]} с рекомендацией редакции НЭН: с какого возраста смотреть, что важно знать родителям и о чём поговорить после просмотра.',
                    land.get('intro'), lst, faq=[tuple(x) for x in land.get('faq', [])], extra_top=top, active=f'/{cfg["section"]}/')
        # Раздел × возраст
        for n in SECTION_AGES.get(kind, []):
            sub = [t for t in lst if fits_age(t, n)]
            if len(sub) < MIN_LIST:
                continue
            sub.sort(key=lambda t: (t['rank'], abs(t['ageMin'] - n), t['title']))
            h1 = f'{cfg["plural"]} для {kid(n)} {age_gen(n)}'
            age_land = landings.get(f'age:{n}', {})
            intro = [p for p in [landings.get(f'section-age:{cfg["section"]}:{n}', {}).get('intro'), age_land.get('short')] if p]
            render_list(f'/{cfg["section"]}/{age_slug(n)}/', [('Главная', '/'), (cfg['plural'], f'/{cfg["section"]}/'), (h1, None)], h1,
                        f'{h1}: что посмотреть с {kid(n, "ins")} | НЭН',
                        f'{h1} — {count_word(len(sub), kind)}, которые советует редакция НЭН. Для каждого: почему подходит и о чём поговорить после просмотра.',
                        intro, sub, active=f'/{cfg["section"]}/')

    # Возраст
    age_tiles = []
    for n in AGES:
        sub = [t for t in titles if fits_age(t, n)]
        if len(sub) < MIN_LIST:
            continue
        sub.sort(key=lambda t: (t['rank'], abs(t['ageMin'] - n), t['title']))
        land = landings.get(f'age:{n}', {})
        h1 = f'Что посмотреть с {kid(n, "ins")} {age_gen(n)}'
        kinds = [(KINDS[k]['plural'], f'/{KINDS[k]["section"]}/{age_slug(n)}/', sum(fits_age(t, n) for t in by_kind[k]))
                 for k in KINDS if n in SECTION_AGES.get(k, []) and sum(fits_age(t, n) for t in by_kind[k]) >= MIN_LIST]
        top = f'<section class="section">{chips_links(kinds)}</section>' if kinds else ''
        render_list(f'/vozrast/{age_slug(n)}/', [('Главная', '/'), ('По возрасту', '/vozrast/'), (h1, None)], h1,
                    land.get('title') or f'{h1}: мультфильмы и фильмы | НЭН',
                    land.get('description') or f'Мультфильмы, фильмы и сериалы для {kid(n)} {age_gen(n)}: {count_word(len(sub))} с советами редакции НЭН.',
                    land.get('intro'), sub, faq=[tuple(x) for x in land.get('faq', [])], extra_top=top, active='/vozrast/')
        age_tiles.append((n, len(sub)))
    teen = sorted([t for t in titles if t['ageMin'] >= 12], key=lambda t: (t['rank'], t['title']))
    land = landings.get('age:podrostki', {})
    if len(teen) >= MIN_LIST:
        render_list('/vozrast/podrostki/', [('Главная', '/'), ('По возрасту', '/vozrast/'), ('Для подростков', None)],
                    'Фильмы и сериалы для подростков', land.get('title') or 'Фильмы и сериалы для подростков 12–17 лет | НЭН',
                    land.get('description') or f'Что посмотреть с подростком: {count_word(len(teen))} с советами редакции НЭН.',
                    land.get('intro'), teen, faq=[tuple(x) for x in land.get('faq', [])], active='/vozrast/')
    tiles = ''.join(f'<a class="age-tile" href="{url("/vozrast/" + age_slug(n) + "/")}"><b>{n} <small>{age_word(n)}</small></b><span>{count_word(c)}</span></a>'
                    for n, c in age_tiles)
    if len(teen) >= MIN_LIST:
        tiles += f'<a class="age-tile" href="{url("/vozrast/podrostki/")}"><b>12+</b><span>подросткам</span></a>'
    land = landings.get('vozrast', {})
    crumbs, crumbs_ld = breadcrumbs([('Главная', '/'), ('По возрасту', None)])
    body = f'''{crumbs}<div class="wrap page-end"><header class="list-head"><h1 class="h1">Что посмотреть с ребёнком: по возрасту</h1>{intro_html(land.get("intro"))}</header>
<section class="section"><div class="age-grid">{tiles}</div></section>{faq_html([tuple(x) for x in land.get("faq", [])])}</div>'''
    write('/vozrast/', page('/vozrast/', 'Мультфильмы и фильмы для детей по возрасту | НЭН',
                            'Что посмотреть с ребёнком 2, 3, 5, 7, 10 лет и с подростком: мультфильмы, фильмы и сериалы по возрасту с советами НЭН.',
                            body, schema=[crumbs_ld] + ([faq_ld([tuple(x) for x in land['faq']])] if land.get('faq') else []), active='/vozrast/'))
    SITEMAP.append('/vozrast/')

    # Темы
    topic_items = []
    for th, (slug, short_name, h1) in VOCAB['themes'].items():
        lst = theme_titles[th]
        if slug not in THEME_PAGES:
            continue
        land = landings.get(f'theme:{slug}', {})
        render_list(f'/tema/{slug}/', [('Главная', '/'), ('Темы', '/tema/'), (h1, None)], h1,
                    land.get('title') or (f'{h1} | НЭН' if len(h1) <= 50 else f'{h1} | НЭН'),
                    land.get('description') or f'{h1}: {count_word(len(lst))} с советами редакции НЭН — с какого возраста смотреть и о чём поговорить.',
                    land.get('intro'), lst, faq=[tuple(x) for x in land.get('faq', [])], active='/tema/')
        topic_items.append((short_name, slug, len(lst)))
    topic_items.sort(key=lambda x: -x[2])
    topics_html = ''.join(f'<a class="topic" href="{url("/tema/" + s + "/")}">{e(n)}<span class="count">{c}</span></a>' for n, s, c in topic_items)
    crumbs, crumbs_ld = breadcrumbs([('Главная', '/'), ('Темы', None)])
    body = f'{crumbs}<div class="wrap page-end"><header class="list-head"><h1 class="h1">Фильмы и мультфильмы по темам</h1>{intro_html(landings.get("tema", {}).get("intro"))}</header><section class="section"><div class="topics">{topics_html}</div></section></div>'
    write('/tema/', page('/tema/', 'Фильмы и мультфильмы для детей по темам | НЭН',
                         'Про дружбу, семью, животных, космос, школу и страхи: фильмы и мультфильмы для детей по темам с советами НЭН.',
                         body, schema=[crumbs_ld], active='/tema/'))
    SITEMAP.append('/tema/')

    # Подборки
    for col in cols:
        picks = ''.join(
            f'<article class="pick">{frame_img(t, "pick-cover", size=(360, 203))}<div class="pick-body"><span class="num">{i:02d}</span>'
            f'<h3><a href="{t["url"]}">{e(t["title"])}</a></h3><p class="meta">{e(t["typeLabel"])} · {t["year"]} · {e(t["ageLabel"])}</p>'
            f'<p class="pick-text">{e(first_sentences(t["card"]["whyRecommended"], 220))}</p></div></article>'
            for i, t in enumerate(col['picks'], 1))
        src = (f'<p class="meta">По материалу журнала НЭН: <a href="{e(col["sourceUrl"])}">{e(col["sourceTitle"])}</a></p>'
               if col.get('sourceUrl') else '')
        path = f'/podborki/{col["slug"]}/'
        crumbs, crumbs_ld = breadcrumbs([('Главная', '/'), ('Подборки', '/podborki/'), (col['title'], None)])
        body = f'''{crumbs}<div class="wrap page-end"><header class="list-head"><p class="eyebrow">Подборка НЭН · {e(count_word(len(col["picks"])))}</p>
<h1 class="h1">{e(col["title"])}</h1>{intro_html(col.get("intro"))}{src}
<div class="actions">{share_html(path, col["title"] + " — подборка НЭН")}</div></header>
<section class="section"><div class="picks">{picks}</div></section></div>'''
        first = next((t for t in col['picks'] if t['frame']), None)
        image = (SITE_ABS + f'/frames/og/{first["key"]}.jpg', 600, 316, col['title']) if first else None
        write(path, page(path, col.get('seoTitle') or f'{col["title"]}: подборка НЭН | НЭН',
                         col.get('seoDescription') or short(col.get('intro', [''])[0] if isinstance(col.get('intro'), list) else col.get('intro', ''), 158),
                         body, schema=[crumbs_ld, {'@type': 'CollectionPage', 'name': col['title'], 'url': ORIGIN + url(path),
                                                   'mainEntity': item_list(col['picks'], col['title'])}], image=image, active='/podborki/'))
        SITEMAP.append(path)
    cards_html = ''.join(collection_card(col) for col in cols)
    crumbs, crumbs_ld = breadcrumbs([('Главная', '/'), ('Подборки', None)])
    body = f'{crumbs}<div class="wrap page-end"><header class="list-head"><h1 class="h1">Подборки редакции НЭН</h1>{intro_html(landings.get("podborki", {}).get("intro"))}</header><section class="section"><div class="grid grid-3">{cards_html}</div></section></div>'
    write('/podborki/', page('/podborki/', 'Подборки фильмов и мультфильмов для детей от редакции НЭН | НЭН',
                             'Новогодние мультфильмы, фильмы про собак, кино для подростков: подборки редакции НЭН для семейного просмотра.',
                             body, schema=[crumbs_ld], active='/podborki/'))
    SITEMAP.append('/podborki/')

    # Каталог, подбор, избранное
    render_catalog(titles)
    render_quiz()
    render_favorites()
    render_home(titles, by_kind, age_tiles, teen, topic_items, cols, home_cfg, landings.get('home', {}))
    render_404()
    write_index(titles)
    write_sitemap()
    print(f'страниц фильмов: {len(titles)}, всего адресов в sitemap: {len(SITEMAP)}, папка: {os.path.relpath(OUT, ROOT)}')


def collection_card(col):
    frames = ''.join(f'<img src="{e(frame_src(t))}" alt="" width="96" height="54" loading="lazy" decoding="async">'
                     for t in [t for t in col['picks'] if t['frame']][:3])
    intro = col.get('intro')
    text = intro[0] if isinstance(intro, list) else (intro or '')
    return (f'<article class="text-card col-card"><div class="mini-frames" aria-hidden="true">{frames}</div>'
            f'<span class="num">{e(count_word(len(col["picks"])))}</span><h3><a href="{url("/podborki/" + col["slug"] + "/")}">{e(col["title"])}</a></h3>'
            f'<p>{e(short(text, 150))}</p></article>')


def filters_form(themes):
    kinds = ''.join(f'<option value="{k}">{e(cfg["plural"])}</option>' for k, cfg in KINDS.items())
    ages = ''.join(f'<option value="{n}">{n} {age_word(n)}</option>' for n in range(2, 18))
    th = ''.join(f'<option value="{e(t)}">{e(VOCAB["themes"][t][1])}</option>' for t in themes)
    moods = ''.join(f'<button class="chip" type="button" data-mood="{e(m)}" aria-pressed="false">{e(m)}</button>' for m in VOCAB['moods'])
    return f'''<form class="filters" id="catalog-filters" role="search">
<div class="row">
<label><span class="visually-hidden">Поиск</span><input type="search" name="q" placeholder="Название или тема" autocomplete="off"></label>
<label><span class="visually-hidden">Раздел</span><select name="kind"><option value="">Все разделы</option>{kinds}</select></label>
<label><span class="visually-hidden">Возраст ребёнка</span><select name="age"><option value="">Любой возраст</option>{ages}</select></label>
<label><span class="visually-hidden">Тема</span><select name="theme"><option value="">Все темы</option>{th}</select></label>
</div>
<fieldset><legend>Настроение</legend><div class="chips">{moods}<button class="chip" type="button" data-short aria-pressed="false">до 30 минут</button></div></fieldset>
</form>'''


def render_catalog(titles):
    themes = [t for t in VOCAB['themes'] if VOCAB['themes'][t][0] in THEME_PAGES]
    form = filters_form(themes)
    n_pages = max(1, (len(titles) + PER_PAGE - 1) // PER_PAGE)
    for p in range(1, n_pages + 1):
        chunk = titles[(p - 1) * PER_PAGE:p * PER_PAGE]
        path = '/katalog/' if p == 1 else f'/katalog/{p}/'
        items = [('Главная', '/'), ('Каталог', None)] if p == 1 else [('Главная', '/'), ('Каталог', '/katalog/'), (f'Страница {p}', None)]
        crumbs, crumbs_ld = breadcrumbs(items)
        h1 = 'Каталог: фильмы, мультфильмы и сериалы для детей' if p == 1 else f'Каталог — страница {p}'
        body = f'''{crumbs}<div class="wrap page-end">
<header class="list-head"><h1 class="h1">{e(h1)}</h1>{'<div class="intro"><p>' + e(f"Все {count_word(len(titles))} каталога НЭН. Выберите возраст ребёнка, тему или настроение — список обновится сразу.") + '</p></div>' if p == 1 else ''}</header>
{form}
<div id="catalog-results" hidden></div>
<div class="results-meta"><span class="meta">{e(count_word(len(titles)))}, страница {p} из {n_pages}</span></div>
{title_grid(chunk)}
{pager('/katalog/', n_pages, p)}
</div>'''
        title = 'Каталог фильмов и мультфильмов для детей | НЭН' if p == 1 else f'Каталог фильмов и мультфильмов для детей — страница {p} | НЭН'
        desc = (f'{count_word(len(titles)).capitalize()} для детей и подростков с советами НЭН: фильтры по возрасту, теме и настроению.'
                if p == 1 else f'Каталог НЭН: фильмы, мультфильмы и сериалы для детей с советами редакции — с какого возраста смотреть и о чём поговорить. Страница {p}.')
        write(path, page(path, title, desc, body, schema=[crumbs_ld, {'@type': 'CollectionPage', 'name': h1, 'url': ORIGIN + url(path),
                                                                    'mainEntity': item_list(chunk, h1)}], active='/katalog/'))
        SITEMAP.append(path)


def render_quiz():
    themes = [t for t in VOCAB['themes'] if VOCAB['themes'][t][0] in THEME_PAGES][:18]
    th = ''.join(f'<button class="chip" type="button" data-theme="{e(t)}" aria-pressed="false">{e(VOCAB["themes"][t][1])}</button>' for t in themes)
    moods = ''.join(f'<button class="chip" type="button" data-mood="{e(m)}" aria-pressed="false">{e(m)}</button>' for m in VOCAB['moods'])
    kinds = ''.join(f'<button class="chip" type="button" data-kind="{k}" aria-pressed="false">{e(cfg["plural"])}</button>' for k, cfg in KINDS.items())
    crumbs, crumbs_ld = breadcrumbs([('Главная', '/'), ('Подобрать', None)])
    body = f'''{crumbs}<div class="wrap page-end">
<header class="list-head"><h1 class="h1">Подобрать фильм или мультфильм</h1><div class="intro"><p>Три вопроса — и список того, что можно посмотреть сегодня вечером. Без JavaScript подбор не работает: воспользуйтесь <a href="{url('/vozrast/')}">списками по возрасту</a> или <a href="{url('/tema/')}">по темам</a>.</p></div></header>
<form class="quiz" id="quiz" hidden>
<div class="step is-active" data-step="1"><h2 class="h3">Сколько лет ребёнку?</h2>
<div class="stepper"><button type="button" data-age="-1" aria-label="Меньше">−</button><output name="age">5 лет</output><button type="button" data-age="1" aria-label="Больше">+</button></div>
<div class="btn-row"><button class="btn btn-primary" type="button" data-next>Дальше</button></div></div>
<div class="step" data-step="2"><h2 class="h3">Что хотите посмотреть?</h2><div class="chips">{kinds}</div><p class="meta">Можно ничего не выбирать.</p>
<div class="btn-row"><button class="btn btn-secondary" type="button" data-prev>Назад</button><button class="btn btn-primary" type="button" data-next>Дальше</button></div></div>
<div class="step" data-step="3"><h2 class="h3">Настроение и темы</h2><div class="chips">{moods}</div><div class="chips">{th}</div>
<div class="btn-row"><button class="btn btn-secondary" type="button" data-prev>Назад</button><button class="btn btn-primary" type="submit">Показать</button></div></div>
</form>
<div id="quiz-results" class="section"></div>
</div>'''
    write('/podobrat/', page('/podobrat/', 'Подобрать фильм или мультфильм для ребёнка | НЭН',
                             'Подбор фильма, мультфильма или сериала по возрасту ребёнка, настроению и теме: три вопроса и готовый список от редакции НЭН.',
                             body, schema=[crumbs_ld], active='/podobrat/'))
    SITEMAP.append('/podobrat/')


def render_favorites():
    crumbs, crumbs_ld = breadcrumbs([('Главная', '/'), ('Избранное', None)])
    body = f'''{crumbs}<div class="wrap page-end"><header class="list-head"><h1 class="h1">Избранное</h1>
<div class="intro"><p>Здесь появятся фильмы, которые вы сохранили. Список хранится в этом браузере.</p></div></header>
<div id="favorites" class="section"><p class="empty">Пока пусто. Нажмите «Сохранить в избранное» на странице фильма.</p></div></div>'''
    write('/izbrannoe/', page('/izbrannoe/', 'Избранное | НЭН', 'Сохранённые фильмы и мультфильмы.', body, schema=[crumbs_ld], noindex=True))


def render_home(titles, by_kind, age_tiles, teen, topics, cols, cfg, land):
    picks = [t for t in (titles if not cfg.get('featured') else [x for s in cfg['featured'] for x in titles if x['key'] == s]) if t['frame']][:8]
    sections = ''.join(
        f'<a class="age-tile kind-tile" href="{url("/" + KINDS[k]["section"] + "/")}"><b>{e(KINDS[k]["plural"])}</b><span>{e(count_word(len(lst), k))}</span></a>'
        for k, lst in by_kind.items() if lst)
    ages = ''.join(f'<a class="age-tile" href="{url("/vozrast/" + age_slug(n) + "/")}"><b>{n} <small>{age_word(n)}</small></b><span>{count_word(c)}</span></a>'
                   for n, c in age_tiles if n in (2, 3, 4, 5, 6, 7, 8, 10, 12))
    if len(teen) >= MIN_LIST:
        ages += f'<a class="age-tile" href="{url("/vozrast/podrostki/")}"><b>12+</b><span>подросткам</span></a>'
    topics_html = ''.join(f'<a class="topic" href="{url("/tema/" + s + "/")}">{e(n)}<span class="count">{c}</span></a>' for n, s, c in topics[:12])
    cols_html = ''.join(collection_card(col) for col in cols[:6])
    faq = [tuple(x) for x in land.get('faq', [])]
    body = f'''<div class="wrap">
<section class="hero hero-with-art">
<div class="hero-copy">
<p class="eyebrow">Сервис журнала НЭН</p>
<h1 class="h1">Что посмотреть с детьми</h1>
<p class="lead">{e(land.get("lead") or "Мультфильмы, фильмы и сериалы, которые советует редакция. Для каждого — с какого возраста смотреть, что важно знать родителям и о чём поговорить после просмотра.")}</p>
<div class="hero-stats"><div><b>{len(titles)}</b>{e(plural(len(titles), "фильм", "фильма", "фильмов"))} в каталоге</div><div><b>{len(cols)}</b>{e(plural(len(cols), "подборка", "подборки", "подборок"))} редакции</div></div>
<div class="btn-row"><a class="btn btn-primary" href="{url('/podobrat/')}">Подобрать фильм</a><a class="btn btn-secondary" href="{url('/katalog/')}">Весь каталог</a></div>
</div>
<picture class="hero-art"><source media="(max-width:599px)" srcset="{url('/assets/hero-600.webp')}"><img src="{url('/assets/hero.webp')}" alt="Ребёнок показывает кино на проекторе — иллюстрация НЭН" width="1200" height="675" fetchpriority="high"></picture>
</section>
<section class="section"><div class="age-grid kinds">{sections}</div></section>
<section class="section"><div class="section-head"><h2 class="h2">По возрасту</h2><a href="{url('/vozrast/')}">Все возрасты</a></div><div class="age-grid">{ages}</div></section>
<section class="section"><div class="section-head"><h2 class="h2">Советуем посмотреть</h2><a href="{url('/katalog/')}">Весь каталог</a></div>{title_grid(picks)}</section>
{f'<section class="section"><div class="section-head"><h2 class="h2">Подборки редакции</h2><a href="{url("/podborki/")}">Все подборки</a></div><div class="grid grid-3">{cols_html}</div></section>' if cols_html else ''}
<section class="section"><div class="section-head"><h2 class="h2">Темы</h2><a href="{url('/tema/')}">Все темы</a></div><div class="topics">{topics_html}</div></section>
<section class="section"><div class="panel-deep"><div><h2 class="h2">Не знаете, что включить?</h2><p>Ответьте на три вопроса: возраст, формат и настроение. Покажем, что подойдёт сегодня.</p></div><div><a class="btn btn-primary" href="{url('/podobrat/')}">Подобрать</a></div></div></section>
{faq_html(faq)}
</div><div class="page-end"></div>'''
    schema = [NEN_ORG, {'@type': 'WebSite', 'name': 'Что посмотреть с детьми — НЭН', 'url': ORIGIN + url('/'),
                        'publisher': {'@id': 'https://n-e-n.ru/#organization'}, 'inLanguage': 'ru'}]
    if faq:
        schema.append(faq_ld(faq))
    write('/', page('/', land.get('title') or 'Что посмотреть с детьми: фильмы и мультфильмы по возрасту | НЭН',
                    land.get('description') or 'Мультфильмы, фильмы и сериалы для детей и подростков с советами редакции НЭН: с какого возраста смотреть, что важно знать родителям, о чём поговорить.',
                    body, schema=schema))
    SITEMAP.insert(0, '/')


def render_404():
    body = f'''<div class="wrap page-end"><header class="list-head"><h1 class="h1">Такой страницы нет</h1>
<div class="intro"><p>Возможно, фильм убрали из каталога или в адресе опечатка. Попробуйте <a href="{url('/katalog/')}">каталог</a>, <a href="{url('/vozrast/')}">списки по возрасту</a> или <a href="{url('/podobrat/')}">подбор</a>.</p></div></header></div>'''
    write('/404.html', page('/404.html', 'Страница не найдена | НЭН', 'Такой страницы нет в сервисе НЭН «Что посмотреть с детьми».', body, noindex=True))


def write_index(titles):
    """Данные для фильтров каталога, подбора и избранного."""
    themes = list(VOCAB['themes'])
    moods = list(VOCAB['moods'])
    kinds = list(KINDS)
    rows = [[t['slug'], yo(t['title']), kinds.index(t['kind']), t['year'], t['ageMin'], t['ageMax'] or 18,
             [themes.index(x) for x in t['themes']], [moods.index(x) for x in t['moods']], 1 if t['frame'] else 0,
             yo(t['snippet']), yo(t['ageLabel']), t['rank'], t.get('minutes') or t.get('episodeMinutes') or 0,
             yo(t['typeLabel']), yo(t.get('originalTitle') or '')] for t in titles]
    os.makedirs(os.path.join(OUT, 'data'), exist_ok=True)
    data = {'themes': [yo(x) for x in themes], 'themeNames': [yo(VOCAB['themes'][x][1]) for x in themes], 'moods': [yo(m) for m in moods],
            'kinds': kinds, 'kindNames': [KINDS[k]['one'] for k in kinds], 'titles': rows}
    with open(os.path.join(OUT, 'data', 'index.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))


def write_sitemap():
    urls = ''.join(f'<url><loc>{ORIGIN}{url(p)}</loc><lastmod>{TODAY}</lastmod></url>' for p in SITEMAP)
    with open(os.path.join(OUT, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
    with open(os.path.join(OUT, 'robots.txt'), 'w', encoding='utf-8') as f:
        f.write('User-agent: *\nDisallow: /\n' if PREVIEW else f'User-agent: *\nAllow: /\nSitemap: {ORIGIN}{BASE}/sitemap.xml\n')
    if PREVIEW:
        open(os.path.join(OUT, '.nojekyll'), 'w').close()


if __name__ == '__main__':
    main()
