import json, subprocess, re, sys
SK='/root/.claude/skills/synced/f7ccfefe-05de-4465-93bf-ad369ae8247d_1ad558a8-e228-4b1e-b9c5-af5a6513b041/nen-archive/scripts'
inp=json.load(open('/home/user/kino/work/in/v2-new-06.json'))
only=sys.argv[1:] 
cache={}
for e in inp:
    if only and e['slug'] not in only: continue
    url=(e.get('discovery') or {}).get('nenUrl')
    if not url: continue
    if url not in cache:
        r=subprocess.run(['python3','search.py','--full',url],cwd=SK,capture_output=True,text=True)
        cache[url]=r.stdout
    txt=cache[url]
    keys=[e['title']]
    if e.get('originalTitle'): keys.append(e['originalTitle'])
    # use stem of title
    stems=[k.split(':')[0].split('.')[0][:max(5,len(k)//2)] for k in keys]
    paras=[p for p in re.split(r'\n+',txt) if any(s.lower() in p.lower() for s in stems)]
    print('=====',e['slug'],url, 'len',len(txt))
    for p in paras[:4]:
        print('  >',p[:1500])
