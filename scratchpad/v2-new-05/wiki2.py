import json, sys, urllib.parse, urllib.request, urllib.error, os, ssl, time
ctx = ssl.create_default_context(cafile='/root/.ccr/ca-bundle.crt')
def get(url, tries=6):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'nen-kino-research/1.0 (editorial research bot)'})
            return urllib.request.urlopen(req, timeout=30, context=ctx).read().decode('utf-8')
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5 * (i + 1)); continue
            if e.code == 404: return None
            raise
    return None
def search(lang, q, n=3):
    u = f'https://{lang}.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit={n}&srsearch=' + urllib.parse.quote(q)
    t = get(u)
    return [r['title'] for r in json.loads(t)['query']['search']] if t else []
def raw(lang, title):
    return get(f'https://{lang}.wikipedia.org/w/index.php?action=raw&title=' + urllib.parse.quote(title.replace(' ', '_')))
inp = json.load(open('/home/user/kino/work/in/v2-new-05.json'))
os.makedirs('dl/wiki', exist_ok=True)
idxf = 'dl/wiki/search.json'
idx = json.load(open(idxf)) if os.path.exists(idxf) else {}
for r in inp:
    res = idx.get(r['slug'], {})
    if not res.get('ru') or any(str(x).startswith('ERR') for x in res['ru']):
        res['ru'] = search('ru', f"{r['title']} {r['year']} фильм"); time.sleep(2)
    if r.get('originalTitle') and (not res.get('en') or any(str(x).startswith('ERR') for x in res['en'])):
        res['en'] = search('en', f"{r['originalTitle']} {r['year']} film"); time.sleep(2)
    idx[r['slug']] = res
    json.dump(idx, open(idxf, 'w'), ensure_ascii=False, indent=1)
    print(r['slug'], res, flush=True)
