// Kathekésis: filtros dos artigos e guia do Catecismo.
(function () {
  // ---- Artigos (página inicial)
  var list = document.getElementById('art-list');
  var chips = document.getElementById('chips');
  if (list && chips) {
    var cards = Array.prototype.slice.call(list.querySelectorAll('.art'));
    var q = document.getElementById('art-search');
    var more = document.getElementById('art-more');
    var empty = document.getElementById('art-empty');
    var tema = 'Todos', limite = 12;
    var norm = function (t) { return t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); };
    cards.forEach(function (c) { c._txt = norm(c.textContent); });
    function render() {
      var termo = norm(q.value.trim());
      var ok = cards.filter(function (c) {
        return (tema === 'Todos' || c.dataset.tema === tema) && (!termo || c._txt.indexOf(termo) >= 0);
      });
      cards.forEach(function (c) { c.hidden = true; });
      ok.slice(0, limite).forEach(function (c) { c.hidden = false; });
      empty.hidden = ok.length > 0;
      more.hidden = ok.length <= limite;
      more.textContent = 'Mostrar mais artigos (' + (ok.length - limite) + ')';
    }
    chips.addEventListener('click', function (e) {
      var b = e.target.closest('.chip');
      if (!b) return;
      tema = b.dataset.tema; limite = 12;
      chips.querySelectorAll('.chip').forEach(function (x) { x.setAttribute('aria-pressed', x === b); });
      render();
    });
    q.addEventListener('input', function () { limite = 12; render(); });
    more.addEventListener('click', function () { limite += 12; render(); });
    render();
  }

  // ---- Catecismo
  var idxEl = document.getElementById('cat-index');
  if (idxEl) {
    var IDX = JSON.parse(idxEl.textContent);
    var modo = 'cic';
    var tC = document.getElementById('tab-cic'), tK = document.getElementById('tab-comp');
    var pC = document.getElementById('painel-cic'), pK = document.getElementById('painel-comp');
    var jn = document.getElementById('jump-n'), out = document.getElementById('jump-out');
    var lede = document.getElementById('cat-lede');
    var fmt = function (n) { return n.toLocaleString('pt-BR'); };
    function setModo(m) {
      modo = m;
      tC.setAttribute('aria-selected', m === 'cic'); tK.setAttribute('aria-selected', m === 'comp');
      pC.hidden = m !== 'cic'; pK.hidden = m !== 'comp';
      document.getElementById('cat-h1').textContent = m === 'cic' ? 'Catecismo da Igreja Católica' : 'Compêndio do Catecismo';
      lede.textContent = m === 'cic' ? lede.dataset.cic : lede.dataset.comp;
      document.getElementById('jump-label').textContent = m === 'cic' ? 'Ir para o parágrafo §' : 'Ir para a pergunta nº';
      jn.max = m === 'cic' ? 2865 : 598; jn.placeholder = m === 'cic' ? 'ex.: 1213' : 'ex.: 252';
      jn.value = ''; out.textContent = '';
    }
    tC.addEventListener('click', function () { setModo('cic'); });
    tK.addEventListener('click', function () { setModo('comp'); });
    function link(item) {
      var a = document.createElement('a');
      a.href = item.u; a.target = '_blank'; a.rel = 'noopener'; a.className = 'ext'; a.textContent = item.t;
      return a;
    }
    document.getElementById('jump').addEventListener('submit', function (e) {
      e.preventDefault();
      var n = parseInt(jn.value, 10), max = modo === 'cic' ? 2865 : 598;
      out.textContent = '';
      if (!(n >= 1 && n <= max)) { out.textContent = 'Digite um número de 1 a ' + fmt(max) + '.'; return; }
      var lista = modo === 'cic' ? IDX.cic : IDX.comp, hit = null;
      for (var i = 0; i < lista.length; i++) { if (n >= lista[i].a0 && n <= lista[i].a1) { hit = lista[i]; break; } }
      if (!hit && modo === 'cic' && n === 26) hit = IDX.cic[1];
      if (!hit && modo === 'comp') hit = { t: 'Introdução', u: IDX.intro };
      if (!hit) { out.textContent = 'Não encontrei esse número.'; return; }
      out.append(modo === 'cic' ? 'O § ' + fmt(n) + ' está em ' + (hit.p ? hit.p + ' · ' : '') : 'A pergunta ' + n + ' está em ');
      out.append(link(hit));
    });
  }
})();
