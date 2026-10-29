# WuwaStats

Analisador de echos de Wuthering Waves: lê os 5 echos de um personagem, compara cada substatus com os valores possíveis e calcula um score por echo a partir das prioridades da build.

## Rodar

```bash
uv sync
uv run wuwastats check-data                          # valida data/*.json
uv run wuwastats analyze fixtures/entradas/suoming_dps.json
uv run wuwastats alias sets "Moonlit Clouds" "<nome PT-BR>"
uv run pytest
uvx ruff check src && uvx pyright src
```

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
