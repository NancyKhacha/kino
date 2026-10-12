import json, lzma, re, sys
inp = json.load(open('work/in/v2-new-04.json'))
arch = {}
with lzma.open(sys.argv[1], 'rt', encoding='utf-8') as f:
    for line in f:
        r = json.loads(line); arch[r['url'].rstrip('/')] = r
keys = {
 'lilo-i-stich-2025':['Стич','Лило'], 'lilovyy-shar':['Лилов'], 'malenkaya-miss-schaste':['мисс Сч','Sunshine'],
 'malyshi-v-dikoy-prirode':['Малыши'], 'mandariniya-strana-chudes':['Мандарин'], 'mezhsezone':['Межсезон','Хант'],
 'merkuriy-v-opasnosti':['Меркур'], 'miss-potter':['Поттер'], 'moy-malysh-smog-by-eto-narisovat':['малыш смог','Marla','Марл','Olmstead','Олмстед'],
 'moy-uchitel-osminog':['осьминог'], 'musornye-mechty':['Мусорн'], 'mustang':['Мустанг'], 'meri-poppins-vozvrashchaetsya':['Поппинс'],
 'na-grebne-volny':['гребне'], 'navernoe-bogi-soshli-s-uma':['боги'], 'nash-dom':['Наш дом'], 'nevezuchie':['Невезуч'],
 'nevidimaya-storona':['Невидим'], 'nevidimyy-mir':['Невидим','Вандел'], 'neobyknovennaya-istoriya-na-rozhdestvo':['Необыкновен','Диккенс'],
 'novye-priklyucheniya-peppi-dlinnyychulok':['Пеппи'], 'obutylochnye':['Обутыл','Tapped'], 'obshchestvo-mertvyh-poetov':['поэтов'],
 'odin-doma-2-zateryannyy-v-nyu-yorke':['Один дома','Нью-Йорк'], 'ostrov-propavshih-devchonok':['Остров','девчон'],
}
for e in inp:
    u = e['discovery'].get('nenUrl')
    if not u: continue
    r = arch.get(u.rstrip('/'))
    print('=====', e['slug'], u, 'FOUND' if r else 'NOT IN ARCHIVE', r and r['date'])
    if not r: continue
    body = r['body']
    paras = body.split('\n')
    for i,p in enumerate(paras):
        if any(k.lower() in p.lower() for k in keys.get(e['slug'],[])):
            ctx = ' '.join(paras[i:i+3])
            print('  >', ctx[:1500])
