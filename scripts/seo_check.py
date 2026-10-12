#!/usr/bin/env python3
"""SEO-проверка собранного сайта: всё, что может помешать поиску после запуска.

  NEN_PREVIEW=0 python3 site/build.py --out dist && python3 scripts/seo_check.py dist

Проверяет каждую страницу: title и description (есть, нужной длины, не повторяются), один H1,
canonical на саму себя, robots, Open Graph с полными адресами картинок, разметку schema.org
(JSON без ошибок), alt и размеры картинок, битые внутренние ссылки, страницы без входящих
ссылок, мало текста, одинаковый текст на разных страницах, sitemap.xml и robots.txt.
Код выхода 1, если есть ошибки (предупреждения не считаются).
"""
import collections, hashlib, html.parser, json, os, re, sys
from urllib.parse import urlsplit, unquote

ORIGIN = 'https://n-e-n.ru'
BASE = '/kino'
NOINDEX_OK = {'/izbrannoe/', '/404.html'}
TITLE_MAX, DESC_MIN, DESC_MAX = 70, 70, 170
THIN_WORDS = 120


class Page(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.meta, self.links, self.canonical = [], {}, [], None
        self.h1, self.imgs, self.ld, self.lang = [], [], [], None
        self._stack, self._buf, self.main_text, self._in_main = [], None, [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'html':
            self.lang = a.get('lang')
        elif tag == 'meta':
            key = a.get('name') or a.get('property')
            if key:
                self.meta.setdefault(key, []).append(a.get('content') or '')
        elif tag == 'link' and a.get('rel') == 'canonical':
            self.canonical = a.get('href')
        elif tag == 'a' and a.get('href'):
            self.links.append(a['href'])
        elif tag == 'img':
            self.imgs.append(a)
        elif tag == 'main':
            self._in_main += 1
        if tag in ('title', 'h1') or (tag == 'script' and a.get('type') == 'application/ld+json'):
            self._stack.append(tag if tag != 'script' else 'ld')
            self._buf = []

    def handle_endtag(self, tag):
        if tag == 'main':
            self._in_main -= 1
        if self._stack and (tag == self._stack[-1] or (tag == 'script' and self._stack[-1] == 'ld')):
            kind = self._stack.pop()
            text = ''.join(self._buf)
            {'title': self.title, 'h1': self.h1, 'ld': self.ld}[kind].append(text.strip())
            self._buf = None

    def handle_data(self, data):
        if self._buf is not None:
            self._buf.append(data)
        if self._in_main and not (self._stack and self._stack[-1] == 'ld'):
            self.main_text.append(data)


def page_path(out, file):
    rel = '/' + os.path.relpath(file, out).replace(os.sep, '/')
    return rel[:-len('index.html')] if rel.endswith('/index.html') else rel


def resolve(out, href):
    """Файл, который отдаст сервер по внутренней ссылке, или None для внешних."""
    parts = urlsplit(href)
    if parts.scheme in ('mailto', 'tel', 'javascript'):
        return None
    if parts.netloc and parts.netloc != 'n-e-n.ru':
        return None
    path = unquote(parts.path)
    if parts.netloc == 'n-e-n.ru' and not path.startswith(BASE + '/') and path != BASE:
        return None                       # остальной сайт НЭН — не наш
    if not path.startswith(BASE):
        return 'outside'
    rel = path[len(BASE):] or '/'
    target = os.path.join(out, rel.lstrip('/'))
    if rel.endswith('/'):
        target = os.path.join(target, 'index.html')
    return target


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'dist'
    errors, warnings = collections.defaultdict(list), collections.defaultdict(list)
    pages, titles, descs, texts, inbound = {}, collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(list), collections.Counter()
    files = sorted(os.path.join(d, f) for d, _, fs in os.walk(out) for f in fs if f.endswith('.html'))
    for file in files:
        path = page_path(out, file)
        p = Page()
        p.feed(open(file, encoding='utf-8').read())
        pages[path] = p
        robots = (p.meta.get('robots') or [''])[0]
        noindex = 'noindex' in robots
        err, warn = errors[path], warnings[path]

        if p.lang != 'ru':
            err.append('нет lang="ru"')
        if not p.meta.get('viewport'):
            err.append('нет viewport')
        if len(p.title) != 1 or not p.title[0]:
            err.append(f'title: {len(p.title)} шт.')
        else:
            t = p.title[0]
            titles[t].append(path)
            if len(t) > TITLE_MAX:
                warn.append(f'title длиннее {TITLE_MAX} ({len(t)}): {t}')
            if len(t) < 15:
                warn.append(f'короткий title: {t}')
        d = (p.meta.get('description') or [''])
        if len(d) != 1 or not d[0]:
            err.append('нет description')
        else:
            descs[d[0]].append(path)
            if not DESC_MIN <= len(d[0]) <= DESC_MAX:
                warn.append(f'description {len(d[0])} знаков')
        if len(p.h1) != 1 or not p.h1[0]:
            err.append(f'H1: {len(p.h1)} шт.')
        if not robots:
            err.append('нет meta robots')
        draft = (p.meta.get('nen-status') or [''])[0] == 'draft'   # карточка ждёт проверки редакцией
        if noindex and path not in NOINDEX_OK and not draft:
            err.append('noindex на странице, которая должна индексироваться')
        if not noindex and path in NOINDEX_OK:
            err.append('служебная страница открыта для индексации')
        p.secondary = False
        if path != '/404.html':
            want = ORIGIN + BASE + path
            if not (p.canonical or '').startswith(ORIGIN + BASE + '/'):
                err.append(f'canonical {p.canonical} не на сервис')
            elif p.canonical != want:
                target = resolve(out, p.canonical)
                if not target or not os.path.exists(target):
                    err.append(f'canonical на несуществующую страницу: {p.canonical}')
                p.secondary = True
        for key in ('og:title', 'og:description', 'og:url', 'og:image', 'og:type', 'twitter:card'):
            if not p.meta.get(key):
                err.append(f'нет {key}')
        for key in ('og:image', 'twitter:image'):
            for v in p.meta.get(key, []):
                if not v.startswith('https://'):
                    err.append(f'{key} без полного адреса: {v}')
        for raw in p.ld:
            try:
                data = json.loads(raw)
            except ValueError as ex:
                err.append(f'JSON-LD не разбирается: {ex}')
                continue
            for node in data.get('@graph', [data]):
                if '@type' not in node:
                    err.append('JSON-LD: узел без @type')
                for k in ('url', '@id', 'image'):
                    v = node.get(k)
                    if isinstance(v, str) and not v.startswith('https://'):
                        err.append(f'JSON-LD {k} без полного адреса: {v}')
        if not noindex and not p.ld and path != '/':
            warn.append('нет разметки schema.org')
        for img in p.imgs:
            if 'alt' not in img:
                err.append(f'картинка без alt: {img.get("src")}')
            if not (img.get('width') and img.get('height')):
                warn.append(f'картинка без размеров: {img.get("src")}')
            src = img.get('src') or ''
            if src.startswith('http://'):
                err.append(f'картинка по http: {src}')
        for href in p.links:
            if href.startswith('#'):
                continue
            if href.startswith('http://'):
                err.append(f'ссылка по http: {href}')
            target = resolve(out, href)
            if target == 'outside':
                err.append(f'ссылка за пределы сервиса без домена: {href}')
            elif target:
                if not os.path.exists(target):
                    err.append(f'битая ссылка: {href}')
                else:
                    inbound[page_path(out, target)] += 1
        text = re.sub(r'\s+', ' ', ' '.join(p.main_text)).strip()
        words = len(re.findall(r'\w+', text))
        if not noindex and words < THIN_WORDS:
            warn.append(f'мало текста: {words} слов')
        if not noindex and not p.secondary:
            texts[hashlib.md5(text.encode()).hexdigest()].append(path)
        if os.path.getsize(file) > 400_000:
            warn.append(f'тяжелая страница: {os.path.getsize(file) // 1024} КБ')

    canon = {path for path, p in pages.items() if not p.secondary}
    for t, ps in titles.items():
        ps = [x for x in ps if x in canon]
        if len(ps) > 1:
            for path in ps:
                errors[path].append(f'title повторяется на {len(ps)} страницах: {t}')
    for dsc, ps in descs.items():
        ps = [x for x in ps if x in canon]
        if len(ps) > 1:
            for path in ps:
                errors[path].append(f'description повторяется на {len(ps)} страницах')
    for h, ps in texts.items():
        if len(ps) > 1:
            for path in ps:
                warnings[path].append(f'одинаковый текст с {len(ps) - 1} другими страницами')
    for path, p in pages.items():
        if path not in ('/', '/404.html') and not inbound[path] and 'noindex' not in (p.meta.get('robots') or [''])[0]:
            warnings[path].append('на страницу никто не ссылается')

    # sitemap и robots
    site_err = []
    sm_file = os.path.join(out, 'sitemap.xml')
    if not os.path.exists(sm_file):
        site_err.append('нет sitemap.xml')
    else:
        locs = re.findall(r'<loc>([^<]+)</loc>', open(sm_file, encoding='utf-8').read())
        in_sitemap = {l[len(ORIGIN + BASE):] for l in locs}
        if len(locs) > 50000:
            site_err.append('в sitemap больше 50 000 адресов — нужен индекс sitemap')
        for path, p in pages.items():
            noindex = 'noindex' in (p.meta.get('robots') or [''])[0]
            if not noindex and not p.secondary and path not in in_sitemap and path != '/404.html':
                site_err.append(f'нет в sitemap: {path}')
            if (noindex or p.secondary) and path in in_sitemap:
                site_err.append(f'в sitemap закрытая или неканоническая страница: {path}')
        for path in in_sitemap - set(pages):
            site_err.append(f'в sitemap несуществующая страница: {path}')
    rb = os.path.join(out, 'robots.txt')
    robots_txt = open(rb, encoding='utf-8').read() if os.path.exists(rb) else ''
    if 'Sitemap:' not in robots_txt and 'Disallow: /\n' not in robots_txt:
        site_err.append('в robots.txt нет ссылки на sitemap')

    n_err = sum(len(v) for v in errors.values()) + len(site_err)
    n_warn = sum(len(v) for v in warnings.values())
    kinds_e = collections.Counter(re.sub(r':.*', '', m) for v in errors.values() for m in v)
    kinds_w = collections.Counter(re.sub(r'[:(\d].*', '', m).strip() for v in warnings.values() for m in v)
    print(f'страниц: {len(pages)} (с canonical на другую страницу: {len(pages) - len(canon)}); '
          f'ошибок: {n_err}; предупреждений: {n_warn}')
    for k, n in kinds_e.most_common():
        print(f'  ошибка  {n:5d}  {k}')
    for k, n in kinds_w.most_common():
        print(f'  предупр {n:5d}  {k}')
    for m in site_err[:20]:
        print('  сайт:', m)
    shown = 0
    for path in sorted(errors):
        for m in errors[path]:
            if shown < 40:
                print(f'  {path}: {m}')
                shown += 1
    if '-v' in sys.argv:
        for path in sorted(warnings):
            for m in warnings[path]:
                print(f'  ~ {path}: {m}')
    sys.exit(1 if n_err else 0)


if __name__ == '__main__':
    main()
