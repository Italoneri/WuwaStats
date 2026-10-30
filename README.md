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
