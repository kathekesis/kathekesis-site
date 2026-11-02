#!/usr/bin/env python3
"""Gera o site do Kathekésis na pasta _site/.

Busca os vídeos mais recentes do canal (feed público do YouTube) e os artigos
do Via Católica (API pública do WordPress). Se alguma busca falhar, usa a
última cópia salva em data/cache/, para o site nunca sair do ar por isso.

Uso:  python build.py            (busca tudo e gera o site)
      python build.py --offline  (usa só as cópias salvas)
"""
import datetime
import html
import json
import re
import shutil
import sys
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CACHE = DATA / "cache"
OUT = ROOT / "_site"
OFFLINE = "--offline" in sys.argv

CFG = json.loads((DATA / "config.json").read_text(encoding="utf-8"))
SITE = CFG["site_url"].rstrip("/")
BASE = CFG.get("base_path", "").rstrip("/")
UA = "KathekesisSite/1.0 (+%s)" % SITE

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESES_LONGOS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
                "agosto", "setembro", "outubro", "novembro", "dezembro"]
TEMAS = {
    "aparicoes-de-nossa-senhora": "Nossa Senhora",
    "historia-da-igreja": "História da Igreja",
    "historia-das-heresias": "Heresias",
    "milagres": "Milagres",
    "oracoes-catolicas": "Orações",
    "protestantismo": "Apologética",
    "sagrada-escritura-e-doutrina": "Escritura e doutrina",
    "artigos": "Escritura e doutrina",
}
ORDEM_TEMAS = ["História da Igreja", "Heresias", "Milagres", "Orações", "Nossa Senhora",
               "Escritura e doutrina", "Apologética", "Outros"]


def u(path):
    """Endereço interno do site, respeitando o base_path."""
    return BASE + path


def esc(t):
    return html.escape(str(t), quote=True)


def baixar(url, accept="*/*"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept,
                                               "Accept-Language": "pt-BR,pt;q=0.9"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace"), dict(r.headers)


def com_cache(nome, buscar):
    arq = CACHE / (nome + ".json")
    if not OFFLINE:
        try:
            dados = buscar()
            CACHE.mkdir(parents=True, exist_ok=True)
            arq.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"[ok] {nome}: dados novos")
            return dados
        except Exception as e:  # noqa: BLE001
            print(f"[aviso] {nome}: não consegui buscar ({e}); usando a cópia salva")
    return json.loads(arq.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- YouTube

def buscar_videos():
    xml, _ = baixar("https://www.youtube.com/feeds/videos.xml?channel_id=" + CFG["canal_id"])
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
          "m": "http://search.yahoo.com/mrss/"}
    raiz = ET.fromstring(xml)
    vids = []
    for e in raiz.findall("a:entry", ns):
        stats = e.find("m:group/m:community/m:statistics", ns)
        vids.append({
            "id": e.findtext("yt:videoId", namespaces=ns),
            "titulo": e.findtext("a:title", namespaces=ns),
            "publicado": e.findtext("a:published", namespaces=ns),
            "views": int(stats.get("views", 0)) if stats is not None else 0,
        })
    if not vids:
        raise ValueError("feed vazio")
    return vids


def buscar_numeros():
    pg, _ = baixar(CFG["canal_url"] + "/videos")
    insc = re.search(r"([\d.,]+(?:\s*mil)?)\s+inscritos", pg)
    vids = re.search(r"([\d.]+)\s+vídeos", pg)
    if not insc or not vids:
        raise ValueError("números não encontrados na página do canal")
    return {"inscritos": re.sub(r"\s+", " ", insc.group(1)), "videos": vids.group(1)}


def limpar_titulo(t):
    t = re.sub(r"\s#\S+", "", t).strip()
    nome = re.split(r"\s+[-–‐]\s+", t)[0].strip()
    return nome or t


def dia_festa(v):
    m = re.search(r"(\d{1,2})\s+de\s+(\w+)", v["titulo"], re.I)
    if m:
        mes = m.group(2).lower()
        for i, nome in enumerate(MESES_LONGOS):
            if mes.startswith(nome[:4]):
                return f"{int(m.group(1))} {MESES[i]}"
    d = datetime.date.fromisoformat(v["publicado"][:10])
    return f"{d.day} {MESES[d.month - 1]}"


