import json, re, sys, subprocess, urllib.parse, time, os
OUT=sys.argv[1]
inp=json.load(open('work/in/v2-new-04.json'))
def get(url):
    r=subprocess.run(['curl','-sS','-L','--max-time','40','-A','Mozilla/5.0 (X11; Linux x86_64)',url],capture_output=True)
    return r.stdout.decode('utf-8','replace')
override={'obyknovennoe-chudo':'Обыкновенное чудо 1978','odin-doma-2-zateryannyy-v-nyu-yorke':'Один дома 2'}
only=sys.argv[2:] 
res={}
for e in inp:
    if only and e['slug'] not in only: continue
    q=override.get(e['slug'],e['title'])
    s=get('https://kino.mail.ru/search/?q='+urllib.parse.quote(q))
    open(os.path.join(OUT,'kms_'+e['slug']+'.html'),'w').write(s)
    cands=[]
    for m in re.finditer(r'data-qa="Poster" id="(\d+)" main_rubric_id="(\d+)" name_eng="([^"]*)" url="([^"]+)"(.{0,3000}?)data-qa="PosterYear">(.{0,200})', s, re.S):
        yr=re.search(r'(\d{4})', re.sub(r'<[^>]+>',' ',m.group(6)))
        nm=re.search(r'PosterNameLink"[^>]*>([^<]*)<', m.group(5))
        cands.append({'id':m.group(1),'eng':m.group(3),'url':m.group(4),'year':yr.group(1) if yr else None,'name':nm.group(1) if nm else None})
    best=None
    for c in cands:
        if c['year'] and abs(int(c['year'])-e['year'])<=1 and c['url'] not in [x['url'] for x in [best] if x]:
            best=c; break
    info={'cands':cands[:6]}
    if best:
        time.sleep(1)
        p=get(best['url']); open(os.path.join(OUT,'kmp_'+e['slug']+'.html'),'w').write(p)
        wu=best['url']
        i=p.find('"watch_url":"'+wu+'"')
        seg=p[i:i+400] if i>=0 else ''
        ar=re.search(r'"age_restrict":"([^"]*)"',seg)
        dur=re.search(r'"duration":"PT(\d+)M"',p)
        info.update({'best':best,'age':ar.group(1) if ar else None,'dur':dur.group(1) if dur else None})
    res[e['slug']]=info
    print(e['slug'], '|', info.get('best',{}).get('url') if info.get('best') else 'NO MATCH', '|', info.get('age'), '|', info.get('dur'), '|', [(c['name'],c['year'],c['eng']) for c in cands[:4]])
    time.sleep(1)
json.dump(res,open(os.path.join(OUT,'kmail.json'),'w'),ensure_ascii=False,indent=1)
