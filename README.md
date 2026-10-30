# WuwaStats

Analisador de echos de Wuthering Waves: lê os 5 echos de um personagem, compara cada substatus com os valores possíveis e calcula um score por echo a partir das prioridades da build.

## Rodar

```bash
uv sync
uv run wuwastats serve                               # API + página em http://127.0.0.1:8000 (contrato: docs/api.md)
uv run wuwastats check-data                          # valida data/*.json
uv run wuwastats analyze fixtures/entradas/suoming_dps.json
uv run wuwastats extract input/ --build Suoming_DPS --saida input/entrada.json  # IA de visão
uv run wuwastats alias sets "Moonlit Clouds" "<nome PT-BR>"
uv run python scripts/importar_dados_jogo.py         # atualiza echos/sets a partir dos dados do jogo
uv run pytest
uvx ruff check src scripts && uvx pyright src scripts
```

## Extração por print

1. Copie `.env.example` para `.env` e preencha `NVIDIA_API_KEY` e `NVIDIA_VISION_MODEL`.
2. Coloque os prints dos echos em `input/` (ordem alfabética = ordem dos slots; o 1º é o echo principal).
   O print da tela do personagem, se houver, deve se chamar `personagem.png` (ou `personagem*`).
3. `extract` gera o JSON de entrada; revise/corrija e rode `analyze`.

Respostas da IA ficam em `cache/vision/` por hash da imagem + modelo: reprocessar o mesmo print não gasta crédito.
Prints que falharem aparecem no resumo com o motivo; preencha esses echos à mão no JSON.

### Captura por atalho (Windows)

`scripts/captura.py` fica rodando num terminal enquanto você joga e tira os prints sem sair do jogo:

```bash
uv run python scripts/captura.py Suoming --build Suoming_DPS   # --build é opcional se o personagem tiver uma build só
```

| Tecla | O que faz |
|---|---|
| F8 | print do echo aberto → `input/<personagem>/echo_N.png` (N em sequência, até 5; o 1º é o echo principal) |
| F9 | print da tela do personagem (arma e regen total) → `input/<personagem>/personagem.png` (substitui o anterior) |
| F10 | roda `extract` na pasta, grava `entrada.json`, sobe a API se ela não estiver no ar e abre a análise no navegador |
| Ctrl+C | encerra (e derruba a API, se foi o script que subiu) |

- Bipe agudo = salvo; dois bipes graves = erro (a mensagem aparece no terminal).
- Só a área interna da janela cujo título é exatamente `Wuthering Waves` é capturada, e só com o jogo em primeiro plano.
  Se o título for outro, o erro lista janelas parecidas; use `--titulo`.
- Use o jogo em modo janela ou tela cheia sem bordas: em tela cheia exclusiva o print pode sair preto.
- O script só lê a tela. Escuta F8–F10 com `RegisterHotKey`, e por isso essas teclas não chegam ao jogo enquanto ele estiver
  rodando. Ele nunca envia cliques nem teclas ao jogo, e um teste falha se alguém incluir uma API que faça isso.
- Para refazer um print de echo, apague o arquivo e aperte F8 de novo: o próximo número livre é usado.
- Se os atalhos não responderem com o jogo em foco, rode o terminal como administrador.

## Dados de jogo

Tudo em `data/`, editável à mão:

| Arquivo | Conteúdo |
|---|---|
| `substats.json` | valores discretos de cada substatus (índice = tier) |
| `main_stats.json` | status principais por custo |
| `sets.json` | sets, nome PT, peças, bônus que são status (ex.: Regen. de Energia) e texto de cada efeito — gerado |
| `echoes.json` | catálogo de echos (nome PT, custo, sets possíveis) — gerado |
| `stat_aliases.json` | chave interna (inglês) → nomes do jogo (PT-BR) e alternativos |
| `characters.json` | perfis de build |
| `fonte_dados_jogo.json` | commit/versão de [Arikatsu/WutheringWaves_Data](https://github.com/Arikatsu/WutheringWaves_Data) usado na última importação |

Entradas com `"status": "TODO: ..."` ainda precisam ser conferidas num wiki atualizado.

### Atualizar echos e sets

`scripts/importar_dados_jogo.py` baixa as tabelas de echos/sonatas e os textos EN/PT do repositório (branch padrão = versão
atual do jogo), regenera `echoes.json` e `sets.json` e acrescenta os nomes PT como aliases, sem apagar mapeamentos manuais.
Tudo é validado numa cópia antes de tocar em `data/`. Compare `commit` em `fonte_dados_jogo.json` com o último commit do
repositório para saber se há atualização.

- Echos cujas variantes têm custos diferentes na fonte ficam com `custo: null` e TODO; o custo que você preencher à mão é mantido nas próximas importações.
- Echos/sets que não existem mais na fonte são mantidos com TODO (podem estar em `characters.json`); renomeie ou remova.