def fmt_views(n):
    if n >= 1000:
        return (f"{n / 1000:.1f}".replace(".", ",").replace(",0", "")) + " mil visualizações"
    return f"{n} visualização" if n == 1 else f"{n} visualizações"


def capa(vid):
    return f"https://i.ytimg.com/vi/{vid}/hq720.jpg"


# ---------------------------------------------------------------- Via Católica

KEEP = {"p", "h2", "h3", "h4", "ul", "ol", "li", "strong", "em", "br", "blockquote", "a",
        "details", "summary", "sup", "mark", "table", "thead", "tbody", "tr", "th", "td"}
REN = {"h1": "h2", "h5": "h4", "h6": "h4", "b": "strong", "i": "em"}
DROP = {"script", "style", "svg", "iframe", "noscript", "figure", "figcaption", "form", "button"}


class Limpador(HTMLParser):
    def __init__(self, internos):
        super().__init__(convert_charrefs=True)
        self.o, self.pilha, self.pula, self.internos = [], [], 0, internos

    def handle_starttag(self, t, a):
        if t in DROP:
            self.pula += 1
            return
        if self.pula or t == "img":
            return
        t = REN.get(t, t)
        if t not in KEEP:
            self.pilha.append(None)
            return
        if t == "a":
            h = dict(a).get("href") or ""
            k = h.split("#")[0].rstrip("/")
            if k in self.internos:
                self.o.append('<a href="%s">' % u("/artigos/%s/" % self.internos[k]))
            elif h.startswith("http"):
                self.o.append('<a href="%s" target="_blank" rel="noopener">' % esc(h))
            else:
                self.pilha.append(None)
                return
            self.pilha.append("a")
            return
        self.o.append("<%s>" % t)
        if t != "br":
            self.pilha.append(t)

    def handle_endtag(self, t):
        if t in DROP:
            self.pula = max(0, self.pula - 1)
            return
        if self.pula or t in ("img", "br"):
            return
        if self.pilha:
            x = self.pilha.pop()
            if x:
                self.o.append("</%s>" % x)

    def handle_data(self, d):
        if not self.pula:
            self.o.append(html.escape(d, quote=False))


def buscar_artigos():
    base = CFG["via_catolica"].rstrip("/") + "/wp-json/wp/v2/posts"
    campos = "id,slug,date,modified,link,title,content,excerpt"
    posts, pagina, total = [], 1, 1
    while pagina <= total:
        txt, hdr = baixar(f"{base}?per_page=50&page={pagina}&_fields={campos}", "application/json")
        total = int({k.lower(): v for k, v in hdr.items()}.get("x-wp-totalpages", 1))
        posts += json.loads(txt)
        pagina += 1
    if not posts:
        raise ValueError("nenhum artigo")
    internos = {p["link"].rstrip("/"): p["slug"] for p in posts}
    arts = []
    for p in posts:
        lim = Limpador(internos)
        lim.feed(p["content"]["rendered"])
        corpo = "".join(lim.o)
        corpo = re.sub(r"<(p|li|h[2-4]|strong|em)>\s*</\1>", "", corpo)
        corpo = re.sub(r"\n\s*\n+", "\n", corpo).strip()
        resumo = html.unescape(re.sub(r"<[^>]+>", "", p["excerpt"]["rendered"]))
        resumo = re.sub(r"\s*\[(…|&hellip;|\.\.\.)\]\s*$", "", resumo).strip()
        if len(resumo) > 170:
            resumo = resumo[:170].rsplit(" ", 1)[0] + "…"
        secao = p["link"].split("://", 1)[1].split("/")[1]
        arts.append({"slug": p["slug"], "titulo": html.unescape(p["title"]["rendered"]),
                     "data": p["date"][:10], "atualizado": p["modified"][:10],
                     "original": p["link"], "tema": TEMAS.get(secao, "Outros"),
                     "resumo": resumo, "corpo": corpo})
    arts.sort(key=lambda a: a["data"], reverse=True)
    return arts


# ---------------------------------------------------------------- Modelo de página

