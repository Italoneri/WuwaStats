# Metas de status por build — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** trocar o número único `regen_energia_min` por uma lista de metas de status por build (faixa + tipo + porquê +
fonte), comparar cada meta com a tela do personagem na análise, mostrar as metas na página do personagem e no editor, e
preencher as metas das 52 builds que já têm `descricao`.

**Architecture:** um módulo de domínio novo (`domain/metas.py`) guarda o tipo `MetaDeStatus` (o mesmo modelo serve de
schema do JSON, de dado de domínio e de saída da API) e a função pura `comparar_meta`. A análise do conjunto
(`domain/conjunto.py`) junta valor lido + meta e gera problemas. A entrada da análise ganha os atributos da tela, crus,
resolvidos na análise como já acontece com os substatus. O front só exibe o que a API devolve.

**Tech Stack:** Python 3.13, Pydantic 2, FastAPI, pytest; front em JS puro (`web/*.js`, helper `el()` de `comum.js`).

**Spec:** `docs/superpowers/specs/2026-10-31-metas-de-status-design.md`

## Decisões do usuário (2026-11-01), respondendo a seção 3 da spec

1. Game8 × Prydwen: **Game8 primeiro**; Prydwen só preenche o que o Game8 não traz (ex.: crítico). Uma fonte por meta.
2. Sem número em nenhuma fonte: **sem meta + `status` TODO** na build. A regra 70/270 nunca vira dado.
3. Suportes: meta de crítico **só se a fonte der**. Suporte sem crítico não gera TODO; DPS sem crítico gera.
4. Condição da faixa (sequência, time, rotação): **só texto** na `explicacao`.
5. Veredito (textos exatos em Task 1). Só `abaixo` vira problema `build`. Avisos de excesso existem **só** para:
   Regen. de Energia acima do máximo/teto da meta, e Taxa CRIT lida **acima de 90%** (com buffs de time, ex. Guardiã da
   Costa, passa de 100%), com ou sem meta de crítico. Crítico/ATQ/HP/DEF acima da faixa: só informativo, "quanto mais melhor".
6. `regen_energia_min` **sai de vez** (JSON, schema, domínio, API, front, importador). Build sem meta de Regen fica sem
   mínimo.
7. Regen comparada com a meta: **valor da tela se houver, senão o total calculado pelos echos**. O aviso de divergência
   continua.
8. Editor de builds: **lista editável** de metas.

## Global Constraints

- Tipos fortes, sem `Any` novo, `Literal` para conjuntos fechados, validar na borda (Pydantic), funções puras no domínio.
- Testes table-driven (`pytest.mark.parametrize`), nomes de teste com verbo na 3ª pessoa, sem "should"; teste ao lado do fonte.
- Remover código antigo por completo: nenhum `regen_energia_min`, `regen.minimo`, `regen.atinge`, `regen_insuficiente`
  pode sobrar (`grep -rn` no fim da Task 3 e da Task 7).
- Textos PT-BR do glossário da spec §7 (Regen. de Energia, Taxa CRIT, Dano CRIT, Guardiã da Costa…).
- Não inventar dado de jogo: número só com fonte; sem número → TODO.
- Nunca rodar o importador com `--substituir` em build com `descricao`. Não separar `status` por `"; "`.
- Gravar `data/characters.json` só via `wuwastats.gamedata.perfis.gravar_perfis` (valida + backup + escrita atômica).
- Rodar com `uv run`; saída de script com `PYTHONIOENCODING=utf-8`; Python sobre HTML baixado com `-I`.
- Commits conventional, minúsculos, sem citar Claude, um por task; direto na `main`, como o histórico do repo.
- Suíte verde antes de cada commit: `uv run pytest` (hoje: 290 passed) e `uv run ruff check`.

## Review Focus

1. **"HP" lido da tela sem `%` e com `percentual: null`** → precisa virar `hp_flat` (senão "HP" é ambíguo entre
   `hp_pct`/`hp_flat` e a meta da Jingran nunca compara). Teste na Task 3.
2. **Fronteiras do veredito**: rotação exatamente no máximo = `dentro`; escala exatamente no teto = `acima` ("no teto").
   Teste na Task 1.
