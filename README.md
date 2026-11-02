# Site do Kathekésis

Site do canal Kathekésis, publicado pelo GitHub Pages. Ele se atualiza sozinho a cada hora:

- **Vídeos recentes e "santo do dia"**: lidos do feed público do canal no YouTube.
- **Números do canal** (inscritos e vídeos): lidos da página do canal.
- **Artigos**: lidos do Via Católica (publicados com autorização). Cada artigo aponta o original como "canonical", para o Google não tratar como cópia.
- **Catecismo e Compêndio**: estrutura com links para o texto oficial em vatican.va.

Se alguma busca falhar, o site usa a última cópia salva em `data/cache/` e continua no ar.

## Onde mudar as coisas

| O que | Arquivo |
|---|---|
| Domínio, link da loja, redes sociais | `data/config.json` |
| Vídeo ligado a cada artigo | `data/videos_artigos.json` |
| Estrutura do Catecismo | `data/catecismo.json` |
| Cores e visual | `assets/style.css` |
| Textos da página inicial | `build.py` (função `gerar_inicio`) |

## Atualizar na hora

No GitHub, abra **Actions → Atualizar e publicar o site → Run workflow**.

## Testar no computador

```bash
python build.py
```

```bash
python -m http.server 8000 --directory _site
```

Depois abra http://localhost:8000.

## Configuração única no GitHub

1. **Settings → Pages → Build and deployment → Source**: escolha **GitHub Actions**.
2. **Settings → Pages → Custom domain**: digite `kathekesis.com.br` e salve. Marque **Enforce HTTPS** quando aparecer.
3. No registro do domínio (Registro.br), aponte o DNS para o GitHub Pages:
   - 4 registros **A** para `kathekesis.com.br`: `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - 1 registro **CNAME** para `www`: `SEU-USUARIO.github.io`

Observação: o GitHub pausa tarefas agendadas em repositórios sem nenhuma alteração por 60 dias. Se isso acontecer, ele avisa por e-mail; basta clicar para reativar.