ICONES = """<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false">
  <symbol id="i-youtube" viewBox="0 0 24 24"><rect x="2" y="5" width="20" height="14" rx="4" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M10 9.2v5.6l4.8-2.8z" fill="currentColor"/></symbol>
  <symbol id="i-instagram" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="5" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="17.3" cy="6.7" r="1.2" fill="currentColor"/></symbol>
  <symbol id="i-tiktok" viewBox="0 0 24 24"><path d="M14 3v11.5a3.5 3.5 0 1 1-3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/><path d="M14 3c.4 2.6 2.2 4.4 5 4.6" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/></symbol>
  <symbol id="i-facebook" viewBox="0 0 24 24"><path d="M13.5 21v-7.5h2.6l.4-3h-3V8.7c0-.9.3-1.5 1.6-1.5h1.6V4.5c-.3 0-1.2-.1-2.3-.1-2.3 0-3.9 1.4-3.9 4V10.5H8v3h2.5V21z" fill="currentColor"/></symbol>
  <symbol id="i-play" viewBox="0 0 16 16"><path d="M4 2.5v11l9-5.5z" fill="currentColor"/></symbol>
</svg>"""

LOGO = """<svg viewBox="0 0 40 34" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round">
        <path d="M20 30 C15 27 9 26 4 27 V5 C9 4 15 5 20 8 C25 5 31 4 36 5 V27 C31 26 25 27 20 30 Z"/>
        <path d="M1.5 9 V30 C8 29 14 30 20 32.5 C26 30 32 29 38.5 30 V9"/>
        <g fill="currentColor" stroke="none"><rect x="18.6" y="7" width="2.8" height="21" rx="1"/><rect x="13" y="13" width="14" height="2.8" rx="1"/><circle cx="20" cy="7" r="2"/><circle cx="20" cy="28" r="2"/><circle cx="13" cy="14.4" r="2"/><circle cx="27" cy="14.4" r="2"/></g>
      </svg>"""

FAVICON = ("data:image/svg+xml," + urllib.request.quote(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40"><rect width="40" height="40" rx="8" fill="#11676A"/>'
    '<g transform="translate(0 3)" fill="none" stroke="#C4AF7A" stroke-width="1.8" stroke-linejoin="round">'
    '<path d="M20 30 C15 27 9 26 4 27 V5 C9 4 15 5 20 8 C25 5 31 4 36 5 V27 C31 26 25 27 20 30 Z"/>'
    '<g fill="#C4AF7A" stroke="none"><rect x="18.6" y="7" width="2.8" height="21"/><rect x="13" y="13" width="14" height="2.8"/></g></g></svg>'))


def icone(rede, cls="icon"):
    return f'<svg class="{cls}" aria-hidden="true"><use href="#i-{rede}"/></svg>'


def cabecalho():
    itens = [("Vídeos", "/#videos"), ("Formação", "/#formacao"), ("Artigos", "/#artigos"),
             ("Catecismo", "/catecismo/"), ("Livraria", "/#livraria"), ("Sobre", "/#sobre")]
    nav = "\n".join(f'        <li><a href="{u(h)}">{t}</a></li>' for t, h in itens)
    return f"""<header class="top">
  <div class="wrap">
    <a class="brand" href="{u('/')}">
      {LOGO}
      Kathekésis
    </a>
    <nav aria-label="Principal">
      <ul>
{nav}
      </ul>
    </nav>
  </div>
</header>"""


def rodape():
    redes = "".join(f'<a href="{esc(r["url"])}" target="_blank" rel="noopener" aria-label="{esc(r["nome"])}">{icone(r["rede"])}</a>'
                    for r in CFG["redes"])
    ano = datetime.date.today().year
    return f"""<footer>
  <div class="wrap">
    <div>© {ano} Kathekésis</div>
    <div class="foot-social">{redes}</div>
    <ul>
      <li><a href="{u('/catecismo/')}">Catecismo</a></li>
      <li><a href="{u('/#artigos')}">Artigos</a></li>
      <li><a href="{u('/#livraria')}">Livraria</a></li>
      <li><a href="{u('/#sobre')}">Sobre</a></li>
    </ul>
  </div>
</footer>"""