3. **Análise salva antiga** (`data/historico/*.json`, `entrada` sem `atributos`) continua abrindo. Teste na Task 3.
4. **Variante com `metas`** substitui a lista inteira; variante sem `metas` herda a da base. Nenhuma build usa variante
   hoje, mas o caminho existe. Teste na Task 2.
5. **Editor: campo "máx." vazio** grava `null`, não `0` (0 < mín. quebraria a validação e travaria o salvar). Conferência
   manual na Task 8.

---

### Task 1: Modelo de meta e veredito (`domain/metas.py`)

**Files:**
- Create: `src/wuwastats/domain/metas.py`
- Test: `src/wuwastats/domain/test_metas.py`

**Interfaces:**
- Produces:
  - `StatDeMeta = Literal["energy_regen", "crit_rate", "crit_dmg", "hp_flat", "atk_flat", "def_flat"]` (os totais da
    tela: HP/ATQ/DEF totais são as chaves `_flat`, como `resolve_stat` devolve).
  - `TipoDeMeta = Literal["escala", "rotacao"]`, `FonteDeMeta = Literal["game8", "prydwen"]`,
    `Veredito = Literal["abaixo", "dentro", "acima"]`, `OrigemValor = Literal["tela", "echos"]`.
  - `class MetaDeStatus(BaseModel)` — `ConfigDict(extra="forbid", frozen=True)`; campos `stat: StatDeMeta`,
    `min: float = Field(gt=0)`, `max: float | None = None`, `tipo: TipoDeMeta`,
    `explicacao: str | None = Field(default=None, min_length=1)`, `fonte: FonteDeMeta`. `model_validator(mode="after")`:
    `max` < `min` → erro `"max menor que min"`; `stat == "energy_regen"` e `min < 100` → erro
    `"Regen. de Energia começa em 100%"`.
  - `class MetaAnalise(BaseModel)` frozen: `meta: MetaDeStatus`, `valor: float | None`, `origem: OrigemValor | None`,
    `veredito: Veredito | None`, `mensagem: str | None`.
  - `def comparar_meta(meta: MetaDeStatus, valor: float | None, origem: OrigemValor | None) -> MetaAnalise`
  - `def formatar_valor(stat: StatDeMeta, valor: float) -> str` — `%` para stats percentuais (`is_percent_stat`), número
    com `:g` (`105%`, `1.5%`); `_flat` com milhar em ponto e sem decimais (`50.000`).
  - `def metas_unicas(metas: list[MetaDeStatus]) -> list[MetaDeStatus]` — `ValueError("meta de <stat> repetida")` se um
    stat aparece duas vezes (usado como validator nas Tasks 2).

**Regra do veredito** (teto da escala = `max` se houver, senão `min`):

| tipo | condição | veredito | mensagem |
|---|---|---|---|
| rotacao | valor < min | abaixo | `abaixo da meta, faltam {min−valor}` |
| rotacao | min ≤ valor ≤ max (ou sem max) | dentro | `dentro da faixa` |
| rotacao | valor > max, stat `energy_regen` | acima | `acima da faixa, {valor−max} sobrando` |
| rotacao | valor > max, outro stat | acima | `acima da faixa, quanto mais melhor` |
| escala | valor < min | abaixo | `abaixo, perde poder` |
| escala | min ≤ valor < teto | dentro | `rendendo, faltam {teto−valor} para o teto` |
| escala | valor ≥ teto | acima | `no teto, o que passar sobra` |
| qualquer | valor `None` | `None` | `None` |

Escala com número único (`max` nulo): teto = min, então valor < min → `abaixo, perde poder`. Diferenças formatadas com
`formatar_valor` e arredondadas a 2 casas antes.

- [ ] **Step 1: Write the failing test** — `test_compara_meta_com_valor_lido` parametrizado:

