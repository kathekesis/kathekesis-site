// Kathekésis: área do aluno (cadastro, login, materiais e cursos) com Firebase.
(function () {
  var app = document.getElementById('membros-app');
  if (!app) return;
  var cfg = JSON.parse(document.getElementById('fb-config').textContent || 'null');
  var ehAdmin = app.dataset.pagina === 'admin';

  function $(sel, el) { return (el || document).querySelector(sel); }
  function mostrar(id) {
    app.querySelectorAll('[data-view]').forEach(function (v) { v.hidden = v.dataset.view !== id; });
  }
  function el(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  }
  function aviso(alvo, msg, tipo) {
    alvo.textContent = msg || '';
    alvo.className = 'm-aviso' + (tipo ? ' ' + tipo : '');
  }

  if (!cfg || !cfg.apiKey || typeof firebase === 'undefined') { mostrar('breve'); return; }

  firebase.initializeApp(cfg);
  var auth = firebase.auth();
  var db = firebase.firestore();
  auth.languageCode = 'pt';
  var ts = firebase.firestore.FieldValue.serverTimestamp;

  var ERROS = {
    'auth/email-already-in-use': 'Já existe uma conta com este e-mail. Use a aba "Entrar".',
    'auth/invalid-email': 'Este e-mail não parece válido. Confira e tente de novo.',
    'auth/weak-password': 'A senha precisa ter pelo menos 8 caracteres.',
    'auth/invalid-credential': 'E-mail ou senha incorretos.',
    'auth/wrong-password': 'E-mail ou senha incorretos.',
    'auth/user-not-found': 'Não encontramos uma conta com este e-mail. Crie sua conta na aba "Criar conta".',
    'auth/too-many-requests': 'Muitas tentativas seguidas. Espere alguns minutos e tente de novo.',
    'auth/popup-closed-by-user': 'A janela do Google foi fechada antes de terminar. Tente de novo.',
    'auth/popup-blocked': 'O navegador bloqueou a janela do Google. Permita pop-ups para este site e tente de novo.',
    'auth/network-request-failed': 'Sem conexão com a internet. Verifique e tente de novo.',
    'permission-denied': 'Você não tem permissão para isso.'
  };
  function erro(e) { return ERROS[e.code] || ('Algo deu errado (' + (e.code || e.message) + '). Tente de novo.'); }

  // ---------------------------------------------------------------- Cadastro e login
  var tabs = app.querySelectorAll('.m-tab');
  tabs.forEach(function (t) {
    t.addEventListener('click', function () {
      tabs.forEach(function (x) { x.setAttribute('aria-selected', x === t); });
      $('#form-cadastro').hidden = t.dataset.tab !== 'cadastro';
      $('#form-entrar').hidden = t.dataset.tab !== 'entrar';
    });
  });

  function salvarMembro(user, extra) {
    var ref = db.collection('membros').doc(user.uid);
    return ref.get().then(function (doc) {
      var dados = { nome: user.displayName || (extra && extra.nome) || '', email: user.email, ultimoAcesso: ts() };
      if (!doc.exists) {
        dados.criadoEm = ts();
        dados.consentimento = true;
        dados.novidades = !!(extra && extra.novidades);
      }
      return ref.set(dados, { merge: true });
    });
  }

  var fc = $('#form-cadastro');
  if (fc) fc.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var msg = $('#cad-msg');
    if (!$('#cad-aceite').checked) { aviso(msg, 'Para criar a conta, marque que leu e aceita a Política de Privacidade.', 'erro'); return; }
    var nome = $('#cad-nome').value.trim();
    var senha = $('#cad-senha').value;
    if (senha.length < 8) { aviso(msg, ERROS['auth/weak-password'], 'erro'); return; }
    aviso(msg, 'Criando sua conta…');
    auth.createUserWithEmailAndPassword($('#cad-email').value.trim(), senha)
      .then(function (r) {
        return r.user.updateProfile({ displayName: nome })
          .then(function () { return salvarMembro(r.user, { nome: nome, novidades: $('#cad-novidades').checked }); })
          .then(function () { return r.user.sendEmailVerification().catch(function () {}); });
      })
      .catch(function (e) { aviso(msg, erro(e), 'erro'); });
  });

  var fe = $('#form-entrar');
  if (fe) fe.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var msg = $('#ent-msg');
    aviso(msg, 'Entrando…');
    auth.signInWithEmailAndPassword($('#ent-email').value.trim(), $('#ent-senha').value)
      .catch(function (e) { aviso(msg, erro(e), 'erro'); });
  });

  var esqueci = $('#ent-esqueci');
  if (esqueci) esqueci.addEventListener('click', function () {
    var msg = $('#ent-msg');
    var email = $('#ent-email').value.trim();
    if (!email) { aviso(msg, 'Digite seu e-mail no campo acima e clique de novo em "Esqueci minha senha".', 'erro'); return; }
    auth.sendPasswordResetEmail(email)
      .then(function () { aviso(msg, 'Enviamos um link para criar uma nova senha. Confira seu e-mail, inclusive a caixa de spam.', 'ok'); })
      .catch(function (e) { aviso(msg, erro(e), 'erro'); });
  });

  app.querySelectorAll('.m-google').forEach(function (b) {
    b.addEventListener('click', function () {
      var msg = $(b.dataset.msg);
      var aceite = b.dataset.aceite ? $(b.dataset.aceite) : null;
      if (aceite && !aceite.checked) { aviso(msg, 'Para criar a conta, marque que leu e aceita a Política de Privacidade.', 'erro'); return; }
      var novidades = b.dataset.novidades ? $(b.dataset.novidades).checked : false;
      auth.signInWithPopup(new firebase.auth.GoogleAuthProvider())
        .then(function (r) { return salvarMembro(r.user, { novidades: novidades }); })
        .catch(function (e) { aviso(msg, erro(e), 'erro'); });
    });
  });

  app.querySelectorAll('.m-sair').forEach(function (b) {
    b.addEventListener('click', function () { auth.signOut(); });
  });

  // ---------------------------------------------------------------- Painel do aluno
  function youtubeId(txt) {
    var m = String(txt || '').match(/(?:youtu\.be\/|v=|shorts\/|embed\/)([A-Za-z0-9_-]{11})/);
    if (m) return m[1];
    return /^[A-Za-z0-9_-]{11}$/.test(txt || '') ? txt : null;
  }
  function paragrafos(alvo, texto) {
    String(texto || '').split(/\n\s*\n/).forEach(function (p) {
      if (p.trim()) alvo.append(el('p', null, p.trim()));
    });
  }

  function carregarMateriais() {
    var lista = $('#lista-materiais');
    lista.textContent = '';
    return db.collection('materiais').orderBy('ordem').get().then(function (snap) {
      if (snap.empty) { lista.append(el('p', 'm-vazio', 'Os primeiros materiais estão sendo preparados. Volte em breve.')); return; }
      snap.forEach(function (d) {
        var m = d.data();
        var a = el('a', 'm-material');
        a.href = m.link; a.target = '_blank'; a.rel = 'noopener';
        a.append(el('span', 'm-tipo', m.tipo || 'Material'));
        a.append(el('b', null, m.titulo));
        if (m.descricao) a.append(el('span', 'm-desc', m.descricao));
        a.append(el('span', 'm-acao', 'Baixar ou abrir →'));
        lista.append(a);
      });
    });
  }

  var progresso = {};
  function carregarCursos(uid) {
    var lista = $('#lista-cursos');
    lista.textContent = '';
    return db.collection('membros').doc(uid).collection('progresso').get().then(function (ps) {
      progresso = {};
      ps.forEach(function (p) { progresso[p.id] = p.data().aulas || []; });
      return db.collection('cursos').orderBy('ordem').get();
    }).then(function (snap) {
      if (snap.empty) { lista.append(el('p', 'm-vazio', 'O primeiro curso está sendo preparado. Volte em breve.')); return; }
      snap.forEach(function (d) {
        var c = d.data();
        var b = el('button', 'm-curso');
        b.type = 'button';
        b.append(el('b', null, c.titulo));
        if (c.descricao) b.append(el('span', 'm-desc', c.descricao));
        var feitas = (progresso[d.id] || []).length;
        b.append(el('span', 'm-acao', feitas ? feitas + ' aula(s) concluída(s) · continuar →' : 'Começar o curso →'));
        b.addEventListener('click', function () { abrirCurso(uid, d.id, c); });
        lista.append(b);
      });
    });
  }

  function abrirCurso(uid, cursoId, curso) {
    mostrar('curso');
    window.scrollTo(0, 0);
    $('#curso-titulo').textContent = curso.titulo;
    var nav = $('#curso-aulas'), corpo = $('#curso-aula');
    nav.textContent = ''; corpo.textContent = '';
    db.collection('cursos').doc(cursoId).collection('aulas').orderBy('ordem').get().then(function (snap) {
      var aulas = [];
      snap.forEach(function (d) { aulas.push({ id: d.id, dados: d.data() }); });
      if (!aulas.length) { corpo.append(el('p', 'm-vazio', 'As aulas deste curso ainda estão sendo preparadas.')); return; }
      function abrirAula(i) {
        var a = aulas[i], feitas = progresso[cursoId] || [];
        nav.querySelectorAll('button').forEach(function (b, j) { b.setAttribute('aria-current', j === i); });
        corpo.textContent = '';
        corpo.append(el('div', 'eyebrow', 'aula ' + (i + 1) + ' de ' + aulas.length));
        corpo.append(el('h2', null, a.dados.titulo));
        var vid = youtubeId(a.dados.video);
        if (vid) {
          var f = el('div', 'm-video');
          var ifr = document.createElement('iframe');
          ifr.src = 'https://www.youtube-nocookie.com/embed/' + vid;
          ifr.title = a.dados.titulo; ifr.allowFullscreen = true;
          ifr.allow = 'accelerometer; encrypted-media; gyroscope; picture-in-picture';
          f.append(ifr); corpo.append(f);
        }
        var t = el('div', 'prose'); paragrafos(t, a.dados.texto); corpo.append(t);
        if (a.dados.material) {
          var lk = el('a', 'btn btn-ghost-dark', 'Material da aula →');
          lk.href = a.dados.material; lk.target = '_blank'; lk.rel = 'noopener';
          corpo.append(lk);
        }
        var acoes = el('div', 'm-aula-acoes');
        var feito = feitas.indexOf(a.id) >= 0;
        var bt = el('button', 'btn ' + (feito ? 'btn-ghost-dark' : 'btn-lapis'), feito ? 'Aula concluída ✓' : 'Marcar como concluída');
        bt.type = 'button';
        bt.addEventListener('click', function () {
          db.collection('membros').doc(uid).collection('progresso').doc(cursoId)
            .set({ aulas: firebase.firestore.FieldValue.arrayUnion(a.id), atualizado: ts() }, { merge: true })
            .then(function () {
              progresso[cursoId] = (progresso[cursoId] || []).concat([a.id]);
              montarNav(); if (i + 1 < aulas.length) abrirAula(i + 1); else abrirAula(i);
            });
        });
        acoes.append(bt);
        if (i + 1 < aulas.length) {
          var prox = el('button', 'btn btn-ghost-dark', 'Próxima aula →');
          prox.type = 'button'; prox.addEventListener('click', function () { abrirAula(i + 1); });
          acoes.append(prox);
        }
        corpo.append(acoes);
      }
      function montarNav() {
        nav.textContent = '';
        var feitas = progresso[cursoId] || [];
        aulas.forEach(function (a, i) {
          var b = el('button', 'm-aula-item');
          b.type = 'button';
          b.append(el('span', 'm-num', feitas.indexOf(a.id) >= 0 ? '✓' : String(i + 1)));
          b.append(el('span', null, a.dados.titulo));
          b.addEventListener('click', function () { abrirAula(i); window.scrollTo(0, 0); });
          nav.append(b);
        });
      }
      montarNav();
      var primeira = aulas.findIndex(function (a) { return (progresso[cursoId] || []).indexOf(a.id) < 0; });
      abrirAula(primeira < 0 ? 0 : primeira);
    });
  }
  var voltar = $('#curso-voltar');
  if (voltar) voltar.addEventListener('click', function () {
    mostrar('painel');
    if (auth.currentUser) carregarCursos(auth.currentUser.uid);
  });

  // ---------------------------------------------------------------- Administração
  function linhaAdmin(titulo, sub, aoApagar) {
    var r = el('div', 'a-linha');
    var t = el('div'); t.append(el('b', null, titulo)); if (sub) t.append(el('span', 'm-desc', sub));
    var bt = el('button', 'a-apagar', 'Apagar'); bt.type = 'button';
    bt.addEventListener('click', function () {
      if (bt.dataset.confirma) { aoApagar(); return; }
      bt.dataset.confirma = '1'; bt.textContent = 'Confirmar exclusão';
      setTimeout(function () { delete bt.dataset.confirma; bt.textContent = 'Apagar'; }, 4000);
    });
    r.append(t, bt); return r;
  }
  function adminMateriais() {
    var l = $('#a-materiais'); l.textContent = '';
    db.collection('materiais').orderBy('ordem').get().then(function (s) {
      if (s.empty) l.append(el('p', 'm-vazio', 'Nenhum material ainda.'));
      s.forEach(function (d) {
        var m = d.data();
        l.append(linhaAdmin(m.ordem + '. ' + m.titulo, (m.tipo || '') + ' · ' + m.link, function () { d.ref.delete().then(adminMateriais); }));
      });
    });
  }
  var cursoSel = null;
  function adminCursos() {
    var l = $('#a-cursos'), sel = $('#a-aula-curso'); l.textContent = ''; sel.textContent = '';
    db.collection('cursos').orderBy('ordem').get().then(function (s) {
      if (s.empty) l.append(el('p', 'm-vazio', 'Nenhum curso ainda.'));
      s.forEach(function (d) {
        var c = d.data();
        l.append(linhaAdmin(c.ordem + '. ' + c.titulo, c.descricao, function () { d.ref.delete().then(adminCursos); }));
        var o = el('option', null, c.titulo); o.value = d.id; sel.append(o);
      });
      cursoSel = sel.value || null; adminAulas();
    });
  }
  function adminAulas() {
    var l = $('#a-aulas'); l.textContent = '';
    if (!cursoSel) { l.append(el('p', 'm-vazio', 'Crie um curso primeiro.')); return; }
    db.collection('cursos').doc(cursoSel).collection('aulas').orderBy('ordem').get().then(function (s) {
      if (s.empty) l.append(el('p', 'm-vazio', 'Nenhuma aula neste curso ainda.'));
      s.forEach(function (d) {
        var a = d.data();
        l.append(linhaAdmin(a.ordem + '. ' + a.titulo, a.video ? 'vídeo: ' + a.video : 'sem vídeo', function () { d.ref.delete().then(adminAulas); }));
      });
    });
  }
  function adminMembros() {
    db.collection('membros').orderBy('criadoEm', 'desc').get().then(function (s) {
      var l = $('#a-membros'); l.textContent = '';
      var emails = [];
      $('#a-total').textContent = s.size + (s.size === 1 ? ' pessoa cadastrada' : ' pessoas cadastradas');
      s.forEach(function (d) {
        var m = d.data();
        var quando = m.criadoEm ? m.criadoEm.toDate().toLocaleDateString('pt-BR') : '';
        var r = el('div', 'a-linha');
        var t = el('div'); t.append(el('b', null, m.nome || '(sem nome)'));
        t.append(el('span', 'm-desc', m.email + ' · ' + quando + (m.novidades ? ' · aceita novidades' : '')));
        r.append(t); l.append(r);
        if (m.novidades) emails.push(m.email);
      });
      var b = $('#a-copiar');
      b.onclick = function () {
        var txt = emails.join(', ');
        var out = $('#a-copiar-msg');
        navigator.clipboard.writeText(txt).then(function () {
          aviso(out, emails.length + ' e-mail(s) copiados.', 'ok');
        }).catch(function () { aviso(out, txt || 'Ninguém aceitou receber novidades ainda.', ''); });
      };
    });
  }
  function form(id, fn) {
    var f = $(id); if (!f) return;
    f.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var msg = f.querySelector('.m-aviso');
      fn(f).then(function () { f.reset(); aviso(msg, 'Salvo.', 'ok'); })
        .catch(function (e) { aviso(msg, erro(e), 'erro'); });
    });
  }
  function num(v) { var n = parseInt(v, 10); return isNaN(n) ? 999 : n; }
  if (ehAdmin) {
    form('#f-material', function (f) {
      return db.collection('materiais').add({ titulo: f.titulo.value.trim(), descricao: f.descricao.value.trim(), tipo: f.tipo.value, link: f.link.value.trim(), ordem: num(f.ordem.value), criadoEm: ts() }).then(adminMateriais);
    });
    form('#f-curso', function (f) {
      return db.collection('cursos').add({ titulo: f.titulo.value.trim(), descricao: f.descricao.value.trim(), ordem: num(f.ordem.value), criadoEm: ts() }).then(adminCursos);
    });
    form('#f-aula', function (f) {
      if (!cursoSel) return Promise.reject({ message: 'Crie um curso primeiro.' });
      var v = f.video.value.trim();
      if (v && !youtubeId(v)) return Promise.reject({ message: 'Não reconheci o link do YouTube.' });
      return db.collection('cursos').doc(cursoSel).collection('aulas').add({ titulo: f.titulo.value.trim(), video: v ? youtubeId(v) : '', texto: f.texto.value, material: f.material.value.trim(), ordem: num(f.ordem.value), criadoEm: ts() }).then(adminAulas);
    });
    $('#a-aula-curso').addEventListener('change', function (e) { cursoSel = e.target.value; adminAulas(); });
  }

  // ---------------------------------------------------------------- Estado da sessão
  auth.onAuthStateChanged(function (user) {
    if (!user) { mostrar('entrar'); return; }
    app.querySelectorAll('.m-nome').forEach(function (n) { n.textContent = (user.displayName || user.email).split(' ')[0]; });
    if (ehAdmin) {
      db.collection('admin').doc('acesso').get().then(function () {
        mostrar('admin'); adminMateriais(); adminCursos(); adminMembros();
      }).catch(function () { mostrar('negado'); });
      return;
    }
    mostrar('painel');
    salvarMembro(user).catch(function () {});
    carregarMateriais().catch(function (e) { aviso($('#painel-msg'), erro(e), 'erro'); });
    carregarCursos(user.uid).catch(function (e) { aviso($('#painel-msg'), erro(e), 'erro'); });
  });
})();
