import json, glob, re
inp = json.load(open('work/in/v2-new-04.json'))
titles = json.load(open('site/data/titles.json'))
def norm(s): return re.sub(r'[^\wа-яё]+',' ',(s or '').lower().replace('ё','е')).strip()
batch_cards=[]
for f in glob.glob('cards/batches/*.json'):
    try:
        for c in json.load(open(f)):
            batch_cards.append((f,c))
    except Exception as e: print('ERR',f,e)
# also other in files v2-new-*
others=[]
for f in glob.glob('work/in/v2-new-*.json'):
    if 'v2-new-04' in f: continue
    for c in json.load(open(f)): others.append((f,c))
for e in inp:
    t=norm(e['title']); o=norm(e.get('originalTitle'))
    hits=[]
    for x in titles:
        xt=norm(x.get('title')); xo=norm(x.get('originalTitle'))
        if (t and (t==xt or (len(t)>5 and t in xt))) or (o and (o==xo or (len(o)>5 and o in xo))):
            hits.append(f"titles:{x['slug']}|{x['title']}|{x.get('originalTitle')}|{x.get('year')}")
    for f,c in batch_cards:
        ct=norm(c.get('title')); 
        if t and (t==ct or (len(t)>5 and t in ct)):
            hits.append(f"{f}:{c.get('slug')}|{c.get('decision')}")
    for f,c in others:
        ct=norm(c.get('title')); co=norm(c.get('originalTitle'))
        if (t and t==ct) or (o and o==co):
            hits.append(f"OTHER {f}:{c.get('slug')}|{c.get('year')}")
    print(e['slug'], '->', hits if hits else '-')