def pagina(titulo, descricao, caminho, corpo, canonical=None, extra=""):
    url = SITE + caminho
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(titulo)}</title>
<meta name="description" content="{esc(descricao)}">
<link rel="canonical" href="{esc(canonical or url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Kathekésis">
<meta property="og:title" content="{esc(titulo)}">
<meta property="og:description" content="{esc(descricao)}">
<meta property="og:url" content="{esc(url)}">
<meta name="theme-color" content="#0C4F52">
<link rel="icon" href="{FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Marcellus&family=Alegreya:ital,wght@0,400;0,500;0,700;1,400&family=Alegreya+Sans+SC:wght@500&family=Montserrat:wght@700&display=swap">
<link rel="stylesheet" href="{u('/assets/style.css')}">
{extra}</head>
<body>
{cabecalho()}
{ICONES}
{corpo}
{rodape()}
<script src="{u('/assets/site.js')}" defer></script>
</body>
</html>
"""


def card_video(v):
    return f"""        <a class="card" href="https://www.youtube.com/watch?v={esc(v['id'])}" target="_blank" rel="noopener">
          <img class="cover" src="{capa(v['id'])}" alt="" loading="lazy">
          <div class="day">{esc(dia_festa(v))}</div><div class="playwrap" aria-hidden="true"><span>{icone('play', 'pi')}</span></div>
          <h3>{esc(limpar_titulo(v['titulo']))}</h3><div class="meta">{fmt_views(v['views'])}</div>
        </a>"""


def card_artigo(a, extra_attrs=True, video=False):
    attrs = f' data-tema="{esc(a["tema"])}"' if extra_attrs else ""
    chamada = "Ler artigo · com vídeo →" if video else "Ler artigo →"
    return (f'        <a class="art" href="{u("/artigos/%s/" % a["slug"])}"{attrs}>'
            f'<div class="cat">{esc(a["tema"])}</div><h3>{esc(a["titulo"])}</h3>'
            f'<p>{esc(a["resumo"])}</p><span class="src">{chamada}</span></a>')


# ---------------------------------------------------------------- Páginas

def gerar_inicio(videos, numeros, artigos, vmap):
    recentes = videos[:6]
    ult = videos[0]
    pub = datetime.date.fromisoformat(ult["publicado"][:10])
    loja = CFG.get("loja_url")
    loja_btn = (f'<a class="btn btn-lapis" href="{esc(loja)}" target="_blank" rel="noopener">Visitar a livraria</a>'
                if loja else '<span class="btn btn-lapis" aria-disabled="true">Livraria em breve</span>')
    redes_hero = "".join(f'<a href="{esc(r["url"])}" target="_blank" rel="noopener" aria-label="{esc(r["nome"])}">{icone(r["rede"])}</a>'
                         for r in CFG["redes"])
    redes_grade = "\n".join(f'          <a href="{esc(r["url"])}" target="_blank" rel="noopener">{icone(r["rede"])}<span><b>{esc(r["nome"])}</b><small>{esc(r["conta"])}</small></span></a>'
                            for r in CFG["redes"])
    contagem = {}
    for a in artigos:
        contagem[a["tema"]] = contagem.get(a["tema"], 0) + 1
    chips = [f'<button class="chip" type="button" data-tema="Todos" aria-pressed="true">Todos<span>{len(artigos)}</span></button>']
    chips += [f'<button class="chip" type="button" data-tema="{esc(t)}" aria-pressed="false">{esc(t)}<span>{contagem[t]}</span></button>'
              for t in ORDEM_TEMAS if t in contagem]
    lista = "\n".join(card_artigo(a, video=a["slug"] in vmap) for a in artigos)
    corpo = f"""<main id="inicio">
  <section class="hero">
    <div class="wrap">
      <div>
        <div class="greek">ΚΑΤΗΧΗΣΙΣ · ensinar de viva voz</div>
        <h1>A verdade eterna comunicada <em>para o hoje</em></h1>
        <p class="lede">Santos, doutrina e história da Igreja explicados com clareza por uma equipe de leigos católicos.</p>
        <div class="actions">
          <a class="btn btn-gold" href="{esc(CFG['canal_url'])}?sub_confirmation=1" target="_blank" rel="noopener">Inscrever-se no canal</a>
          <a class="btn btn-ghost" href="#livraria">Conhecer a livraria</a>
        </div>
        <div class="stats">
          <div><b>{esc(numeros['inscritos'])}</b>inscritos</div>
          <div><b>{esc(numeros['videos'])}</b>vídeos</div>
          <div><b>Diário</b>santo do dia</div>
        </div>
        <div class="social-hero"><span class="lbl">Siga</span>{redes_hero}</div>
      </div>
      <aside class="today" aria-label="Vídeo mais recente">
        <div class="eyebrow">santo do dia · novo vídeo</div>
        <div class="date">{esc(dia_festa(ult))}</div>
        <h3>{esc(limpar_titulo(ult['titulo']))}</h3>
        <p>Publicado em {pub.day} de {MESES_LONGOS[pub.month - 1]} de {pub.year}.</p>
        <a class="today-link" href="https://www.youtube.com/watch?v={esc(ult['id'])}" target="_blank" rel="noopener">Assistir no YouTube →</a>
      </aside>
    </div>
  </section>

  <section id="videos">
    <div class="wrap">
      <div class="head-row">
        <div>
          <div class="eyebrow">santo do dia</div>
          <h2>Vídeos recentes</h2>
        </div>
        <a href="{esc(CFG['canal_url'])}/videos" target="_blank" rel="noopener">Ver todos no YouTube →</a>
      </div>
      <div class="cards">
{chr(10).join(card_video(v) for v in recentes)}
      </div>
    </div>
  </section>

  <section id="formacao" class="pillars">
    <div class="wrap">
      <div class="eyebrow">formação</div>
      <h2 class="sec-title">O que você encontra aqui</h2>
      <div class="pillar-grid">
        <div class="pillar"><span class="mark">✠</span><h3>Santos e mártires</h3><p>A vida de quem viveu o Evangelho até o fim, um santo a cada dia do calendário.</p></div>
        <div class="pillar"><span class="mark">✠</span><h3>Doutrina e espiritualidade</h3><p>O <a href="{u('/catecismo/')}">Catecismo</a>, Santo Tomás e os Padres da Igreja em linguagem acessível.</p></div>
        <div class="pillar"><span class="mark">✠</span><h3>História e cultura cristã</h3><p>Concílios, ordens religiosas e a herança que formou a civilização cristã.</p></div>
        <div class="pillar"><span class="mark">✠</span><h3>Evangelho do domingo</h3><p>Comentários à liturgia dominical à luz da tradição patrística.</p></div>
      </div>
    </div>
  </section>

  <section id="artigos" class="articles">
    <div class="wrap">
      <div class="eyebrow">estudos</div>
      <h2 class="sec-title">Artigos</h2>
      <p class="partner">Estudos sobre história da Igreja, heresias, milagres e orações, escritos pelo nosso parceiro <a href="{esc(CFG['via_catolica'])}/" target="_blank" rel="noopener">Via Católica</a> e publicados aqui com autorização.</p>
      <div class="art-tools">
        <div class="chips" id="chips" role="group" aria-label="Filtrar por tema">{''.join(chips)}</div>
        <input class="search" id="art-search" type="search" placeholder="Buscar artigo" aria-label="Buscar artigo">
      </div>
      <div class="art-list" id="art-list">
{lista}
      </div>
      <p class="art-empty" id="art-empty" hidden>Nenhum artigo encontrado. Tente outra palavra ou outro tema.</p>
      <div class="more"><button class="btn btn-lapis" id="art-more" type="button" hidden>Mostrar mais artigos</button></div>
    </div>
  </section>

  <section id="livraria" class="shop">
    <div class="wrap">
      <div>
        <div class="eyebrow">kathekésis livraria</div>
        <h2>Livros para aprofundar a fé</h2>
        <p>Obras selecionadas pela mesma equipe do canal: catecismos, clássicos da espiritualidade, Padres da Igreja e vidas de santos.</p>
        <div class="actions" style="margin-top: 24px;">
          {loja_btn}
        </div>
      </div>
      <div class="shelf">
        <a href="{u('/catecismo/')}"><span class="spine"></span><span><b>Catecismo e doutrina</b><small>Catecismo da Igreja Católica e Compêndio, por seções</small></span></a>
        <a href="{esc(loja or '#livraria')}"><span class="spine"></span><span><b>Padres da Igreja</b><small>Agostinho, Crisóstomo, Jerônimo</small></span></a>
        <a href="{esc(loja or '#livraria')}"><span class="spine"></span><span><b>Vidas de santos</b><small>Biografias e hagiografias</small></span></a>
        <a href="{esc(loja or '#livraria')}"><span class="spine"></span><span><b>Espiritualidade</b><small>Oração, ascese e vida interior</small></span></a>
      </div>
    </div>
  </section>

  <section id="sobre" class="about">
    <div class="wrap">
      <div class="eyebrow">sobre</div>
      <h2>Quem somos</h2>
      <p>Somos uma equipe de leigos católicos comprometidos em anunciar a sã doutrina da Igreja e transmitir a riqueza da fé católica de forma clara e envolvente.</p>
      <p>Nosso propósito é tornar os ensinamentos perenes da Igreja compreensíveis para o mundo de hoje, ajudando você a conhecer mais profundamente a verdade de Cristo, viver a fé no cotidiano e redescobrir a beleza do patrimônio espiritual católico.</p>
      <blockquote>Kathekésis: a verdade eterna comunicada para o hoje.</blockquote>
      <div class="follow">
        <div class="eyebrow">acompanhe</div>
        <h3>Siga o Kathekésis</h3>
        <div class="follow-grid">
{redes_grade}
        </div>
      </div>
    </div>
  </section>
