/* «Что посмотреть с детьми»: фильтры каталога, подбор, избранное, «Поделиться».
   Страницы целиком собраны на сервере; без JavaScript всё читается и все ссылки работают. */
(function () {
  'use strict';
  var BASE = document.body.getAttribute('data-base') || '';
  var FAV_KEY = 'nen-kino-favorites';
  var SHOWN = 48;
  var indexPromise = null;

  function loadIndex() {
    if (!indexPromise) {
      indexPromise = fetch(BASE + '/data/index.json').then(function (r) { return r.json(); });
    }
    return indexPromise;
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function plural(n, one, few, many) {
    if (n % 10 === 1 && n % 100 !== 11) return one;
    if ([2, 3, 4].indexOf(n % 10) >= 0 && [12, 13, 14].indexOf(n % 100) < 0) return few;
    return many;
  }
  function films(n) { return n + ' ' + plural(n, 'фильм', 'фильма', 'фильмов'); }
  function years(n) { return plural(n, 'год', 'года', 'лет'); }

  // Индекс: [slug, title, kind, year, ageMin, ageMax, themes, moods, frame, snippet, ageLabel, rank, minutes, typeLabel, original]
  var GEN = { multfilm: 'мультфильма', multserial: 'мультсериала', film: 'фильма', serial: 'сериала' };

  function card(idx, t) {
    var kind = idx.kinds[t[2]];
    var href = BASE + '/' + kind + '/' + t[0] + '/';
    var cover = t[8]
      ? '<div class="cover"><img src="' + BASE + '/frames/' + esc(t[0]) + '.webp" alt="' + esc('Кадр из ' + GEN[kind] + ' «' + t[1] + '»') + '" width="720" height="405" loading="lazy" decoding="async"></div>'
      : '<div class="cover frame-empty" aria-hidden="true"><span>' + esc(t[1]) + '</span></div>';
    var tags = '<span class="tag tag-blue">' + esc(t[10]) + '</span>';
    if (t[7].length) tags += '<span class="tag tag-yellow">' + esc(idx.moods[t[7][0]]) + '</span>';
    return '<article class="card film-card">' + cover +
      '<h3 class="title"><a href="' + href + '">' + esc(t[1]) + '</a></h3>' +
      '<p class="author">' + esc(t[13] + ' · ' + t[3]) + '</p><p class="snippet">' + esc(t[9]) + '</p>' +
      '<div class="tags">' + tags + '</div></article>';
  }

  function grid(idx, list) {
    return '<div class="grid grid-4">' + list.map(function (t) { return card(idx, t); }).join('') + '</div>';
  }

  function norm(s) { return String(s || '').toLowerCase().replace(/ё/g, 'е'); }

  function filterTitles(idx, f) {
    var q = norm(f.q).trim();
    var theme = f.theme ? idx.themes.indexOf(f.theme) : -1;
    var kinds = (f.kinds || []).map(function (k) { return idx.kinds.indexOf(k); });
    var themesAny = (f.themes || []).map(function (t) { return idx.themes.indexOf(t); }).filter(function (i) { return i >= 0; });
    var moodsAny = (f.moods || []).map(function (m) { return idx.moods.indexOf(m); }).filter(function (i) { return i >= 0; });
    return idx.titles.filter(function (t) {
      if (kinds.length && kinds.indexOf(t[2]) < 0) return false;
      if (f.age && !(t[4] <= f.age && f.age <= t[5])) return false;
      if (theme >= 0 && t[6].indexOf(theme) < 0) return false;
      if (themesAny.length && !themesAny.some(function (i) { return t[6].indexOf(i) >= 0; })) return false;
      if (moodsAny.length && !moodsAny.some(function (i) { return t[7].indexOf(i) >= 0; })) return false;
      if (f.short && !(t[12] && t[12] <= 30)) return false;
      if (q) {
        var hay = norm(t[1] + ' ' + t[14] + ' ' + t[9] + ' ' + t[6].map(function (i) { return idx.themes[i] + ' ' + idx.themeNames[i]; }).join(' '));
        if (q.split(/\s+/).some(function (w) { return hay.indexOf(w) < 0; })) return false;
      }
      return true;
    });
  }

  /* ── Каталог ── */
  function initCatalog() {
    var form = document.getElementById('catalog-filters');
    var box = document.getElementById('catalog-results');
    if (!form || !box) return;
    var serverList = Array.prototype.slice.call(document.querySelectorAll('#catalog-results ~ .results-meta, #catalog-results ~ .grid, #catalog-results ~ .pager'));
    var shown = SHOWN;
    var params = new URLSearchParams(location.search);
    var state = {
      q: params.get('q') || '', kind: params.get('kind') || '', age: parseInt(params.get('age'), 10) || 0,
      theme: params.get('theme') || '', mood: params.get('mood') || '', short: params.get('short') === '1'
    };
    form.q.value = state.q;
    form.kind.value = state.kind;
    form.age.value = state.age || '';
    form.theme.value = state.theme;

    function active() { return state.q || state.kind || state.age || state.theme || state.mood || state.short; }
    function syncChips() {
      form.querySelectorAll('[data-mood]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-mood') === state.mood)); });
      form.querySelectorAll('[data-short]').forEach(function (b) { b.setAttribute('aria-pressed', String(state.short)); });
    }
    function render() {
      syncChips();
      var p = new URLSearchParams();
      if (state.q) p.set('q', state.q);
      if (state.kind) p.set('kind', state.kind);
      if (state.age) p.set('age', state.age);
      if (state.theme) p.set('theme', state.theme);
      if (state.mood) p.set('mood', state.mood);
      if (state.short) p.set('short', '1');
      // replaceState, а не pushState: ввод в поиске не засоряет историю браузера
      history.replaceState(null, '', location.pathname + (p.toString() ? '?' + p : ''));
      if (!active()) {
        box.hidden = true;
        serverList.forEach(function (el) { el.hidden = false; });
        return;
      }
      loadIndex().then(function (idx) {
        var list = filterTitles(idx, { q: state.q, kinds: state.kind ? [state.kind] : [], age: state.age, theme: state.theme,
          moods: state.mood ? [state.mood] : [], short: state.short });
        serverList.forEach(function (el) { el.hidden = true; });
        box.hidden = false;
        var n = list.length;
        var head = '<div class="results-meta"><span class="meta">' + (n ? 'Нашлось: ' + films(n) : '') + '</span></div>';
        if (!n) {
          box.innerHTML = head + '<p class="empty">Ничего не нашлось. Попробуйте убрать один из фильтров.</p>';
          return;
        }
        box.innerHTML = head + grid(idx, list.slice(0, shown)) +
          (n > shown ? '<div class="btn-row" style="margin-top:24px"><button class="btn btn-secondary" type="button" data-more>Показать ещё</button></div>' : '');
      });
    }
    form.addEventListener('submit', function (ev) { ev.preventDefault(); });
    form.addEventListener('input', function (ev) {
      var t = ev.target;
      if (t.name === 'q') state.q = t.value;
      if (t.name === 'kind') state.kind = t.value;
      if (t.name === 'age') state.age = parseInt(t.value, 10) || 0;
      if (t.name === 'theme') state.theme = t.value;
      shown = SHOWN;
      render();
    });
    form.addEventListener('click', function (ev) {
      var t = ev.target.closest('button');
      if (!t) return;
      if (t.hasAttribute('data-mood')) state.mood = state.mood === t.getAttribute('data-mood') ? '' : t.getAttribute('data-mood');
      if (t.hasAttribute('data-short')) state.short = !state.short;
      shown = SHOWN;
      render();
    });
    box.addEventListener('click', function (ev) {
      if (ev.target.hasAttribute('data-more')) { shown += SHOWN; render(); }
    });
    if (active()) render(); else syncChips();
  }

  /* ── Подбор ── */
  function initQuiz() {
    var form = document.getElementById('quiz');
    var out = document.getElementById('quiz-results');
    if (!form) return;
    form.hidden = false;
    var age = 5, step = 1, kinds = [], moods = [], themes = [];
    var ageOut = form.querySelector('output[name=age]');

    function toggle(list, value, btn) {
      var i = list.indexOf(value);
      if (i >= 0) list.splice(i, 1); else list.push(value);
      btn.setAttribute('aria-pressed', String(i < 0));
    }
    function show() {
      form.querySelectorAll('.step').forEach(function (s) { s.classList.toggle('is-active', +s.getAttribute('data-step') === step); });
      ageOut.textContent = age + ' ' + years(age);
    }
    form.addEventListener('click', function (ev) {
      var t = ev.target.closest('button');
      if (!t) return;
      if (t.hasAttribute('data-age')) age = Math.max(2, Math.min(17, age + (+t.getAttribute('data-age'))));
      if (t.hasAttribute('data-next')) step = Math.min(3, step + 1);
      if (t.hasAttribute('data-prev')) step = Math.max(1, step - 1);
      if (t.hasAttribute('data-kind')) toggle(kinds, t.getAttribute('data-kind'), t);
      if (t.hasAttribute('data-mood')) toggle(moods, t.getAttribute('data-mood'), t);
      if (t.hasAttribute('data-theme')) toggle(themes, t.getAttribute('data-theme'), t);
      show();
    });
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      loadIndex().then(function (idx) {
        var list = filterTitles(idx, { age: age, kinds: kinds, moods: moods, themes: themes });
        // Сначала то, что ближе всего к возрасту ребёнка и написано по знанию фильма
        list.sort(function (a, b) {
          var da = Math.abs(a[4] - age) + (a[5] >= 18 ? 1 : 0);
          var db = Math.abs(b[4] - age) + (b[5] >= 18 ? 1 : 0);
          return (a[11] - b[11]) || (da - db);
        });
        var n = list.length;
        out.innerHTML = n
          ? '<h2 class="h2">Нашлось: ' + films(n) + '</h2><p class="meta" style="margin:8px 0 20px">Для ребёнка ' + age + ' ' + years(age) + '.</p>' + grid(idx, list.slice(0, 24))
          : '<p class="empty">Ничего не нашлось. Попробуйте выбрать меньше тем или другое настроение.</p>';
        out.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
    show();
  }

  /* ── Избранное ── */
  function favs() {
    try { return JSON.parse(localStorage.getItem(FAV_KEY)) || []; } catch (e) { return []; }
  }
  function saveFavs(list) {
    try { localStorage.setItem(FAV_KEY, JSON.stringify(list)); } catch (e) { /* приватный режим */ }
  }
  function initFavs() {
    document.querySelectorAll('[data-fav]').forEach(function (btn) {
      var slug = btn.getAttribute('data-fav');
      function sync() {
        var on = favs().indexOf(slug) >= 0;
        btn.setAttribute('aria-pressed', String(on));
        btn.textContent = on ? 'В избранном' : 'Сохранить в избранное';
      }
      btn.addEventListener('click', function () {
        var list = favs();
        var i = list.indexOf(slug);
        if (i >= 0) list.splice(i, 1); else list.unshift(slug);
        saveFavs(list);
        sync();
      });
      sync();
    });
    var box = document.getElementById('favorites');
    if (!box) return;
    var list = favs();
    if (!list.length) return;
    loadIndex().then(function (idx) {
      var bySlug = {};
      idx.titles.forEach(function (t) { bySlug[t[0]] = t; });
      var items = list.map(function (s) { return bySlug[s]; }).filter(Boolean);
      if (items.length) box.innerHTML = grid(idx, items);
    });
  }

  /* ── Поделиться ── */
  function initShare() {
    document.querySelectorAll('.share').forEach(function (box) {
      var text = box.getAttribute('data-share-text') || document.title;
      var link = location.origin + location.pathname;
      var u = encodeURIComponent(link), t = encodeURIComponent(text);
      var nets = {
        'Телеграм': 'https://t.me/share/url?url=' + u + '&text=' + t,
        'ВКонтакте': 'https://vk.com/share.php?url=' + u + '&title=' + t,
        'WhatsApp': 'https://wa.me/?text=' + t + '%20' + u,
        'Одноклассники': 'https://connect.ok.ru/offer?url=' + u + '&title=' + t
      };
      box.querySelectorAll('a[data-net]').forEach(function (a) {
        var href = nets[a.getAttribute('data-net')];
        if (href) a.href = href;
      });
      box.querySelector('summary').addEventListener('click', function (ev) {
        if (navigator.share && matchMedia('(pointer: coarse)').matches) {
          ev.preventDefault();
          navigator.share({ title: text, url: link }).catch(function () {});
        }
      });
      var copy = box.querySelector('[data-copy]');
      copy.addEventListener('click', function () {
        function done() { copy.textContent = 'Ссылка скопирована'; setTimeout(function () { copy.textContent = 'Скопировать ссылку'; box.open = false; }, 1500); }
        if (navigator.clipboard) navigator.clipboard.writeText(link).then(done, function () { prompt('Ссылка:', link); });
        else { prompt('Ссылка:', link); }
      });
    });
    document.addEventListener('click', function (ev) {
      document.querySelectorAll('.share[open]').forEach(function (box) { if (!box.contains(ev.target)) box.open = false; });
    });
  }

  /* Кадр не загрузился: показываем плашку с названием, а не пустой прямоугольник */
  document.addEventListener('error', function (ev) {
    var img = ev.target;
    if (!img || img.tagName !== 'IMG') return;
    var box = img.parentNode;
    if (box && box.classList.contains('mini-frames')) { box.removeChild(img); return; }
    if (box && (box.classList.contains('cover') || box.classList.contains('film-frame') || box.classList.contains('pick-cover'))) {
      var name = (img.alt || '').replace(/^Кадр из \S+ /, '').replace(/[«»]/g, '');
      box.classList.add('frame-empty');
      box.innerHTML = '<span>' + esc(name) + '</span>';
    } else {
      img.style.visibility = 'hidden';
    }
  }, true);

  initCatalog();
  initQuiz();
  initFavs();
  initShare();
})();