```python
ROT = dict(tipo="rotacao", fonte="prydwen")
ESC = dict(tipo="escala", fonte="game8")
CASOS = [
    (MetaDeStatus(stat="energy_regen", min=105, max=130, **ROT), 100, "abaixo", "abaixo da meta, faltam 5%"),
    (MetaDeStatus(stat="energy_regen", min=105, max=130, **ROT), 130, "dentro", "dentro da faixa"),
    (MetaDeStatus(stat="energy_regen", min=105, max=130, **ROT), 131.5, "acima", "acima da faixa, 1.5% sobrando"),
    (MetaDeStatus(stat="energy_regen", min=120, **ROT), 200, "dentro", "dentro da faixa"),
    (MetaDeStatus(stat="crit_dmg", min=210, max=260, **ROT), 280, "acima", "acima da faixa, quanto mais melhor"),
    (MetaDeStatus(stat="energy_regen", min=250, **ESC), 240, "abaixo", "abaixo, perde poder"),
    (MetaDeStatus(stat="energy_regen", min=250, **ESC), 250, "acima", "no teto, o que passar sobra"),
    (MetaDeStatus(stat="energy_regen", min=125, max=150, **ESC), 130, "dentro", "rendendo, faltam 20% para o teto"),
    (MetaDeStatus(stat="hp_flat", min=50000, **ESC), 48000, "abaixo", "abaixo, perde poder"),
    (MetaDeStatus(stat="crit_rate", min=60, max=80, **ROT), None, None, None),
]
```
  Mais: `test_formata_valor` (`("hp_flat", 50000) → "50.000"`, `("crit_rate", 62.5) → "62.5%"`);
  `test_rejeita_meta_invalida` parametrizado (`max=100, min=105` → "max menor que min"; `energy_regen min=90` →
  "começa em 100%"; `explicacao=""`; `stat="hp_pct"`); `test_rejeita_stat_repetido` em `metas_unicas`.

- [ ] **Step 2: Run** `uv run pytest src/wuwastats/domain/test_metas.py` — Expected: FAIL (`ModuleNotFoundError`).
- [ ] **Step 3: Implement** `domain/metas.py` com as interfaces acima (tabela do veredito como função pequena por tipo;
  um dict `{"escala": _escala, "rotacao": _rotacao}` despacha).
- [ ] **Step 4: Run** `uv run pytest src/wuwastats/domain/test_metas.py` — Expected: PASS.
- [ ] **Step 5: Commit** `feat: add stat target model and verdict`

---

### Task 2: `metas` no schema, no loader e na `BuildSpec`

**Files:**
- Modify: `src/wuwastats/gamedata/schemas.py` (`BuildSpecRaw`, `VarianteRaw`)
- Modify: `src/wuwastats/domain/tables.py` (`BuildSpec`)
- Modify: `src/wuwastats/gamedata/loader.py` (`_Resolvedor._spec`)
- Modify: `fixtures/gamedata/characters.json`
- Test: `src/wuwastats/gamedata/test_loader.py`

**Interfaces:**
- Consumes: `MetaDeStatus`, `metas_unicas` (Task 1).
- Produces: `BuildSpecRaw.metas: list[MetaDeStatus] = []` (validator `metas_unicas`); `VarianteRaw.metas:
  list[MetaDeStatus] | None = None` (mesmo validator quando não nulo); `BuildSpec.metas: tuple[MetaDeStatus, ...]`;
  `BuildSpec.meta_de(stat: StatDeMeta) -> MetaDeStatus | None`. `regen_energia_min` **ainda fica** nesta task (sai na 3).

Fixture: `Suoming_DPS` ganha `metas: [{"stat": "energy_regen", "min": 110, "tipo": "rotacao", "fonte": "game8",
"explicacao": "Teste."}, {"stat": "crit_rate", "min": 60, "max": 80, "tipo": "rotacao", "fonte": "prydwen"}]`;
`Suoming_SubDPS` ganha `[{"stat": "energy_regen", "min": 120, "max": 130, "tipo": "rotacao", "fonte": "game8"}]`.

- [ ] **Step 1: Write the failing tests** — `test_carrega_metas_da_build` (`dados.perfis["Suoming_DPS"].base.meta_de("crit_rate").max == 80`;
  `meta_de("crit_dmg") is None`); `test_variante_herda_ou_substitui_metas` (perfil numa cópia de dados com 2 variantes:
  uma sem `metas` → `spec.metas == base.metas`; outra com `metas: []` → `spec.metas == ()`); acrescentar à tabela de
  erros existente (linha ~69) os casos `metas` com stat repetido e com `max < min`, esperando o caminho
  `characters.json › Suoming_DPS › metas`.