</main>"""
    return pagina("Kathekésis", "Santos, doutrina e história da Igreja explicados com clareza por uma equipe de leigos católicos.", "/", corpo)


def gerar_artigo(a, artigos, vmap):
    v = vmap.get(a["slug"])
    caixa_video = ""
    if v:
        h = " h" if v["formato"] == "horizontal" else ""
        caixa_video = f"""    <a class="watch" href="https://www.youtube.com/watch?v={esc(v['id'])}" target="_blank" rel="noopener">
      <span class="vthumb{h}"><img src="{capa(v['id'])}" alt="" loading="lazy"><span class="play" aria-hidden="true">{icone('play', 'pi')}</span></span>
      <span><small>assista no canal kathekésis</small><b>{esc(v['titulo'])}</b></span>
    </a>"""
    rel = [x for x in artigos if x["tema"] == a["tema"] and x["slug"] != a["slug"]][:3]
    rel_html = "\n".join(card_artigo(x, extra_attrs=False, video=x["slug"] in vmap) for x in rel)
    corpo = f"""<article id="leitor">
  <div class="wrap">
    <a class="back" href="{u('/#artigos')}">← Todos os artigos</a>
    <div class="eyebrow" style="margin-top: 22px;">{esc(a['tema'])}</div>
    <h1>{esc(a['titulo'])}</h1>
    <div class="credit">Publicado originalmente no <a href="{esc(a['original'])}" target="_blank" rel="noopener">Via Católica</a></div>
{caixa_video}
    <div class="prose">
{a['corpo']}
    </div>
    <div class="endnote"><p>Este artigo foi publicado originalmente no <a href="{esc(a['original'])}" target="_blank" rel="noopener">Via Católica</a> e é reproduzido aqui com autorização. Quer se aprofundar? Conheça os livros da <a href="{u('/#livraria')}">Kathekésis Livraria</a>.</p></div>
    <div class="related"><div class="eyebrow">continue lendo</div><h2>Mais em {esc(a['tema'])}</h2><div class="art-list">
{rel_html}
    </div></div>
  </div>
