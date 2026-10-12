import json, re, html, os, sys, time, urllib.parse, subprocess
def curl(url, out):
    subprocess.run(['curl', '-sS', '-m', '40', '-L', '-A', 'Mozilla/5.0 (X11; Linux x86_64)', '-o', out, url], check=False)
    return open(out, encoding='utf-8', errors='ignore').read() if os.path.exists(out) else ''
def text(t):
    s = re.sub(r'<script.*?</script>', '', t, flags=re.S)
    s = re.sub(r'<style.*?</style>', '', s, flags=re.S)
    s = re.sub(r'<[^>]+>', ' ', s); s = html.unescape(s); return re.sub(r'\s+', ' ', s)
def search(q, slug):
    t = curl('https://kino.mail.ru/search/?q=' + urllib.parse.quote(q), f'dl/km/s_{slug}.html')
    res = []
    for m in re.finditer(r'data-qa="Poster" id="(\d+)" main_rubric_id="\d+" name_eng="([^"]*)" url="([^"]+)".*?PosterNameLink"[^>]*>([^<]+)</a><div[^>]*><div[^>]*data-qa="PosterYear">([^<]*)<', t, flags=re.S):
        res.append({'id': m.group(1), 'eng': html.unescape(m.group(2)), 'url': m.group(3), 'name': html.unescape(m.group(4)), 'year': m.group(5)})
    return res
def page(url, slug):
    t = text(curl(url, f'dl/km/p_{slug}.html'))
    i = t.find('Ваша оценка буду смотреть')
    body = t[i:i+6000] if i >= 0 else t[:6000]
    age = re.search(r'Возрастные ограничения (\d+) \+', t)
    dur = re.search(r'(\d) ч\. (\d+) мин\.|(\d+) мин\.', body)
    return {'age': age.group(1) + '+' if age else None, 'dur': dur.group(0) if dur else None, 'body': body}
if __name__ == '__main__':
    os.makedirs('dl/km', exist_ok=True)
    inp = json.load(open('/home/user/kino/work/in/v2-new-05.json'))
    only = sys.argv[1:]
    out = json.load(open('dl/km/result.json')) if os.path.exists('dl/km/result.json') else {}
    for r in inp:
        if only and r['slug'] not in only: continue
        res = search(r['title'], r['slug'])
        cand = [x for x in res if x['year'].startswith(str(r['year']))] or [x for x in res if x['year'][:4].isdigit() and abs(int(x['year'][:4]) - r['year']) <= 1]
        info = {'search': res[:8]}
        if cand:
            info['pick'] = cand[0]
            info.update(page(cand[0]['url'], r['slug']))
        out[r['slug']] = info
        print(r['slug'], info.get('pick', {}).get('url'), info.get('age'), info.get('dur'), flush=True)
        json.dump(out, open('dl/km/result.json', 'w'), ensure_ascii=False, indent=1)
        time.sleep(1)