- [ ] **Step 2: Run** `uv run pytest src/wuwastats/gamedata/test_loader.py` — Expected: FAIL.
- [ ] **Step 3: Implement** os campos; `_spec` passa `metas=tuple(raw.metas)`; `base_campos` já leva `metas` para a
  variante via `model_dump` (conferir que `exclude_unset` mantém a herança).
- [ ] **Step 4: Run** `uv run pytest` — Expected: tudo PASS.
- [ ] **Step 5: Commit** `feat: load per-build stat targets`

---

### Task 3: Análise compara metas com a tela; `regen_energia_min` sai do Python e dos dados

**Files:**
- Modify: `src/wuwastats/domain/models.py` (`EntradaBuild`)
- Modify: `src/wuwastats/domain/conjunto.py`, `src/wuwastats/domain/report.py`, `src/wuwastats/domain/analyze.py`
- Modify: `src/wuwastats/gamedata/schemas.py`, `src/wuwastats/domain/tables.py`, `src/wuwastats/gamedata/loader.py`
  (remover `regen_energia_min`)
- Modify: `fixtures/gamedata/characters.json` (remover `regen_energia_min`), `data/characters.json` (migração)
- Modify: `docs/api.md` (exemplos de `perfil`, `conjunto.regen`, tabela de códigos, `entrada.atributos`)
- Test: `src/wuwastats/domain/test_analyze.py`, `src/wuwastats/api/test_app.py`, `src/wuwastats/gamedata/test_loader.py`,
  `src/wuwastats/gamedata/test_historico.py` (criar se não houver teste de histórico; senão no arquivo existente)

**Interfaces:**
- Consumes: Task 1 e 2.
- Produces:
  - `EntradaBuild.atributos: tuple[StatLido, ...] = ()` — atributos totais da tela, nomes crus.
  - `ConjuntoAnalise.metas: list[MetaAnalise]` (na ordem da build).
  - `RegenAnalise` **sem** `minimo` e `atinge`.
  - `PerfilAplicado.metas: list[MetaDeStatus]` no lugar de `regen_energia_min`.
  - Códigos novos em `CodigoProblema`/`SEVERIDADE`: `meta_abaixo` (build, `campo` = stat), `regen_sobrando` (aviso,
    `campo="regen"`), `taxa_crit_excessiva` (aviso, `campo="crit_rate"`). `regen_insuficiente` removido.
  - Constante `LIMITE_TAXA_CRIT = 90.0` em `conjunto.py`.

Origem do valor por stat: `energy_regen` → `regen.informado` (origem `"tela"`) se não nulo, senão `regen.total`
(`"echos"`); os demais → atributo da tela resolvido com `resolve_stat(dados.stat_names, a.stat, a.percentual if
a.percentual is not None else False)` (origem `"tela"`), senão `None`. Nome que não resolve é ignorado (a tela tem
atributos que nenhuma meta usa).

Mensagens dos problemas (rótulo = primeiro alias do stat, como `contracts._rotulo`):
- `meta_abaixo`: `"{rótulo} {valor} abaixo da meta de {min}."`
- `regen_sobrando` (meta de Regen com veredito `acima`): `"Regen. de Energia {valor} passa do máximo da meta ({teto}): {sobra} sobrando, dá para trocar por dano."`
- `taxa_crit_excessiva` (Taxa CRIT da tela > 90): `"Taxa CRIT {valor} passa de 90%: com buffs de time (ex.: Guardiã da Costa) pode passar de 100%, e o excesso não rende."`

Migração de `data/characters.json` (script único no scratchpad, não versionado; grava com `gravar_perfis`), para cada
build (base e variantes):
- `status` contém `"o Game8 não cita meta de Regen. de Energia; ficou 100"` **e** valor 100 → sem meta; trocar esse
  trecho do status por `"sem meta de Regen. de Energia nas fontes"` (comparar a string inteira, não separar por `"; "`).
- Senão → `metas: [{"stat": "energy_regen", "min": <valor>, "tipo": "rotacao", "fonte": <fonte>}]`, `fonte = "prydwen"`
  para `Encore_Fusion_DPS`, `Lumi_Resonance_Skill_Sub_DPS`, `Taoqi_Tank_Sub_DPS`, `Verina_Full_Support` e as builds do
  commit `fix: set energy regen targets from prydwen where game8 has none` (`git show dcdd61f --stat` + diff), `"game8"`
  nas demais. Faixa, tipo `escala` e explicação vêm nas Tasks 9–14.