</article>"""
    # canonical aponta para o original no Via Católica (evita conteúdo duplicado no Google)
    return pagina(f"{a['titulo']} · Kathekésis", a["resumo"], f"/artigos/{a['slug']}/", corpo, canonical=a["original"])


def gerar_catecismo(cat, artigos):
    por_slug = {a["slug"]: a for a in artigos}
    romanos = ["I", "II", "III", "IV"]
    n = lambda x: f"{x:,}".replace(",", ".")

    def ext(url, txt, cls=""):
        classes = (cls + " ext").strip()
        return f'<a class="{classes}" href="{esc(url)}" target="_blank" rel="noopener">{esc(txt)}</a>'

    def linha(t, url, faixa, subs=()):
        sub = ""
        if subs:
            sub = "<ul>" + "".join(f"<li>{ext(s['u'], s['t'])}</li>" for s in subs) + "</ul>"
        return f'<div class="crow">{ext(url, t, "ct")}<span class="cr">{esc(faixa)}</span>{sub}</div>'

    def bloco(i, titulo, faixa, resumo, dentro, aberto):
        return (f'<details class="cpart"{" open" if aberto else ""}><summary><span class="pn">{romanos[i]}</span>'
                f'<h2>{esc(titulo)}</h2><span class="prange">{esc(faixa)}<span class="chev">›</span></span>'
                f'<p class="psum">{esc(resumo)}</p></summary><div class="cbody">{dentro}</div></details>')

    cic = [f'<div class="cpart"><div class="cbody" style="padding-top:6px">{linha("Prólogo", cat["pro"]["u"], "§ 1–25")}</div></div>']
    for i, p in enumerate(cat["cic"]):
        dentro = ""
        for s in p["secs"]:
            titulo = s["t"].replace("Os dez mandamentos", "Os Dez Mandamentos").replace("«Pai Nosso»", "Pai-Nosso") if s["t"] else None
            dentro += '<div class="csec">' + (f"<h3>{esc(titulo)}</h3>" if titulo else "")
            for c in s["items"]:
                faixa = ""
                if c["a0"]:
                    faixa = "§ " + n(c["a0"]) + (("–" + n(c["a1"])) if c["a1"] and c["a1"] != c["a0"] else "")
                dentro += linha(c["t"], c["u"], faixa, c["arts"])
            dentro += "</div>"
        rel = [por_slug[x] for x in p.get("rel", []) if x in por_slug]
        if rel:
            dentro += ('<div class="crel"><div class="eyebrow">aprofunde nos artigos</div><div class="chips">'
                       + "".join(f'<a class="chip" href="{u("/artigos/%s/" % a["slug"])}">{esc(a["titulo"])}</a>' for a in rel)
                       + "</div></div>")
        cic.append(bloco(i, p["t"], f"§ {n(p['a0'])}–{n(p['a1'])}", p["sum"], dentro, i == 0))
    resumos = ["As verdades da fé, do desejo de Deus ao Credo.", "A liturgia e os sete sacramentos.",
               "A vida moral, a graça e os Dez Mandamentos.", "A oração cristã e o Pai-Nosso."]
    comp = [f'<div class="cpart"><div class="cbody" style="padding-top:6px">{linha("Motu proprio e Introdução", cat["compIntro"], "")}</div></div>']
    for i, p in enumerate(cat["comp"]):
        dentro = ""
        for s in p["secs"]:
            dentro += f'<div class="csec"><h3>{esc(s["t"])}</h3>'
            if not s["ch"]:
                dentro += linha(s["t"], s["u"], f"perg. {s['q'][0]}–{s['q'][1]}")
            for c in s["ch"]:
                dentro += linha(c["t"], c["u"], f"perg. {c['q0']}–{c['q1']}")
            dentro += "</div>"
        comp.append(bloco(i, p["t"], f"perguntas {p['q'][0]}–{p['q'][1]}", resumos[i], dentro, i == 0))
    comp.append(f'<div class="cpart"><div class="cbody" style="padding-top:6px">{linha("Apêndice: orações comuns e fórmulas de doutrina católica", cat["compApp"], "")}</div></div>')

    # índice enxuto para o "ir para o parágrafo/pergunta"
    idx_cic = [{"t": "Prólogo", "u": cat["pro"]["u"], "a0": 1, "a1": 25, "p": ""}]
    for p in cat["cic"]:
        for s in p["secs"]:
            for c in s["items"]:
                if c["a0"]:
                    idx_cic.append({"t": c["t"], "u": c["u"], "a0": c["a0"], "a1": c["a1"] or c["a0"], "p": p["t"]})
    idx_comp = []
    for p in cat["comp"]:
        for s in p["secs"]:
            for c in s["ch"]:
                idx_comp.append({"t": c["t"], "u": c["u"], "a0": c["q0"], "a1": c["q1"]})
            idx_comp.append({"t": s["t"], "u": s["u"], "a0": s["q"][0], "a1": s["q"][1]})
    idx = json.dumps({"cic": idx_cic, "comp": idx_comp, "intro": cat["compIntro"]}, ensure_ascii=False).replace("</", "<\\/")

    corpo = f"""<div id="catecismo-view">
  <div class="cat-hero">
    <div class="wrap cat-wrap">
      <a class="back" href="{u('/')}">← Início</a>
      <div class="eyebrow" style="margin-top: 18px;">doutrina</div>
      <h1 id="cat-h1">Catecismo da Igreja Católica</h1>
      <p id="cat-lede" data-cic="O Catecismo completo, organizado em partes, seções e capítulos. Cada link abre o texto oficial no site do Vaticano." data-comp="A síntese do Catecismo em 598 perguntas e respostas, publicada por Bento XVI em 2005. Cada link abre o texto oficial no site do Vaticano.">O Catecismo completo, organizado em partes, seções e capítulos. Cada link abre o texto oficial no site do Vaticano.</p>
      <div class="tabs" role="tablist" aria-label="Escolha o texto">
        <button class="tab" role="tab" id="tab-cic" aria-selected="true" aria-controls="painel-cic" type="button">Catecismo · 2.865 parágrafos</button>
        <button class="tab" role="tab" id="tab-comp" aria-selected="false" aria-controls="painel-comp" type="button">Compêndio · 598 perguntas</button>
      </div>
    </div>
  </div>
  <div class="wrap cat-wrap">
    <form class="jump" id="jump">
      <label for="jump-n" id="jump-label">Ir para o parágrafo §</label>
      <input id="jump-n" type="number" inputmode="numeric" min="1" max="2865" placeholder="ex.: 1213">
      <button class="btn btn-lapis" type="submit">Localizar</button>
      <div class="jump-out" id="jump-out" aria-live="polite"></div>
    </form>
    <div id="painel-cic" role="tabpanel" aria-labelledby="tab-cic">{''.join(cic)}</div>
    <div id="painel-comp" role="tabpanel" aria-labelledby="tab-comp" hidden>{''.join(comp)}</div>
    <p class="cnote">Texto oficial © Libreria Editrice Vaticana, publicado em <a class="ext" href="{esc(cat['cicIndex'])}" target="_blank" rel="noopener">vatican.va</a>. Os resumos das partes foram escritos pela equipe Kathekésis.</p>
  </div>
