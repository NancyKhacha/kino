import re, sys, glob, os
D=sys.argv[1]
keys_ru=['РусНаз','ОригНаз','Режиссёр','Режиссер','Страна','Год','Время','Длительность','Возраст','Рейтинг','Продолжение','Предыдущий','Следующий','Жанр','Компания']
keys_en=['director','runtime','country','released','release_date','based_on','name']
for f in sorted(glob.glob(os.path.join(D,'*.txt'))):
    t=open(f).read()
    print('=====',os.path.basename(f))
    keys = keys_ru if f.endswith('.ru.txt') else keys_en
    for k in keys:
        for m in re.finditer(r'^\s*\|\s*'+k+r'\s*=\s*(.*)$', t, re.M):
            v=m.group(1).strip()
            if v: print(f'  {k}: {v[:200]}')