- Remover `regen_energia_min`. Conferir: `uv run wuwastats check-data` OK e contagem `77` builds.

- [ ] **Step 1: Write the failing tests** em `test_analyze.py` (substituem `test_avisa_regen_abaixo_do_minimo` e o
  `regen.atinge` de `test_soma_regen_de_echos_e_bonus_de_set`), table-driven onde couber:
  - `test_compara_regen_da_tela_antes_dos_echos`: Suoming_SubDPS (meta 120–130), `regen_total_informado=125` →
    `metas[0].origem == "tela"`, `veredito == "dentro"`; sem `regen_total_informado` → `origem == "echos"`, `valor == 145.2`, `veredito == "acima"`.
  - `test_aponta_problemas_das_metas` parametrizado por (build, mudança na entrada, código esperado/ausente):
    regen 108.4 (entrada do teste antigo) em Suoming_DPS → `meta_abaixo`; Suoming_SubDPS sem tela (145.2 > 130) →
    `regen_sobrando`; `atributos=[{"stat": "Taxa CRIT", "valor": 92}]` → `taxa_crit_excessiva`; `valor: 90` → ausente;
    `atributos` com Taxa CRIT 85 em Suoming_DPS (meta 60–80) → nenhum problema de meta (acima é informativo).
  - `test_resolve_hp_da_tela_sem_percentual`: perfil de teste com meta `hp_flat` min 50000 (via cópia de dados), `atributos=[{"stat": "HP", "valor": 48000}]` → `valor == 48000`, `veredito == "abaixo"`.
  - `test_meta_sem_valor_fica_so_de_referencia`: meta `crit_rate` sem tela → `valor is None`, `veredito is None`, sem problema.
  - `test_perfil_aplicado_traz_metas`: `analise.perfil.metas[1].stat == "crit_rate"`.
  - histórico: `AnaliseSalva.model_validate` de um JSON salvo sem `atributos` em `entrada` funciona.
  - `test_app.py`: trocar os usos de `regen_energia_min` (linhas ~382–425) por `metas`; erro de validação esperado
    passa a ser `body › metas › 0` (ex.: `{"stat": "energy_regen", "min": 50, ...}`).
  - `test_loader.py`: caso `_suoming("regen_energia_min", 90)` vira "campo desconhecido `regen_energia_min`" (extra forbid).
- [ ] **Step 2: Run** `uv run pytest` — Expected: FAIL nos testes novos.
- [ ] **Step 3: Implement** `_metas(entrada, regen, spec, dados) -> list[MetaAnalise]` e
  `_problemas_metas(metas, atributos_resolvidos) -> list[Problema]` em `conjunto.py`; remover `minimo`/`atinge`/
  `_problemas_regen` (o aviso `regen_divergente` fica); `perfil_aplicado` passa `metas`; remover `regen_energia_min` do
  schema/tabelas/loader/fixture.
- [ ] **Step 4: Migrate** `data/characters.json` com o script acima; `uv run wuwastats check-data`.
- [ ] **Step 5: Update** `docs/api.md` (exemplos e tabela de códigos).
- [ ] **Step 6: Run** `uv run pytest`, `uv run ruff check`, `grep -rn "regen_energia_min\|regen_insuficiente" src fixtures data/characters.json docs/api.md` — Expected: PASS, ruff limpo, grep vazio.
- [ ] **Step 7: Commit** `feat: compare stat targets with the character screen` (inclui dados migrados).

---

### Task 4: Captura e extração passam os atributos da tela para a entrada

**Files:**
- Modify: `src/wuwastats/vision/parse.py`, `src/wuwastats/captura/sessao.py` (`montar_entrada`),
  `src/wuwastats/vision/extract.py` (`_montar_entrada`)
- Test: `src/wuwastats/captura/test_sessao.py`, `src/wuwastats/vision/test_extract.py`

**Interfaces:**
- Consumes: `EntradaBuild.atributos` (Task 3).
- Produces: `def atributos_da_tela(leitura: LeituraPersonagem) -> tuple[StatLido, ...]` em `vision/parse.py`, usado pelos
  dois pontos de montagem.

