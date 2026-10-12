import json, glob, re, sys
ROOT='/home/user/kino'
inp=json.load(open(f'{ROOT}/work/in/v2-new-06.json'))
titles=json.load(open(f'{ROOT}/site/data/titles.json'))
batches={}
for p in glob.glob(f'{ROOT}/cards/batches/*.json'):
    try:
        for c in json.load(open(p)):
            batches.setdefault(p.split('/')[-1],[]).append(c)
    except Exception as e: print('ERR',p,e)
# also other inputs
ins={}
for p in glob.glob(f'{ROOT}/work/in/*.json'):
    if 'v2-new-06' in p: continue
    try:
        for c in json.load(open(p)):
            ins.setdefault(p.split('/')[-1],[]).append(c)
    except Exception as e: print('ERR',p,e)
def norm(s): return re.sub(r'[^\wа-яё]','',(s or '').lower().replace('ё','е'))
for e in inp:
    keys=[k for k in (e['title'],e.get('originalTitle')) if k]
    keyn=[norm(k) for k in keys]
    hits=[]
    for t in titles:
        for k in keyn:
            if k and (k in norm(t['title']) or (t.get('originalTitle') and k==norm(t['originalTitle']))):
                hits.append(f"titles: {t['slug']} | {t['title']} | {t.get('originalTitle')} | {t['year']} | {t['kind']}")
                break
    for b,cs in batches.items():
        for c in cs:
            for k in keyn:
                if k and (k in norm(c.get('title'))  or k in norm((c.get('fixes') or {}).get('title')) or k in norm((c.get('fixes') or {}).get('originalTitle'))):
                    hits.append(f"batch {b}: {c['slug']} | {c.get('title')} | {c.get('decision')}")
                    break
    for b,cs in ins.items():
        for c in cs:
            for k in keyn:
                if k and (k in norm(c.get('title')) or (c.get('originalTitle') and k==norm(c.get('originalTitle')))):
                    hits.append(f"in {b}: {c['slug']} | {c.get('title')} | {c.get('originalTitle')} | {c.get('year')}")
                    break
    print('==',e['slug'],'|',e['title'],'|',e.get('originalTitle'),e['year'])
    for h in sorted(set(hits)): print('   ',h)
