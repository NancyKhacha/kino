import json, glob, re, sys
inp = json.load(open('work/in/v2-new-05.json'))
titles = json.load(open('site/data/titles.json'))
batches = {}
for f in glob.glob('cards/batches/*.json'):
    try:
        batches[f] = json.load(open(f))
    except Exception as e:
        print('ERR', f, e)
def norm(s): return (s or '').lower().replace('ё','е')
for r in inp:
    keys = [norm(r['title'])]
    if r['originalTitle']: keys.append(norm(r['originalTitle']))
    # short key: first part before colon
    hits = []
    for t in titles:
        tt = norm(t.get('title')); ot = norm(t.get('originalTitle'))
        for k in keys:
            if k and (k == tt or k == ot or (len(k) > 6 and (k in tt or k in ot))):
                hits.append(f"T:{t['slug']}|{t['title']}|{t.get('originalTitle')}|{t['year']}")
                break
    for f, cards in batches.items():
        for c in cards:
            st = norm(c.get('title')); fx = c.get('fixes') or {}
            ft = norm(fx.get('title')); fo = norm(fx.get('originalTitle'))
            for k in keys:
                if k and (k == st or k == ft or k == fo or (len(k) > 6 and (k in st))):
                    hits.append(f"B:{f.split('/')[-1]}:{c['slug']}|{c.get('decision')}")
                    break
            if c.get('slug') == r['slug']:
                hits.append(f"SLUG:{f}")
    print(r['slug'], '=>', sorted(set(hits)))