- [ ] **Step 1: Write the failing tests** — `test_sessao.py`: sessão com `PersonagemLido` cujos `atributos` são
  `[{"stat": "Taxa CRIT", "valor": 62.5, "percentual": true}, {"stat": "HP", "valor": 15000}]` →
  `montar_entrada(...).atributos` tem os dois, na ordem; sem personagem → `()`. `test_extract.py`: mesmo para
  `_montar_entrada` via `extrair_build` com o extrator falso já usado nos testes.
- [ ] **Step 2: Run** `uv run pytest src/wuwastats/captura src/wuwastats/vision` — Expected: FAIL.
- [ ] **Step 3: Implement** `atributos_da_tela` e o campo `atributos=` nas duas montagens.
- [ ] **Step 4: Run** `uv run pytest` — Expected: PASS.
- [ ] **Step 5: Commit** `feat: send character screen attributes to the analysis`

---

### Task 5: Importador do Game8 grava a faixa de Regen

**Files:**
- Modify: `scripts/importar_builds_game8.py` (`meta_de_regen`, `montar_build`), `README.md` (seção do importador, "fica 100")
- Test: `scripts/test_importar_builds_game8.py`

**Interfaces:**
- Produces: `def faixa_de_regen(texto: str) -> tuple[int, int | None] | None` no lugar de `meta_de_regen` (mesmos
  padrões `META_DE_REGEN`; primeira meta citada; `"105–130%"` → `(105, 130)`; `"120%+"`/número único → `(120, None)`;
  números < 100 ignorados).
- `montar_build`: com faixa → `metas: [{"stat": "energy_regen", "min", "max"?, "tipo": "rotacao", "fonte": "game8"}]` e
  aviso `"conferir o tipo e escrever a explicação da meta de Regen. de Energia"`; sem faixa → sem `metas` e aviso
  `"sem meta de Regen. de Energia nas fontes"`. Nenhum aviso pode conter `"; "`.

- [ ] **Step 1: Write the failing tests** — converter `test_acha_a_meta_de_regen_no_texto` para `faixa_de_regen`
  mantendo os casos existentes e esperando tuplas (casos de faixa → `(min, max)`); linha ~79 passa a conferir
  `build.perfil["metas"] == [{"stat": "energy_regen", "min": 115, "tipo": "rotacao", "fonte": "game8"}]`;
  `test_sem_meta_de_regen_fica_100_com_todo` vira `test_sem_meta_de_regen_fica_sem_meta_com_todo` (`"metas" not in
  build.perfil`, status contém `"sem meta de Regen. de Energia nas fontes"`); `test_avisos_nao_contem_separador` (nenhum
  aviso com `"; "`).
- [ ] **Step 2: Run** `uv run pytest scripts` — Expected: FAIL.
- [ ] **Step 3: Implement**; remover `REGEN_PADRAO` se ficar sem uso; atualizar o README.
- [ ] **Step 4: Run** `uv run pytest` — Expected: PASS.
- [ ] **Step 5: Commit** `feat: import energy regen range from game8`

---

### Task 6: Página do personagem mostra as metas

**Files:**
- Modify: `web/comum.js` (helper compartilhado), `web/personagem.js` (`conteudoBuild`), `web/style.css` (se precisar de classe)

**Interfaces:**
- Consumes: `BuildResumo.base.metas` / `variantes[].perfil.metas` (Task 3).
- Produces (em `comum.js`, exportados): `faixaDaMeta(meta) -> string` (`"105–130%"`, `"120%+"`, `"50.000"` para
  `_flat`, `"250%"` para escala de número único); `ROTULO_TIPO_META = { escala: "Escala do kit", rotacao: "Rotação" }`;
  `ROTULO_FONTE = { game8: "Game8", prydwen: "Prydwen" }`.

Card "Metas de status" entre as tabelas e o `textoDaBuild`: uma linha por meta com rótulo do stat
(`rotulo.stat(meta.stat)`), faixa, chip do tipo, `explicacao` (se houver) e "fonte: Game8". Sem metas: linha muda
"Sem metas pesquisadas para esta build." Mesmo estilo de `tcard`/`linha()` já usado.

