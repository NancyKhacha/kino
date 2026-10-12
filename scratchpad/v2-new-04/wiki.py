import json, sys, urllib.parse, subprocess, os
OUT = sys.argv[1]
def get(url):
    r = subprocess.run(['curl','-sS','-L','--max-time','30','-A','Mozilla/5.0 (research bot; kino cards)',url],capture_output=True)
    return r.stdout.decode('utf-8','replace')
def search(lang, q, n=5):
    u=f'https://{lang}.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit={n}&srsearch='+urllib.parse.quote(q)
    try: return [x['title'] for x in json.loads(get(u))['query']['search']]
    except Exception as e: return ['ERR '+str(e)]
def raw(lang, title):
    u=f'https://{lang}.wikipedia.org/w/index.php?action=raw&redirect=true&title='+urllib.parse.quote(title.replace(' ','_'))
    return get(u)
if __name__=='__main__':
    mode=sys.argv[2]
    if mode=='search':
        lang=sys.argv[3]
        for q in sys.argv[4:]:
            print(q,'=>',search(lang,q))
    elif mode=='raw':
        lang=sys.argv[3]; name=sys.argv[4]; title=sys.argv[5]
        t=raw(lang,title)
        if t.startswith('#REDIRECT') or t.startswith('#перенаправление') or t.startswith('#ПЕРЕНАПРАВЛЕНИЕ'):
            import re
            m=re.search(r'\[\[([^\]]+)\]\]',t); t=raw(lang,m.group(1))
        open(os.path.join(OUT,f'{name}.{lang}.txt'),'w').write(t)
        print(name,lang,len(t))