</div>
<script type="application/json" id="cat-index">{idx}</script>"""
    return pagina("Catecismo da Igreja Católica · Kathekésis",
                  "O Catecismo da Igreja Católica e o Compêndio organizados por partes, seções e capítulos, com links para o texto oficial.",
                  "/catecismo/", corpo)


def gerar_404():
    corpo = f"""<main class="about"><div class="wrap" style="padding-block: 80px;">
  <div class="eyebrow">página não encontrada</div>
  <h2>Esta página não existe</h2>
  <p>O endereço pode ter mudado. Volte para o <a href="{u('/')}">início</a> ou veja os <a href="{u('/#artigos')}">artigos</a>.</p>
</div></main>"""
    return pagina("Página não encontrada · Kathekésis", "Página não encontrada.", "/404.html", corpo)


def escrever(caminho, conteudo):
    arq = OUT / caminho
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(conteudo, encoding="utf-8")


def main():
    videos = com_cache("videos", buscar_videos)
    numeros = com_cache("numeros", buscar_numeros)
    artigos = com_cache("artigos", buscar_artigos)
    vmap = json.loads((DATA / "videos_artigos.json").read_text(encoding="utf-8"))
    cat = json.loads((DATA / "catecismo.json").read_text(encoding="utf-8"))

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "assets", OUT / "assets")
    escrever("index.html", gerar_inicio(videos, numeros, artigos, vmap))
    for a in artigos:
        escrever(f"artigos/{a['slug']}/index.html", gerar_artigo(a, artigos, vmap))
    escrever("catecismo/index.html", gerar_catecismo(cat, artigos))
    escrever("404.html", gerar_404())

    hoje = datetime.date.today().isoformat()
    urls = [(SITE + "/", hoje), (SITE + "/catecismo/", hoje)]
    # os artigos ficam fora do sitemap: o canonical deles aponta para o Via Católica
    mapa = "\n".join(f"  <url><loc>{esc(l)}</loc><lastmod>{d}</lastmod></url>" for l, d in urls)
    escrever("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{mapa}\n</urlset>\n')
    escrever("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    if CFG.get("dominio"):
        escrever("CNAME", CFG["dominio"] + "\n")
    escrever(".nojekyll", "")
    print(f"[ok] site gerado em {OUT}: {len(artigos)} artigos, {len(videos[:6])} vídeos recentes")


if __name__ == "__main__":
    main()