- [ ] **Step 1: Implement**.
- [ ] **Step 2: Verify** — `uv run wuwastats serve` (ou servidor já rodando + `POST /api/dados/recarregar` → 204), abrir
  `personagem.html?nome=Suoming` com a skill `claude-in-chrome`: card aparece com "110%" e "60–80%"; personagem com
  build sem meta mostra a frase de vazio; console sem erro (`read_console_messages`).
- [ ] **Step 3: Commit** `feat: show stat targets on the character page`

---

### Task 7: Análise mostra metas e veredito

**Files:**
- Modify: `web/analise.js` (`resumo`, linha da Regen ~324–340)

**Interfaces:**
- Consumes: `conjunto.metas`, `faixaDaMeta`, `ROTULO_FONTE` (Tasks 3 e 6).

Linha da Regen: sinal = meta de `energy_regen` (`null` sem meta; `veredito !== "abaixo"` com meta); trocar
`· mínimo X%` por `· meta {faixa} · {mensagem}` (ou `· sem meta` quando não há). Uma `linhaResumo` nova por meta que não
seja Regen: valor lido + mensagem, ou "só referência: falta o print da tela" quando `valor === null` (sinal `null`); a
explicação em texto mudo. Os avisos `regen_sobrando`/`taxa_crit_excessiva` já entram pela lista de problemas.

