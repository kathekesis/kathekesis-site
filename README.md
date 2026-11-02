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
3. Na Hostinger, onde o domínio foi registrado, aponte o DNS para o GitHub Pages.
   Caminho: **hPanel → Domínios → (seu domínio) → DNS / Nameservers → Registros DNS**.
   - Apague os registros **A** de nome `@` e o **CNAME** de nome `www` que a Hostinger cria por padrão (eles apontam para a página "em construção" da Hostinger).
   - Crie 4 registros **A** com nome `@`, um para cada endereço: `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - Crie 1 registro **CNAME** com nome `www` apontando para `SEU-USUARIO.github.io`
   - A mudança pode levar de alguns minutos até 24 horas para valer.
   - Não é preciso contratar hospedagem na Hostinger: o site fica no GitHub Pages, de graça. Só o domínio é pago.

Observação: o GitHub pausa tarefas agendadas em repositórios sem nenhuma alteração por 60 dias. Se isso acontecer, ele avisa por e-mail; basta clicar para reativar.
