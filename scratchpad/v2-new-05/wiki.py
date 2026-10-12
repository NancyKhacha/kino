import json, sys, urllib.parse, urllib.request, os, ssl
ctx = ssl.create_default_context(cafile='/root/.ccr/ca-bundle.crt')
def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'nen-kino-research/1.0 (contact trulyalyalya)'})
    return urllib.request.urlopen(req, timeout=30, context=ctx).read().decode('utf-8')
def search(lang, q, n=3):
    u = f'https://{lang}.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit={n}&srsearch=' + urllib.parse.quote(q)
    return [r['title'] for r in json.loads(get(u))['query']['search']]
def raw(lang, title):
    return get(f'https://{lang}.wikipedia.org/w/index.php?action=raw&title=' + urllib.parse.quote(title.replace(' ', '_')))
if __name__ == '__main__':
    inp = json.load(open('/home/user/kino/work/in/v2-new-05.json'))
    os.makedirs('dl/wiki', exist_ok=True)
    idx = {}
    for r in inp:
        res = {}
        try:
            res['ru'] = search('ru', f"{r['title']} {r['year']} фильм")
        except Exception as e:
            res['ru'] = ['ERR ' + str(e)]
        if r.get('originalTitle'):
            try:
                res['en'] = search('en', f"{r['originalTitle']} {r['year']} film")
            except Exception as e:
                res['en'] = ['ERR ' + str(e)]
        idx[r['slug']] = res
        print(r['slug'], res, flush=True)
    json.dump(idx, open('dl/wiki/search.json', 'w'), ensure_ascii=False, indent=1)
