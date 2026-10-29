# WuwaStats

Analisador de echos de Wuthering Waves: lê os 5 echos de um personagem, compara cada substatus com os valores possíveis e calcula um score por echo a partir das prioridades da build.

## Rodar

```bash
uv sync
uv run wuwastats check-data                          # valida data/*.json
uv run wuwastats analyze fixtures/entradas/suoming_dps.json
uv run wuwastats extract input/ --build Suoming_DPS --saida input/entrada.json  # IA de visão
uv run wuwastats alias sets "Moonlit Clouds" "<nome PT-BR>"
uv run pytest
uvx ruff check src && uvx pyright src
```

## Extração por print

1. Copie `.env.example` para `.env` e preencha `NVIDIA_API_KEY` e `NVIDIA_VISION_MODEL`.
2. Coloque os prints dos echos em `input/` (ordem alfabética = ordem dos slots; o 1º é o echo principal).
   O print da tela do personagem, se houver, deve se chamar `personagem.png` (ou `personagem*`).
3. `extract` gera o JSON de entrada; revise/corrija e rode `analyze`.

Respostas da IA ficam em `cache/vision/` por hash da imagem + modelo: reprocessar o mesmo print não gasta crédito.
Prints que falharem aparecem no resumo com o motivo; preencha esses echos à mão no JSON.

## Dados de jogo

Tudo em `data/`, editável à mão:

| Arquivo | Conteúdo |
|---|---|
| `substats.json` | valores discretos de cada substatus (índice = tier) |
| `main_stats.json` | status principais por custo |
| `sets.json` | sets, peças e bônus que são status (ex.: Regen. de Energia) |
| `echoes.json` | catálogo de echos (custo) |
| `stat_aliases.json` | chave interna (inglês) → nomes do jogo (PT-BR) e alternativos |
| `characters.json` | perfis de build |

Entradas com `"status": "TODO: confirmar"` ainda precisam ser conferidas num wiki atualizado.
