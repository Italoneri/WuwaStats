# Fanart na tela do personagem

## Objetivo

Separar as duas imagens do personagem:

- **Galeria** (`index.html`): foto padrão com fundo transparente (estilo nanoka), enviada à mão pelo botão de trocar no
  próprio card. Continua em `data/imagens/personagens/<chave>.png`.
- **Tela do personagem**: fanart como banner de fundo do cabeçalho, com crédito do artista (nome + link da postagem).

## Decisões

| Ponto | Escolha |
|---|---|
| Layout | Banner de fundo no cabeçalho, escurecido no lado do texto; crédito no canto inferior direito; abas abaixo do banner |
| Crédito | `artista` (obrigatório, até 80 caracteres) + `link` (opcional, só http/https) |
| Sem fanart | Banner usa a foto padrão (contain, à direita), sem crédito; sem foto padrão, a silhueta |
| Foto padrão | Envio manual no card da galeria |

## Armazenamento

`data/imagens/fanarts/<nome>.webp` + `<nome>.json` (`{"artista": "...", "link": "..."}`), lado máximo 1920 px, envio
até 15 MB. WebP (qualidade 90) porque fanart é grande e não precisa de transparência. Pasta já está no `.gitignore`.

## API

- `GET /api/fanarts` → `{"<chave>": {"artista": str, "link": str | null}}` (só quem tem fanart)
- `GET /api/fanarts/{chave}` → a imagem (`image/webp`, `no-cache`)
- `PUT /api/fanarts/{chave}` multipart: `arquivo` (opcional quando a fanart já existe: só troca o crédito), `artista`,
  `link`. 404 para chave fora dos ressonadores, 422 para imagem/crédito inválido ou falta de imagem na primeira vez.

## Frontend

- `web/fanart.js`: arte do banner, crédito e diálogo de envio/edição (arquivo, artista, link).
- `web/personagem.js`: cabeçalho vira banner; abas saem do cabeçalho.
- `web/personagens.js`: card da galeria com botão de trocar a foto padrão (sem navegar ao clicar nele).
