/* Интерактивная карта России.
   Данные (контуры регионов, рек и озёр) лежат в assets/data.js,
   здесь — только отрисовка и обработка наведения/выбора. */
(function () {
  'use strict';

  var D = window.MAP_DATA;
  if (!D) return;

  var NS = 'http://www.w3.org/2000/svg';
  var svg = document.getElementById('map');
  var tip = document.getElementById('tip');
  var card = document.getElementById('card');
  var cardKicker = document.getElementById('card-kicker');
  var cardTitle = document.getElementById('card-title');
  var cardSub = document.getElementById('card-sub');
  var cardBody = document.getElementById('card-body');
  var closeBtn = document.getElementById('close');
  var qInput = document.getElementById('q');
  var hits = document.getElementById('hits');
  var hint = document.getElementById('hint');
  var labelsToggle = document.getElementById('t-labels');
  var waterToggle = document.getElementById('t-water');

  var vb = D.vb || [0, 0, D.w, D.h];
  svg.setAttribute('viewBox', vb.join(' '));
  svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');

  function el(name, attrs, parent) {
    var n = document.createElementNS(NS, name);
    if (attrs) for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }

  var gLand = el('g', null, svg);
  var gSubj = el('g', null, svg);
  var gWater = el('g', { class: 'wlayer' }, svg);
  var gRegion = el('g', null, svg);
  var gLabels = el('g', { class: 'lbl-layer' }, svg);

  el('path', { class: 'land', d: D.land }, gLand);

  /* ---------- округа ---------- */
  var districtById = {};
  D.districts.forEach(function (d, i) {
    districtById[d.id] = d;
    d.__el = el('path', { class: 'region', d: d.d }, gRegion);
    d.__i = i;
  });

  /* ---------- субъекты ---------- */
  var subjEls = Object.create(null);
  D.subjects.forEach(function (s) {
    var p = el('path', {
      class: 'subj',
      d: s.d,
      'data-iso': s.iso,
      tabindex: '0',
      role: 'button',
      'aria-label': s.name
    }, gSubj);
    p.__data = s;
    subjEls[s.iso] = p;
  });

  /* ---------- вода ---------- */
  D.rivers.forEach(function (r) { el('path', { class: 'water-river', d: r.d }, gWater); });
  D.lakes.forEach(function (l) { el('path', { class: 'water-lake', d: l.d }, gWater); });

  /* ---------- подписи ---------- */
  function multiText(parent, x, y, str, cls, lineH) {
    var t = el('text', { class: cls, x: x, y: y }, parent);
    var lines = String(str).split('\n');
    var top = y - (lines.length - 1) * lineH / 2;
    lines.forEach(function (ln, i) {
      var ts = document.createElementNS(NS, 'tspan');
      ts.setAttribute('x', x);
      ts.setAttribute('y', top + i * lineH);
      ts.textContent = ln;
      t.appendChild(ts);
    });
    return t;
  }

  D.districts.forEach(function (d) {
    multiText(gLabels, d.x, d.y, d.name, 'lbl', 22);
  });
  D.seas.forEach(function (s) {
    multiText(gLabels, s.x, s.y, s.name, 'lbl lbl-sea', 17);
  });

  /* ---------- состояние ---------- */
  var mode = 'subject';
  var sel = null;
  var hoveredEl = null;

  function districtName(id) {
    var d = districtById[id];
    return d ? d.name.replace('\n', ' ') : '';
  }

  function showTip(html, ev) {
    tip.innerHTML = html;
    tip.hidden = false;
    moveTip(ev);
  }
  function moveTip(ev) {
    var x = Math.min(ev.clientX + 14, window.innerWidth - 270);
    var y = Math.min(ev.clientY + 14, window.innerHeight - 80);
    tip.style.left = Math.max(8, x) + 'px';
    tip.style.top = Math.max(8, y) + 'px';
  }
  function hideTip() { tip.hidden = true; }

  function clearDistrictHover() {
    var list = gSubj.querySelectorAll('.dhover');
    for (var i = 0; i < list.length; i++) list[i].classList.remove('dhover');
  }
  function hoverDistrict(id) {
    clearDistrictHover();
    if (!id) return;
    D.subjects.forEach(function (s) {
      if (s.district === id && subjEls[s.iso]) subjEls[s.iso].classList.add('dhover');
    });
  }

  function clearSel() {
    var s = gSubj.querySelectorAll('.sel');
    for (var i = 0; i < s.length; i++) s[i].classList.remove('sel');
    var r = gRegion.querySelectorAll('.on');
    for (var j = 0; j < r.length; j++) r[j].classList.remove('on');
    sel = null;
    card.hidden = true;
    setHash(null);
  }

  function hideHint() { if (hint) hint.style.opacity = '0'; }

  function setHash(v) {
    try {
      if (v) history.replaceState(null, '', '#' + v);
      else history.replaceState(null, '', location.pathname + location.search);
    } catch (err) { /* file:// и старые браузеры могут запрещать — не критично */ }
  }

  /* карточка встаёт с той стороны, где не закроет выбранный регион */
  function placeCard(el) {
    if (!el || !el.getBoundingClientRect) return;
    var r = el.getBoundingClientRect();
    var cx = (r.left + r.right) / 2;
    card.classList.toggle('right', cx < window.innerWidth / 2 + 60);
  }

  /* ---------- карточка ---------- */
  function selectSubject(s) {
    if (!s) return;
    clearSel();
    var p = subjEls[s.iso];
    if (p) p.classList.add('sel');
    var d = districtById[s.district];
    if (d) d.__el.classList.add('on');

    sel = { kind: 'subject', id: s.iso };
    cardKicker.textContent = 'Субъект федерации';
    cardTitle.textContent = s.name;
    cardSub.textContent = d ? 'Входит в ' + d.full : '';
    cardBody.innerHTML = d
      ? '<p>На схеме крупных регионов это <b>' + d.name.replace('\n', ' ') + '</b>.</p>'
      : '';
    card.hidden = false;
    hideHint();
    setHash(s.iso);
    placeCard(p);
  }

  function selectDistrict(id) {
    var d = districtById[id];
    if (!d) return;
    clearSel();
    var members = D.subjects.filter(function (s) { return s.district === id; });
    members.forEach(function (s) {
      if (subjEls[s.iso]) subjEls[s.iso].classList.add('sel');
    });
    d.__el.classList.add('on');

    sel = { kind: 'district', id: id };
    cardKicker.textContent = 'Крупный регион';
    cardTitle.textContent = d.name.replace('\n', ' ');
    cardSub.textContent = d.full;
    cardBody.innerHTML =
      '<p>' + members.length + ' субъектов:</p><div class="chips">' +
      members.map(function (s) {
        return '<button type="button" class="chip" data-iso="' + s.iso + '">' + s.name + '</button>';
      }).join('') + '</div>';
    card.hidden = false;
    hideHint();
    setHash(id);
    placeCard(d.__el);
  }

  cardBody.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('.chip') : null;
    if (!b) return;
    var s = null;
    for (var i = 0; i < D.subjects.length; i++) {
      if (D.subjects[i].iso === b.getAttribute('data-iso')) { s = D.subjects[i]; break; }
    }
    if (s) selectSubject(s);
  });

  closeBtn.addEventListener('click', clearSel);

  /* ---------- наведение ---------- */
  svg.addEventListener('pointerover', function (e) {
    var p = e.target.closest ? e.target.closest('.subj') : null;
    if (!p) return;
    hideTip();
    clearDistrictHover();
    hoveredEl = p;
    var s = p.__data;

    if (mode === 'district') {
      hoverDistrict(s.district);
      var cnt = D.subjects.filter(function (x) { return x.district === s.district; }).length;
      showTip('<b>' + districtName(s.district) + '</b><span>' + cnt + ' субъектов</span>', e);
    } else {
      p.classList.add('hover');
      showTip('<b>' + s.name + '</b><span>' + districtName(s.district) + '</span>', e);
    }
  });

  svg.addEventListener('pointerout', function (e) {
    var p = e.target.closest ? e.target.closest('.subj') : null;
    if (!p) return;
    p.classList.remove('hover');
    hoveredEl = null;
    hideTip();
    if (mode === 'district') clearDistrictHover();
  });

  svg.addEventListener('pointermove', function (e) {
    if (hoveredEl) moveTip(e);
  });

  /* ---------- выбор ---------- */
  svg.addEventListener('click', function (e) {
    var p = e.target.closest ? e.target.closest('.subj') : null;
    if (!p) { clearSel(); return; }
    var s = p.__data;
    if (mode === 'district') selectDistrict(s.district);
    else selectSubject(s);
  });

  gSubj.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    var p = e.target.closest ? e.target.closest('.subj') : null;
    if (!p) return;
    e.preventDefault();
    if (mode === 'district') selectDistrict(p.__data.district);
    else selectSubject(p.__data);
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { clearSel(); qInput.blur(); }
  });

  /* ---------- поиск ---------- */
  function clearSearch() {
    var all = gSubj.querySelectorAll('.subj');
    for (var i = 0; i < all.length; i++) {
      all[i].classList.remove('match');
      all[i].classList.remove('dim');
    }
    hits.textContent = '';
  }

  qInput.addEventListener('input', function () {
    var q = qInput.value.trim().toLowerCase();
    if (!q) { clearSearch(); return; }
    var n = 0;
    var all = gSubj.querySelectorAll('.subj');
    for (var i = 0; i < all.length; i++) {
      var ok = all[i].__data.name.toLowerCase().indexOf(q) !== -1;
      all[i].classList.toggle('match', ok);
      all[i].classList.toggle('dim', !ok);
      if (ok) n++;
    }
    hits.textContent = n ? n + ' найдено' : 'не найдено';
  });

  qInput.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter') return;
    var all = gSubj.querySelectorAll('.subj.match');
    if (all.length) {
      if (mode === 'district') selectDistrict(all[0].__data.district);
      else selectSubject(all[0].__data);
      all[0].focus();
    }
  });

  /* ---------- режимы и слои ---------- */
  var modeBtns = document.querySelectorAll('.modes button');
  Array.prototype.forEach.call(modeBtns, function (b) {
    b.addEventListener('click', function () {
      mode = b.getAttribute('data-mode');
      Array.prototype.forEach.call(modeBtns, function (x) {
        var on = x === b;
        x.classList.toggle('on', on);
        x.setAttribute('aria-pressed', String(on));
      });
      clearSel();
      clearDistrictHover();
      hideTip();
    });
  });

  labelsToggle.addEventListener('change', function () {
    gLabels.classList.toggle('off', !labelsToggle.checked);
  });
  waterToggle.addEventListener('change', function () {
    gWater.classList.toggle('off', !waterToggle.checked);
  });

  /* ---------- ссылка на конкретный регион: index.html#RU-KO ---------- */
  function applyHash() {
    var h = '';
    try { h = decodeURIComponent(location.hash.replace(/^#/, '')); } catch (err) { h = ''; }
    if (!h) return false;
    if (subjEls[h]) {
      for (var i = 0; i < D.subjects.length; i++) {
        if (D.subjects[i].iso === h) { selectSubject(D.subjects[i]); return true; }
      }
    }
    if (districtById[h]) { selectDistrict(h); return true; }
    return false;
  }
  applyHash();
  window.addEventListener('hashchange', applyHash);

  /* на вертикальном телефоне карта шире экрана — показываем середину страны */
  var stage = document.querySelector('.stage');
  function centerStage() {
    if (stage && stage.scrollWidth > stage.clientWidth + 4) {
      stage.scrollLeft = (stage.scrollWidth - stage.clientWidth) / 2;
    }
  }
  centerStage();
  window.addEventListener('load', centerStage);
  window.addEventListener('orientationchange', function () { setTimeout(centerStage, 250); });

  /* ---------- во весь экран ---------- */
  var fsBtn = document.getElementById('fs');

  function fsElement() {
    return document.fullscreenElement || document.webkitFullscreenElement || null;
  }
  function fsRequest(el) {
    var fn = el.requestFullscreen || el.webkitRequestFullscreen;
    if (!fn) return Promise.reject(new Error('unsupported'));
    try {
      var p = fn.call(el);
      return p && p.then ? p : Promise.resolve();
    } catch (e) {
      return Promise.reject(e);
    }
  }
  function fsExit() {
    var fn = document.exitFullscreen || document.webkitExitFullscreen;
    if (fn) fn.call(document);
  }

  if (fsBtn && fsRequest && (document.getElementById('map'))) {
    fsBtn.addEventListener('click', function () {
      if (fsElement()) { fsExit(); return; }
      if (document.body.classList.contains('focus')) {
        document.body.classList.remove('focus');
        return;
      }
      fsRequest(document.documentElement).catch(function () {
        // браузер не дал полноэкранный режим — просто прячем шапку и подвал
        document.body.classList.add('focus');
      });
    });
  }
})();