- [ ] **Step 1: Implement**.
- [ ] **Step 2: Verify** — no navegador, abrir uma análise salva (ou rodar `POST /api/analisar` com
  `fixtures/entradas/suoming_dps.json` pela página de captura) e conferir a linha da Regen e a de Taxa CRIT ("só
  referência" sem print); console sem erro. `grep -n "minimo\|atinge" web/analise.js` → vazio.
- [ ] **Step 3: Commit** `feat: show stat target verdicts in the analysis`

---

### Task 8: Editor de builds edita as metas

**Files:**
- Modify: `web/perfis.js` (`CAMPOS_VARIANTE`, `abrirNova`, `camposDeBuild`, novo `editorMetas(alvo, prefixo)`)

Trocar o campo "Regen mínima" por "Metas de status": uma linha por meta com `select` de stat (os 6 de `StatDeMeta`,
rotulados por `rotulo.stat`), `min`, `max` (vazio → `null`), `select` de tipo, `select` de fonte, `input` de explicação
(vazio → `null`), botão remover; botão "Adicionar meta" (padrão `{stat: "energy_regen", min: 100, max: null, tipo:
"rotacao", fonte: "game8", explicacao: null}`), não oferecendo stat já usado. Erros do servidor no prefixo
`${prefixo}metas` (padrão de `linha()`). `CAMPOS_VARIANTE`: `{ campo: "metas", rotulo: "Metas de status" }`.
`abrirNova`: `metas: []` no lugar de `regen_energia_min`.

- [ ] **Step 1: Implement**.
- [ ] **Step 2: Verify** no navegador, numa build de teste criada pelo editor (apagar depois; nunca salvar em cima de
  uma build com `descricao`): adicionar meta com máx. vazio → salvar → `GET /api/perfis` mostra sem `max`;
  máx. < mín. → erro aparece no campo; remover meta → salva sem ela. `grep -n regen_energia_min web/` → vazio.
- [ ] **Step 3: Commit** `feat: edit stat targets in the build editor`

---

### Tasks 9–14: Metas das 52 builds com `descricao` (um lote por task)

Processo de cada build (spec §6): Game8 bloco → Game8 página inteira → Prydwen (curl com user-agent de Chrome, HTML no
scratchpad, Python `-I`), aplicando as decisões 1–4 acima. Para cada build:
- **Regen**: faixa (`min`/`max`), `tipo` (`escala` só quando o kit converte até um teto: Guardiã da Costa 250, Mornye 260,
  Sigrika 125–150, Brant e outras só com texto da fonte que diga isso), `explicacao` de uma frase dizendo o que muda de
  uma ponta à outra (condição de sequência/time/rotação dentro dela), `fonte`.
- **Crítico**: `crit_rate` e `crit_dmg` quando alguma fonte dá número (Game8 primeiro); suporte sem número → sem meta,
  sem TODO.
- **HP/DEF**: só com limiar do kit ou número da fonte (Jingran 50.000 HP, `tipo: "escala"`).
- **status**: tirar o TODO de Regen resolvido; acrescentar `"sem meta de Regen. de Energia nas fontes"` /
  `"sem meta de crítico nas fontes"` (só DPS) quando faltar; nada de `"; "` dentro de um aviso.
- Dados já levantados na spec §5.1 entram direto (conferir a explicação). As 5 builds da §5.2 (Camellya, Hiyuki, Lucy,
  Aemeath, Buling) têm a faixa conferida e o status trocado (Aemeath e Buling não têm `descricao`, mas a correção do status
  entra no lote da Task 9).
- Dúvida que as decisões 1–4 não resolvem (fonte ambígua, número que parece errado, tipo incerto) → **perguntar ao
  usuário antes de gravar**.

Cada lote: pesquisar → gravar com `gravar_perfis` → `uv run wuwastats check-data` → `POST
http://127.0.0.1:8000/api/dados/recarregar` (→ 204) → conferir 2 builds na página do personagem → commit
`feat: add stat targets for <lote>` (ex.: `feat: add stat targets for suoming to camellya`).

- [ ] **Task 9:** Suoming_DPS, Suoming_SubDPS, Suoming_SubDPS_Nuvens, Hsin_DPS, Hsin_SubDPS, Shorekeeper_Suporte,
  Aalto_DPS_Support, Brant_Fusion_DPS, Camellya_Havoc_Main_DPS (+ status de Aemeath e Buling)
- [ ] **Task 10:** Cantarella_Havoc_Sub_DPS, Cantarella_Coordinated_ATK_Sub_DPS, Carlotta_Glacio_Main_DPS,
  Cartethyia_Aero_Erosion_DPS, Cartethyia_Aero_Erosion_DPS_w_o_Ciaccona, Changli_Fusion_DMG, Ciaccona_Aero_Erosion_Sub_DPS,
  Danjin_Havoc_DPS, Encore_Fusion_DPS
- [ ] **Task 11:** Hiyuki_Glacio_Chafe_DPS, Jianxin_Crowd_Control_Sub_DPS, Jingran_Fusion_HP_Heavy_Attack_DPS_w_Sig,
  Jingran_Fusion_HP_Heavy_Attack_DPS_w_o_Sig, Jinhsi_Burst_DPS, Jiyan_Liberation_DPS, Lingyang_Glacio_DPS,
  Lucilla_Glacio_Chafe_Sub_DPS, Lucilla_Echo_Skill_Buffer_Sub_DPS
- [ ] **Task 12:** Lumi_Resonance_Skill_Sub_DPS, Luuk_Herssen_Tune_Strain_Basic_ATK_DPS, Mornye_DEF_Based_Healer_Support,
  Mornye_Rejuvenating_Glow, Phoebe_Spectro_Frazzle_Sub_DPS, Phoebe_Spectro_Frazzle_DPS, Qingxiao_Aero_Tune_Strain_DPS,
  Roccia_Havoc_Sub_DPS
- [ ] **Task 13:** Rover_Electro_Electro_Flare_Sub_DPS, Rover_Electro_Negative_Status_Sub_DPS, Rover_Havoc_Burst_DPS,
  Sanhua_Basic_ATK_Sub_DPS, Sigrika_Echo_Skill_Aero_DPS, Taoqi_Tank_Sub_DPS, Verina_Full_Support,
  Yangyang_Xuanling_Havoc_Bane_DPS
- [ ] **Task 14:** Yinlin_Sub_DPS, Zani_Spectro_Frazzle_Main_DPS, Iuno_Aero_Sub_DPS, Phrolova_Havoc_DPS,
  Qiuyuan_Full_Echo_Sub_DPS, Qiuyuan_Hypercarry_Sub_DPS, Qiuyuan_Aero_Heavy_Attack_DMG_DPS, Lucy_Heavy_Attack_DMG_DPS,
  Rebecca_Heavy_Attack_Buffer_Sub_DPS

Depois deste plano (fora dele): textos + metas das 25 builds sem `descricao` (spec §5.4), no fluxo de textos de sempre.
Ao terminar, atualizar a memória `wuwastats-metas-de-status` (handoff concluído) e `wuwastats-textos-builds` (metas junto
com os textos).
