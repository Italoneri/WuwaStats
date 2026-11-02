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
uv run python scripts/importar_builds_game8.py --simular  # builds dos guias do Game8 (sem --simular, grava)
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

A captura roda dentro do servidor (`uv run wuwastats serve`). **Rode o servidor num terminal como administrador**: o jogo
roda como admin, e com ele em foco o Windows não entrega os atalhos a um processo comum (a tecla some sem bipe nem erro).
Se o jogo já estiver aberto como admin e o servidor não, **Iniciar captura** recusa com essa explicação.

Na página Captura, escolha a build e clique em
**Iniciar captura**: o servidor passa a escutar as teclas enquanto você joga, e cada print é lido pela IA na hora.

| Tecla (padrão) | O que faz |
|---|---|
| F8 | print do echo aberto → próximo espaço vazio (ou o marcado com "Refazer"); o 1º espaço é o echo principal |
| F9 | print da tela do personagem (arma, nível, atributos totais) → substitui o anterior |
| F10 | avisa a página aberta para ir para a análise |

- Bipe agudo = salvo; dois bipes graves = erro (a mensagem aparece na página).
- Só a área interna da janela cujo título é exatamente `Wuthering Waves` é capturada, e só com o jogo em primeiro plano.
  Se o título for outro, o erro lista janelas parecidas; ajuste `CAPTURA_TITULO_JANELA` no `.env`.
- Use o jogo em modo janela ou tela cheia sem bordas: em tela cheia exclusiva o print pode sair preto.
- O servidor só lê a tela. Escuta F8–F10 com `RegisterHotKey` enquanto a captura estiver ligada, e por isso essas teclas
  não chegam ao jogo nesse período. Ele nunca envia cliques nem teclas ao jogo, e um teste falha se alguém incluir uma API
  que faça isso. Parar a captura (ou derrubar o servidor) solta as teclas.
- O jogo pode engolir as teclas comuns enquanto está em foco (nem o PrtSc funciona). Combinações com a tecla Windows
  costumam passar: troque os atalhos no `.env` (`CAPTURA_TECLA_ECHO=Win+Shift+E` etc.; aceita Ctrl, Alt, Shift, Win +
  F1–F24, A–Z, 0–9, Num0–Num9). A página mostra as teclas configuradas.
### Mais na interface

- **Echos** (menu lateral): todos os echos com a imagem, para conferir à mão; o filtro "Só sem imagem" mostra os que
  faltam. Clicar abre o que o echo faz (habilidade com os valores do nível mais alto) e permite trocar a imagem.
- **Editor de builds** (menu lateral): prioridade dos substatus em estrelas (1 a 3, ordem ajustável entre iguais), metas de status (faixa, tipo, fonte e porquê), custos, principais, set, echo principal, armas e
  variantes. Salvar valida com o mesmo loader dos dados, guarda o arquivo anterior em `data/backups/` e recarrega.
- **Imagens**: passe o mouse no retrato do personagem, na arma ou no echo e clique na câmera para enviar uma imagem
  (PNG/JPEG/WebP até 5 MB). Ficam em `data/imagens/`.
- **Histórico**: na Análise, "Salvar análise" guarda a entrada corrigida em `data/historico/`; depois dá para reabrir e
  comparar o antes e o depois de trocar um echo.
- `data/imagens/`, `data/historico/` e `data/backups/` estão no `.gitignore` (dados pessoais).

## Dados de jogo

Tudo em `data/`, editável à mão:

