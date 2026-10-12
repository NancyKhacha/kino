#!/usr/bin/env python3
"""Проверка карточек фильмов по стайлгайду.

  python3 scripts/check_cards.py cards/batches/batch-001.json

Печатает замечания по каждой карточке и итог «с замечаниями: N».
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOCAB = json.load(open(os.path.join(ROOT, 'site', 'content', 'vocab.json'), encoding='utf-8'))

RANGES = {'about': (300, 650), 'whyRecommended': (300, 750), 'parentsNote': (100, 450), 'ageReason': (80, 300)}
# Фильм знаем только по описанию: дописывать нечем, выдумывать нельзя.
RANGES_DESCRIPTION = {'about': (150, 650), 'whyRecommended': (150, 750), 'parentsNote': (80, 450), 'ageReason': (60, 300)}
BANNED = re.compile(r'чудесн|увлекательн|незабываем|красочн|шедевр|must see|от мала до велика|развивает воображение|'
                    r'учит дружбе и доброте|заставляет задуматься|обязательно посмотрите', re.I)
FIELDS = ('slug', 'title', 'decision', 'source', 'ageMin', 'ageMax', 'ageReason', 'about', 'whyRecommended', 'parentsNote',
          'discussionQuestions', 'themes', 'mood', 'sensitiveTopics', 'seoDescription', 'editorNotes')
FIXABLE = {'title', 'year', 'country', 'originalTitle', 'kind', 'minutes', 'episodeMinutes'}


def check(card):
    if card.get('decision') == 'skip':
        return [] if card.get('skipReason') else ['skip без skipReason']
    if card.get('decision') != 'publish':
        return ['decision должно быть publish или skip']
    problems = [f'нет поля {f}' for f in FIELDS if f not in card]
    if problems:
        return problems
    if card['source'] not in ('knowledge', 'description'):
        problems.append('source должно быть knowledge или description')
    ranges = RANGES_DESCRIPTION if card['source'] == 'description' else RANGES
    for field, (lo, hi) in ranges.items():
        n = len(card.get(field) or '')
        if not lo <= n <= hi:
            problems.append(f'{field}: {n} знаков (нужно {lo}–{hi})')
    if len(card['seoDescription']) > 160:
        problems.append(f'seoDescription: {len(card["seoDescription"])} знаков (лимит 160)')
    if not re.match(r'Для (детей|подростков)', card['seoDescription']):
        problems.append('seoDescription начинается не с «Для детей…» / «Для подростков…»')
    for field in ('about', 'whyRecommended', 'parentsNote', 'ageReason', 'seoDescription'):
        m = BANNED.search(card.get(field) or '')
        if m:
            problems.append(f'{field}: штамп «{m.group(0)}»')
        if '!' in (card.get(field) or '').replace('!»', ''):
            problems.append(f'{field}: восклицательный знак')
    if len(card['discussionQuestions']) != 3:
        problems.append(f'вопросов {len(card["discussionQuestions"])}, нужно 3')
    lo, hi = card['ageMin'], card['ageMax']
    if not isinstance(lo, int) or not 0 <= lo <= 17:
        problems.append(f'ageMin {lo!r}')
    if hi is not None and (not isinstance(hi, int) or hi < lo or hi > 18):
        problems.append(f'ageMax {hi!r}')
    if not 1 <= len(card['themes']) <= 5:
        problems.append(f'тем {len(card["themes"])}, нужно 1–5')
    for t in card['themes']:
        if t not in VOCAB['themes']:
            problems.append(f'тема не из словаря: {t}')
    for m in card['mood']:
        if m not in VOCAB['moods']:
            problems.append(f'настроение не из словаря: {m}')
    if not 1 <= len(card['mood']) <= 2:
        problems.append(f'настроений {len(card["mood"])}, нужно 1–2')
    for s in card['sensitiveTopics']:
        if s not in VOCAB['sensitive']:
            problems.append(f'сложная тема не из словаря: {s}')
    if card['source'] == 'description' and not any('сверить' in n for n in card['editorNotes']):
        problems.append('source=description без пометки «сверить с фильмом» в editorNotes')
    for k in (card.get('fixes') or {}):
        if k not in FIXABLE:
            problems.append(f'fixes: поле {k} нельзя исправлять')
    text = ' '.join(str(card.get(f) or '') for f in ('about', 'whyRecommended', 'parentsNote', 'ageReason'))
    if re.search(r'"[^"]+"', text):
        problems.append('прямые кавычки вместо «ёлочек»')
    if re.search(r'(\d+)–(\d+) лет', card['ageReason'] + card['seoDescription']):
        for a, b in re.findall(r'(\d+)–(\d+) лет', card['ageReason']):
            if int(b) % 10 in (1, 2, 3, 4) and int(b) % 100 not in (11, 12, 13, 14) and 'для' not in card['ageReason']:
                problems.append(f'возраст «{a}–{b} лет» — проверьте падеж')
    return problems


def main(paths):
    total = bad = 0
    for path in paths:
        cards = json.load(open(path, encoding='utf-8'))
        for c in cards:
            total += 1
            p = check(c)
            if p:
                bad += 1
                print(f'{c.get("slug")}: ' + '; '.join(p))
    print(f'карточек: {total}, с замечаниями: {bad}')
    return bad


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(1 if main(sys.argv[1:]) else 0)