| Arquivo | Conteúdo |
|---|---|
| `substats.json` | valores discretos de cada substatus (índice = tier) |
| `main_stats.json` | status principais por custo |
| `sets.json` | sets, nome PT, peças, bônus que são status (ex.: Regen. de Energia) e texto de cada efeito — gerado |
| `echoes.json` | catálogo de echos (nome PT, custo, sets possíveis, o que a habilidade faz) — gerado |
| `stat_aliases.json` | chave interna (inglês) → nomes do jogo (PT-BR) e alternativos |
| `characters.json` | perfis de build (com `armas` recomendadas, opcional) |
| `notas.json` | faixas de nota (SSS…C) pelo score |
| `resonators.json` | ressonadores jogáveis (elemento, tipo de arma, raridade, nome PT) — gerado |
| `weapons.json` | armas (nome PT, tipo, raridade) — gerado |
| `fonte_dados_jogo.json` | commit/versão de [Arikatsu/WutheringWaves_Data](https://github.com/Arikatsu/WutheringWaves_Data) usado na última importação |

Entradas com `"status": "TODO: ..."` ainda precisam ser conferidas num wiki atualizado.

### Atualizar echos, sets, ressonadores e armas

`scripts/importar_dados_jogo.py` baixa as tabelas de echos (com a habilidade)/sonatas e os textos EN/PT do repositório (branch padrão = versão
atual do jogo), regenera `echoes.json`, `sets.json`, `resonators.json` e `weapons.json` e acrescenta os nomes PT como aliases, sem apagar mapeamentos manuais.
Tudo é validado numa cópia antes de tocar em `data/`. Compare `commit` em `fonte_dados_jogo.json` com o último commit do
repositório para saber se há atualização.

- Echos cujas variantes têm custos diferentes na fonte ficam com `custo: null` e TODO; o custo que você preencher à mão é mantido nas próximas importações.
- Echos/sets que não existem mais na fonte são mantidos com TODO (podem estar em `characters.json`); renomeie ou remova.
- Ícones de echos, armas e sets: depois de gravar os dados, baixa de [nanoka.cc](https://ww.nanoka.cc) (mesmo caminho de textura
  dos campos de ícone da fonte) os que ainda não estão em `data/imagens/`. Imagem que já existe, inclusive enviada à mão, nunca
  é sobrescrita; para trocar, envie outra pela página. Ressonadores ficam de fora: a imagem deles é escolhida à mão.

### Kit dos personagens

`uv run python scripts/importar_kits.py --personagens Aemeath Yangyang Suoming` grava em `data/kits.json` o kit oficial
(habilidades na ordem do jogo, multiplicadores do nível 1 ao 10, inerentes, bônus da árvore, sequências e tags) com o texto PT
do jogo, do mesmo commit de `fonte_dados_jogo.json` (`--ref` troca). Sem `--personagens`, importa todos; só os pedidos são
trocados no arquivo.

- Texto sem tradução PT usa o oficial em inglês e aparece nos avisos. Nada é escrito à mão em `kits.json`.
- Ícones das habilidades/sequências e as ilustrações do forte vêm do [nanoka.cc](https://ww.nanoka.cc) para
  `data/imagens/kit/<personagem>/`. Ícone que não existir lá vira placeholder na página; ilustração do forte que não
  existir (ex.: as da Suoming) simplesmente não aparece.
- O resumo do topo da aba Kit fica em `data/kit_resumos.json`, escrito à mão (palavras próprias, a partir do Game8).

### Builds a partir do Game8

`scripts/importar_builds_game8.py` lê os guias "Best Builds and Teams" do [Game8](https://game8.co/games/Wuthering-Waves) e
gera uma build por bloco do guia: armas, set, padrão de custo, echo principal, status principais e estrelas dos substatus.

- Personagem que já tem build fica intacto; `--personagem X --substituir` troca as builds dele. `--simular` só mostra o relatório.
- Grava como o editor: valida tudo antes, guarda o arquivo anterior em `data/backups/` e escreve de forma atômica.
- A meta de Regen. de Energia vira a faixa citada no guia (`115–120%` → mínimo 115, máximo 120), com tipo `rotacao` e fonte
  `game8`; tipo e explicação ficam para conferir à mão.
- O que precisa de revisão fica em `status: "TODO: ..."`: meta de Regen. de Energia sem explicação ou que o guia não cita
  (a build fica sem meta), nome fora do catálogo, ou combinação de sets (3 peças + 2), já que a build guarda um set só.
- O texto explicativo (`descricao`) não é gerado: é escrito à mão, com palavras próprias.
- As páginas ficam em `cache/game8/`; `--atualizar` baixa de novo (por exemplo, depois de um patch).
