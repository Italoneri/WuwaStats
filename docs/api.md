# API WuwaStats

Contrato consumido pela interface. A página em `web/` é provisória e usa só o que está aqui.
O esquema OpenAPI completo (gerado do código) fica em `http://127.0.0.1:8000/docs` e `/openapi.json`.

```bash
uv run wuwastats serve            # http://127.0.0.1:8000
```

## Convenções

- JSON em UTF-8. Nomes de campo em português, `snake_case`.
- **Chaves internas** identificam status, sets e echos (`crit_dmg`, `Moonlit Clouds`, `Suhsin`).
  Para exibir, use o primeiro nome de `GET /api/catalogo` (`nomes[0]`), que é o nome do jogo em PT-BR quando cadastrado.
- Chaves terminadas em `_flat` são valores fixos; as demais são percentuais.
- **Índices** de echo (`indice`, `echos`) começam em 0 e seguem a ordem dos slots. O índice 0 é o echo principal.
- Números já vêm arredondados (1 ou 2 casas). Percentuais vêm sem o `%` (`17.4` = 17,4%).

### Erros

Todo erro (4xx/5xx) tem o mesmo formato:

```json
{ "mensagem": "build 'X' não existe em characters.json", "erros": ["Suoming_DPS", "Suoming_SubDPS"] }
```

| Status | Quando |
|---|---|
| 404 | build inexistente (`erros` lista as disponíveis), sessão de captura inexistente ou substituída |
| 409 | captura: atalho em uso por outro programa ou jogo como admin com o servidor sem admin, nenhum echo lido ainda |
| 422 | corpo inválido (`erros` aponta campo › motivo), alias inválido, dados de jogo inválidos |
| 501 | captura por atalho fora do Windows |
| 503 | IA de visão não configurada (`.env` sem `NVIDIA_API_KEY`/`NVIDIA_VISION_MODEL`) |

## Fluxo sugerido para a interface

1. `GET /api/personagens`, `GET /api/builds` e `GET /api/catalogo` ao abrir.
2. Prints: captura no servidor (`POST /api/captura/iniciar` + eventos) e `GET /api/captura/{sessao}/entrada`,
   ou upload manual → `POST /api/extrair`, que mostra `extracao.echos` (ok/falhou) e já desenha `analise`.
3. O usuário corrige qualquer valor na `extracao.entrada` → `POST /api/analisar` a cada mudança.
4. Se `analise.condicoes_pendentes` não for vazio, pergunte (ex.: "Está com a arma assinatura?") e reenvie com `condicoes`.
5. Para cada item de `analise.nomes_desconhecidos`, ofereça mapear para uma chave do catálogo → `POST /api/aliases` e reanalise.

---

## `GET /api/health`

`200 {"status": "ok"}`

## `GET /api/personagens`

Todos os ressonadores jogáveis (`data/resonators.json`, gerado pelo importador), em ordem alfabética da chave.

```json
[
  {
    "chave": "Suoming",
    "nome": "Suoming",
    "elemento": { "chave": "electro", "nome": "Voltaico" },
    "tipo_arma": { "chave": "sword", "nome": "Espada" },
    "raridade": 5,
    "builds": ["Suoming_DPS", "Suoming_SubDPS"],
    "tem_perfil": true
  }
]
```

- `chave`: nome em inglês; é o `personagem` de `/api/builds`. `nome`: nome PT-BR do jogo (o inglês se não houver).
- `elemento.chave` ∈ `glacio`, `fusion`, `electro`, `aero`, `spectro`, `havoc`.
  `tipo_arma.chave` ∈ `broadblade`, `sword`, `pistols`, `gauntlets`, `rectifier`.
- `tem_perfil: false` (e `builds: []`): o personagem ainda não tem build em `characters.json`.

## `GET /api/builds`

Lista de builds (perfis em `data/characters.json`).

```json
[
  {
    "chave": "Suoming_DPS",
    "personagem": "Suoming",
    "condicoes": ["arma_assinatura"],
    "armas": { "melhor": "Unspoken Rue", "alternativas": [] },
    "base": { "escala": "ATQ", "custos": [4,3,3,1,1], "sets": {}, "echo_principal": null,
              "principais": { "4": ["crit_dmg", "crit_rate"] }, "estrelas": { "crit_rate": 3 },
              "metas": [ { "stat": "energy_regen", "min": 110, "max": 125, "tipo": "rotacao", "fonte": "game8",
                           "explicacao": "110% com a rotação otimizada, 125% na simples." } ] },
    "variantes": [
      { "condicao": { "arma_assinatura": true }, "perfil": { "sets": { "Heart of Sworn Vigil": 5 }, "...": "..." } },
      { "condicao": { "arma_assinatura": false }, "perfil": { "sets": { "Moonlit Clouds": 5 }, "...": "..." } }
    ],
    "descricao": "Suoming é uma DPS **Electro** que tira a maior parte do dano do **Ataque Básico**. [...]"
  }
]
```

- `base` e `variantes[].perfil` têm o formato de `perfil` da **Analise**. O perfil da variante já vem completo
  (base + o que a variante sobrescreve).
- `condicoes`: chaves que a interface pode precisar perguntar. Hoje só existe `arma_assinatura` (booleano).
- `sets`: set → peças pedidas. Um set só: `{ "Heart of Sworn Vigil": 5 }`; combinação: `{ "Dream of the Lost": 3, "Havoc Eclipse": 2 }`; `{}` = set livre.
- `armas`: recomendação para a tela do personagem (não entra no cálculo); chaves de `catalogo.armas`.
  `null` se a build não define.
- `descricao`: explicação da build, mostrada abaixo das tabelas. Parágrafos separados por linha em branco (`\n\n`) e
  `**negrito**`; monte como texto, nunca como HTML. `null` se a build não tem.

## `GET /api/catalogo`

Tudo que a interface precisa para rótulos, seletores e validação visual.

```json
{
  "stats": [
    {
      "chave": "crit_dmg",
      "nomes": ["Dano CRIT", "Crit DMG", "CRIT DMG"],
      "percentual": true,
      "substatus": [12.6, 13.8, 15.0, 16.2, 17.4, 18.6, 19.8, 21.0],
      "principal": { "4": 44.0 }
    }
  ],
  "sets": [{ "chave": "Moonlit Clouds", "nomes": [], "pecas": 5 }],
  "echoes": [{ "chave": "Reminiscence: Suhsin the Inevitable", "nomes": ["Reminiscência: Suhsin, a Inevitável"], "custo": 4 }],
  "armas": [{ "chave": "Unspoken Rue", "nomes": ["Penumbra Abissal"], "tipo": "sword", "raridade": 5 }]
}
```

- `substatus`: valores discretos possíveis (posição no array = tier − 1); `null` se o status não existe como substatus.
- `principal`: valor máximo como status principal, por custo (`"1"`, `"3"`, `"4"`).

## `GET /api/echoes`

Todos os echos de `data/echoes.json`, em ordem alfabética da chave, com o que cada um faz. Usado pela página Echos.

```json
[
  {
    "chave": "Crownless",
    "nome": "Destronado",
    "custo": 4,
    "sets": [{ "chave": "Havoc Eclipse", "nome": "Eclipse Aniquilante" }],
    "habilidade": "Transforme-se em Destronado e realize até 4 ataques consecutivos. [...]

Recarga: 20 s"
  }
]
```

- `habilidade`: texto do jogo com os valores do nível mais alto, sem a marcação de estilo; PT-BR quando houver, senão
  inglês. Use `white-space: pre-line` para manter os parágrafos. `null` se os dados do jogo não trazem a descrição.

## `POST /api/analisar`

Corpo: **EntradaBuild**. Resposta: **Analise**.

### EntradaBuild

```json
{
  "build": "Suoming_DPS",
  "condicoes": { "arma_assinatura": false },
  "regen_externa": 0,
  "regen_total_informado": 145.2,
  "atributos": [ { "stat": "Taxa CRIT", "valor": 62.5, "percentual": true }, { "stat": "HP", "valor": 15000 } ],
  "echos": [
    {
      "nome": "Suhsin",
      "custo": 4,
      "set": "Moonlit Clouds",
      "principal": { "stat": "Dano CRIT", "valor": 44 },
      "substatus": [
        { "stat": "Taxa CRIT", "valor": 8.1 },
        { "stat": "ATQ", "valor": 50, "percentual": false }
      ]
    }
  ]
}
```

| Campo | Tipo | Notas |
|---|---|---|
| `build` | string | chave de `/api/builds` |
| `condicoes` | objeto | opcional; ausente/`null` = desconhecido (vira pendente) |
| `regen_externa` | número | Regen. de Energia de arma, cadeia etc. Padrão 0 |
| `regen_total_informado` | número \| null | Regen total da tela do personagem; quando há, é ela que se compara com a meta de Regen |
| `atributos` | lista | opcional; atributos totais da tela do personagem (nomes como lidos). Sem `percentual`, conta como valor fixo (`HP` = HP total) |
| `echos` | 1 a 5 | ordem dos slots |
| `echos[].nome`, `set` | string \| null | qualquer nome cadastrado (PT-BR, inglês ou chave) |
| `echos[].custo` | 1 \| 3 \| 4 | |
| `stat` | string | nome do jogo, alias ou chave interna |
| `percentual` | bool \| null | só necessário para nomes ambíguos (`ATQ`, `HP`, `DEF`) |

Campos extras são rejeitados (422).

### Analise

```json
{
  "build": "Suoming_DPS",
  "personagem": "Suoming",
  "variante": 1,
  "condicoes_pendentes": [],
  "perfil": { "escala": "ATQ", "custos": [4,3,3,1,1], "sets": { "Moonlit Clouds": 5 },
              "echo_principal": null, "principais": { "4": ["crit_dmg", "crit_rate"] }, "estrelas": { "crit_rate": 3 },
              "metas": [ /* MetaDeStatus */ ] },
  "echos": [ /* EchoAnalise */ ],
  "conjunto": { /* ConjuntoAnalise */ },
  "candidatos_troca": [ { "indice": 4, "nome": null, "score_pct": 6.3, "nota": "C", "motivos": ["Principal hp_pct; a build pede atk_pct no custo 1.", "Score 6.3%."] } ],
  "nomes_desconhecidos": [ { "categoria": "sets", "nome_lido": "Nuvens ao Luar", "echos": [0, 1] } ],
  "revisao": false
}
```

| Campo | Significado |
|---|---|
| `variante` | índice da variante aplicada; `null` = perfil base |
| `condicoes_pendentes` | condições que faltam para escolher a variante (enquanto isso vale o perfil base) |
| `perfil` | build efetivamente aplicada (base + variante), com chaves internas |
| `candidatos_troca` | **todos** os echos, do pior para o melhor: primeiro quem foge da build, depois menor score |
| `nomes_desconhecidos` | nomes fora do dicionário, agrupados; `categoria` ∈ `stats`, `echoes`, `sets` |
| `revisao` | `true` se algum echo ou o conjunto tem problema de severidade `revisao` |

#### EchoAnalise

```json
{
  "indice": 0,
  "nome": "Suhsin", "nome_lido": "Suhsin",
  "custo": 4,
  "set": "Moonlit Clouds", "set_lido": "Moonlit Clouds",
  "principal": { "stat": "crit_dmg", "stat_lido": "Dano CRIT", "valor": 44.0, "valor_esperado": 44.0,
                 "valido_para_custo": true, "recomendado": true },
  "substatus": [ /* Substat */ ],
  "score_pct": 80.4,
  "nota": "SS",
  "cv": 33.6,
  "revisao": false,
  "problemas": [ /* Problema */ ]
}
```

- `nome`/`set` resolvidos (chave interna) ou `null` se desconhecidos; `*_lido` é o texto original.
- `principal.valor_esperado`: valor no nível máximo para o custo; `null` se o status não pode ser principal nesse custo.
- `principal.recomendado`: se está entre os principais pedidos pela build (`null` = build não define para esse custo).
- `score_pct` (0–100): `Σ peso × valor/máximo` dos substatus ÷ melhor caso possível da build (5 maiores pesos no máximo).
  O peso de cada substatus é `estrelas ÷ 3` (`perfil.estrelas`); sem estrela, 0. O mesmo echo tem scores diferentes em builds diferentes. O principal não entra no score.
- `nota`: faixa de `score_pct` definida em `data/notas.json` (hoje SSS, SS, S, A, B, C).
- `cv`: Crit Value dos substatus = `2 × Taxa CRIT + Dano CRIT`.

#### Substat (união discriminada por `tipo`)

```json
{ "tipo": "valido", "stat": "crit_dmg", "stat_lido": "Dano CRIT",
  "valor_lido": 17.5, "valor": 17.4, "diferenca": 0.1, "dentro_tolerancia": true,
  "min": 12.6, "max": 21.0, "posicao_pct": 57.1, "tier": 5, "tiers_total": 8,
  "peso": 1.0, "pontos": 0.8286 }
```

```json
{ "tipo": "invalido", "stat_lido": "Sorte", "valor_lido": 50, "motivo": "desconhecido" }
```

- `valor` é o valor válido mais próximo (use ele nas barras); `valor_lido` é o que veio na entrada.
- `posicao_pct`: posição de `valor` entre `min` (0) e `max` (100).
- `tier`: posição de `valor` entre os valores discretos (1 = mínimo, `tiers_total` = máximo).
- `motivo` do inválido: `desconhecido` (nome fora do dicionário) ou `nao_e_substatus` (ex.: Dano Elétrico).

#### ConjuntoAnalise

```json
{
  "cv": 114.6, "cv_com_principal": 158.6, "score_medio_pct": 42.6, "nota_media": "B",
  "regen": { "base": 100, "echos": 35.2, "sets": 10, "externa": 0, "total": 145.2,
             "informado": null, "diferenca_informado": null },
  "custos": { "esperado": [4,3,3,1,1], "atual": [4,3,3,1,1], "ok": true },
  "set": { "pedidos": [ { "set": "Moonlit Clouds", "pecas_necessarias": 5, "pecas_equipadas": 5, "ok": true } ], "ok": true,
           "bonus_ativos": [ { "set": "Moonlit Clouds", "pecas": 2, "stats": { "energy_regen": 10.0 } } ] },
  "echo_principal": { "esperado": null, "atual": "Suhsin", "ok": null },
  "metas": [
    { "meta": { "stat": "energy_regen", "min": 110, "max": 125, "tipo": "rotacao", "fonte": "game8", "explicacao": "..." },
      "valor": 145.2, "origem": "echos", "veredito": "acima", "mensagem": "acima da faixa, 20.2% sobrando" },
    { "meta": { "stat": "crit_rate", "min": 60, "max": 80, "tipo": "rotacao", "fonte": "prydwen", "explicacao": null },
      "valor": null, "origem": null, "veredito": null, "mensagem": null }
  ],
  "problemas": []
}
```

- `metas[]`: uma por meta da build. `valor` da Regen = `regen.informado` (origem `tela`) ou `regen.total` (`echos`);
  dos outros stats, o atributo da tela (`tela`) ou `null` sem print (meta só de referência).
- `veredito`: `abaixo` | `dentro` | `acima` | `null`. Na `rotacao`, bater a faixa basta; na `escala` (o kit converte até um
  teto = `max`, ou `min` sem `max`), `acima` quer dizer "no teto".

- `regen.total = base + echos (principal + substatus) + sets (bônus ativos) + externa`.
- `regen.diferenca_informado = informado − total` (positivo: a tela mostra mais do que o calculado).
- `set.ok`/`echo_principal.ok`: `null` quando não há o que conferir (build sem set definido, peças desconhecidas).

#### Problema

```json
{ "codigo": "valor_fora_tolerancia", "severidade": "revisao", "mensagem": "crit_dmg: lido 25.0, valor válido mais próximo 21.0.", "campo": "substatus[1]" }
```

`campo` aponta o local na entrada (`nome`, `set`, `custo`, `principal`, `substatus[i]`, `substatus`, `regen`, `custos`, `echo_principal`)
ou o stat da meta (`energy_regen`, `crit_rate`, …).

| Severidade | Significado para a interface |
|---|---|
| `revisao` | leitura provavelmente errada: destacar e pedir correção |
| `mapeamento` | nome fora do dicionário: oferecer mapeamento |
| `build` | leitura ok, mas foge da build |
| `aviso` | informativo |

| Código | Severidade | Nível |
|---|---|---|
| `stat_desconhecido` | revisao | echo |
| `stat_nao_e_substatus` | revisao | echo |
| `valor_fora_tolerancia` | revisao | echo |
| `substat_duplicado` | revisao | echo |
| `excesso_substatus` | revisao | echo |
| `principal_invalido_para_custo` | revisao | echo |
| `custo_divergente` | revisao | echo |
| `custo_total_excedido` | revisao | conjunto |
| `nome_desconhecido` | mapeamento | echo |
| `set_desconhecido` | mapeamento | echo |
| `principal_fora_da_build` | build | echo |
| `set_fora_da_build` | build | echo |
| `custos_fora_da_build` | build | conjunto |
| `set_incompleto` | build | conjunto |
| `echo_principal_fora_da_build` | build | conjunto |
| `meta_abaixo` | build | conjunto |
| `principal_valor_divergente` | aviso | echo |
| `regen_divergente` | aviso | conjunto |
| `regen_sobrando` | aviso | conjunto (Regen acima do máximo/teto da meta) |
| `taxa_crit_excessiva` | aviso | conjunto (Taxa CRIT da tela acima de 90%) |

## `POST /api/extrair`

`multipart/form-data`. Lê os prints com a IA de visão e já devolve a análise.

| Campo | Tipo | Notas |
|---|---|---|
| `build` | texto | obrigatório |
| `echos` | arquivo (repetido) | 1 a 5 prints, na ordem dos slots; PNG, JPEG ou WebP; até 15 MB cada |
| `personagem` | arquivo | opcional; tela de atributos (arma + Regen total) |
| `arma_assinatura` | `sim` \| `nao` | opcional; sobrescreve o que for detectado |
| `regen_externa` | número | opcional, padrão 0 |

Resposta:

```json
{
  "extracao": {
    "entrada": { /* EntradaBuild só com os echos lidos; null se nenhum foi lido */ },
    "echos": [
      { "tipo": "ok", "arquivo": "1.png", "do_cache": false, "echo": { /* echo da EntradaBuild */ } },
      { "tipo": "falhou", "arquivo": "2.png", "do_cache": true, "motivo": "a resposta não contém um objeto JSON",
        "resposta_bruta": "Não consegui ler." }
    ],
    "personagem": { "tipo": "ok", "arquivo": "personagem.png", "do_cache": false,
                    "leitura": { "personagem": "Suoming", "nivel": 90, "arma": "Penumbra Abissal", "arma_nivel": 90,
                                 "arma_rank": 1, "regen_energia_total": 131.2,
                                 "atributos": [ { "stat": "HP", "valor": 13245, "percentual": false },
                                                { "stat": "Dano CRIT", "valor": 273.2, "percentual": true } ] } }
  },
  "analise": { /* Analise dos echos lidos; null se nenhum */ }
}
```

- `extracao.echos[i]` corresponde ao i-ésimo arquivo enviado (`arquivo` é `1.png`, `2.png`... no servidor).
- Echos que falharam **não** entram em `entrada`: a interface deve permitir preenchê-los à mão e reanalisar.
- `do_cache`: a resposta veio do cache (sem gastar crédito da API).
- `leitura.atributos`: atributos totais da tela, na ordem e com o nome como aparecem no jogo (só para exibição).
  Campos que a IA não conseguiu ler vêm `null` (`[]` em `atributos`).
- Com o print do personagem, `entrada.condicoes.arma_assinatura` é detectada comparando a arma lida com `armas_assinatura` da build, e `entrada.regen_total_informado` vem da tela.

## Captura no servidor

O servidor escuta três atalhos globais enquanto uma sessão estiver ativa (padrão F8 = echo, F9 = tela do personagem,
F10 = ir para a análise; configuráveis no `.env` com `CAPTURA_TECLA_ECHO`, `CAPTURA_TECLA_PERSONAGEM` e
`CAPTURA_TECLA_ANALISE`, ex.: `Win+Shift+E`) e lê cada print com a IA assim que ele chega. Uma sessão por vez: iniciar outra encerra a anterior. Só Windows (fora dele, `iniciar` responde 501).

### Sessao

Resposta de todos os endpoints abaixo que mudam ou consultam a sessão.

```json
{
  "id": "9450ce4e9406",
  "build": "Suoming_DPS",
  "ativa": true,
  "echos": [
    { "estado": "lido", "captura": 1, "do_cache": false, "echo": { /* echo da EntradaBuild */ } },
    { "estado": "falhou", "captura": 2, "motivo": "a resposta não contém um objeto JSON" },
    { "estado": "lendo", "captura": 3 },
    { "estado": "recebido", "captura": 4 },
    { "estado": "vazio" }
  ],
  "personagem": { "estado": "lido", "captura": 5, "do_cache": true, "leitura": { /* leitura de /api/extrair */ } },
  "alvo_f8": null,
  "ultima_captura": 5
}
```

- `echos`: sempre 5 espaços, na ordem dos slots (o 0 é o echo principal). `estado` ∈ `vazio`, `recebido` (na fila),
  `lendo`, `lido`, `falhou`.
- `captura`: número do print na sessão. A leitura acha o espaço por ele, então reordenar ou esvaziar durante a leitura é seguro
  (a leitura de um print removido é descartada).
- `alvo_f8`: espaço marcado com "Refazer". Sem marca, o F8 vai para o primeiro espaço vazio; com os 5 ocupados, vira
  `erro_captura`.

### `GET /api/captura/teclas`

Atalhos configurados, para a página mostrar as teclas certas: `{ "echo": "F8", "personagem": "F9", "analise": "F10" }`.

### `POST /api/captura/iniciar`

Corpo `{ "build": "Suoming_DPS" }`. Liga os atalhos e devolve a **Sessao** nova. `404` build inexistente,
`409` atalho em uso por outro programa ou jogo rodando como administrador com o servidor sem admin, `501` fora do Windows, `503` IA não configurada.

### `POST /api/captura/parar`

Solta os atalhos e encerra a sessão (ela continua consultável, com `ativa: false`). Os prints continuam disponíveis
até iniciar outra sessão ou o servidor desligar. `204`.

### `GET /api/captura/{sessao}`

A **Sessao** atual. `404` se não existe ou foi substituída.

### `GET /api/captura/{sessao}/eventos`

`text/event-stream` (SSE). O primeiro evento é `estado`; com a sessão encerrada vem `encerrada` em seguida e o stream fecha.
A cada 15 s sem eventos chega um comentário `: ping`.

```
event: lido
data: {"tipo": "lido", "espaco": 0, "nome": "Suhsin", "principal": {"stat": "Dano CRIT", "valor": 44, "percentual": true},
       "motivo": null, "sessao": { /* Sessao */ }}
```

Todo evento traz a **Sessao** completa depois da mudança: basta redesenhar a partir dela.

| `tipo` | Quando | Campos |
|---|---|---|
| `estado` | ao conectar e depois de reordenar, esvaziar ou refazer | — |
| `print_recebido` | F8/F9 salvou o print | `espaco` |
| `leitura_iniciada` | a IA começou a ler | `espaco` |
| `lido` | leitura ok | `espaco`, `nome` (echo ou personagem), `principal` (só echo) |
| `falhou` | leitura falhou | `espaco`, `motivo` |
| `erro_captura` | o print nem foi tirado (jogo fora de foco, espaços cheios...) | `motivo` |
| `ir_para_analise` | atalho de análise pressionado | — |
| `encerrada` | sessão parada ou substituída; o stream fecha | — |

`espaco` é o índice do echo (0–4) ou `"personagem"`.

### `POST /api/captura/{sessao}/reordenar`

Corpo `{ "ordem": [1, 0, 2, 3, 4] }`: `ordem[j]` é o índice atual do espaço que vai para a posição `j`
(o exemplo troca os dois primeiros). A marca de "Refazer" acompanha o espaço. `422` se não for uma permutação de 0 a 4.

### `DELETE /api/captura/{sessao}/echos/{indice}` e `DELETE /api/captura/{sessao}/personagem`

Esvaziam o espaço. Devolvem a **Sessao**.

### `POST /api/captura/{sessao}/echos/{indice}/refazer`

Marca o espaço como destino do próximo F8 (o print atual fica até lá). Devolve a **Sessao**.

### `GET /api/captura/{sessao}/imagens/{espaco}`

O print (PNG) que está no espaço: `0` a `4` ou `personagem`. `404` se o espaço está vazio ou o print já foi apagado.
O mesmo espaço muda de print (Refazer, reordenar): acrescente `?captura=N` (o número da captura no espaço) para o
cache do navegador não mostrar o antigo.

### `GET /api/captura/{sessao}/entrada`

**EntradaBuild** montada da sessão: só os echos lidos, na ordem dos espaços; `condicoes.arma_assinatura` e
`regen_total_informado` vêm da tela do personagem, se lida. Os que falharam devem ser preenchidos na análise.
`409` se nenhum echo foi lido.

## Editor de builds

Edita os perfis de `data/characters.json`. O editor usa **chaves internas** (`crit_rate`, `Moonlit Clouds`,
`Unspoken Rue`): sem ambiguidade de idioma nem de ATQ/ATQ%. Nomes em PT continuam aceitos no `PUT`.

### `GET /api/perfis`

`{ "<chave da build>": PerfilRaw }`, no formato do arquivo, com os nomes trocados pelas chaves. Campos ausentes não
aparecem; numa variante, campo presente = substitui o da base.

### `PUT /api/perfis/{chave}`

Corpo: o perfil (mesmo formato). Cria ou substitui a build `chave` (letras, números, `_` ou `-`). O servidor valida o
`characters.json` inteiro com o loader numa cópia dos dados. Se passar, copia o arquivo anterior para
`data/backups/characters-<data>.json`, grava de forma atômica, recarrega os dados e devolve o perfil salvo.
`422` com `erros` (`characters.json › <chave> › estrelas › X: motivo` ou `body › metas › 0: motivo`); nesse caso
nada é gravado.

### `DELETE /api/perfis/{chave}`

Apaga a build, com o mesmo backup e validação. `204`; `404` se não existe.

## Análises salvas

Entradas corrigidas guardadas para reabrir depois e comparar o antes e o depois de trocar um echo, em
`data/historico/<id>.json`. Guarda a **entrada**, não o resultado: ao reabrir, rode `POST /api/analisar` com ela
(as estrelas atuais da build valem). `score_medio_pct`/`nota_media` são os do momento em que foi salva, só para a lista.

### `POST /api/historico`

```json
{ "nome": "antes de trocar o echo 5", "entrada": { /* EntradaBuild */ }, "leitura": { /* leitura da tela do personagem, opcional */ } }
```

`201` com o **ResumoAnaliseSalva**. `nome` vazio vira "<build> · dd/mm hh:mm". `404` se a build não existe.

```json
{ "id": "20261030-193000-a1b2c3", "nome": "antes de trocar o echo 5", "build": "Suoming_DPS",
  "criado_em": "2026-10-30T19:30:00-03:00", "score_medio_pct": 42.6, "nota_media": "B" }
```

### `GET /api/historico?build=Suoming_DPS`

Lista de **ResumoAnaliseSalva**, mais recentes primeiro. Sem `build`, todas.

### `GET /api/historico/{id}` e `DELETE /api/historico/{id}`

O resumo + `entrada` + `leitura`; ou apaga (`204`). `404` se não existe.

## Imagens do catálogo

Imagens de personagens, echos, armas e sets (enviadas pelo usuário ou baixadas pelo importador), em `data/imagens/<categoria>/<chave>.png`.
`categoria` ∈ `personagens`, `echoes`, `armas`, `sets`; `chave` é a chave do catálogo (`Suoming`,
`Reminiscence: Suhsin the Inevitable`, `Unspoken Rue`), codificada na URL. Chave fora do catálogo: `404`.

### `GET /api/imagens`

Quais chaves têm imagem: `{ "personagens": ["Suoming"], "echoes": [], "armas": [], "sets": [] }`. As outras usam placeholder.

### `GET /api/imagens/{categoria}/{chave}`

A imagem (PNG). `404` se não há imagem. Vem com `Cache-Control: no-cache`, então o navegador revalida depois de uma troca.

### `PUT /api/imagens/{categoria}/{chave}`

`multipart/form-data` com `arquivo`: PNG, JPEG ou WebP, até 5 MB. A imagem é regravada como PNG, com no máximo
1024 px no maior lado. Substitui a anterior. `204`; `422` se o arquivo não é uma imagem aceita.

## Fanarts

Fanart do banner da tela do personagem, com o crédito do artista, em `data/imagens/fanarts/<chave>.webp` + `.json`.
A galeria continua com a foto padrão de `/api/imagens/personagens`; sem fanart, o banner usa essa foto. `chave` fora
dos ressonadores: `404`.

### `GET /api/fanarts`

Crédito e enquadramento de quem tem fanart:
`{ "Aemeath": { "artista": "@fulano", "link": "https://www.pixiv.net/artworks/1", "enquadramento": { "x": 50, "y": 12, "zoom": 1.3 } } }`.
`x`/`y` são o ponto focal em % (`object-position`) e `zoom` amplia a partir desse ponto, sobre o recorte que já cobre
o banner. Fanarts gravadas antes do enquadramento voltam com o padrão `{ "x": 50, "y": 25, "zoom": 1 }`.

### `GET /api/fanarts/{chave}`

A imagem (WebP, `Cache-Control: no-cache`). `404` se não há fanart.

### `PUT /api/fanarts/{chave}`

`multipart/form-data` com `artista` (1 a 80 caracteres), `link` (opcional, só `http://`/`https://`) e `arquivo` (PNG,
JPEG ou WebP até 15 MB, regravado como WebP com no máximo 1920 px no maior lado), mais o enquadramento: `posicao_x` e
`posicao_y` (0 a 100, padrão 50 e 25) e `zoom` (1 a 3, padrão 1). Sem `arquivo`, troca só o crédito e o enquadramento
da fanart que já existe. `204`; `422` se a imagem ou o crédito é inválido, ou se falta a imagem na primeira vez.

## `POST /api/aliases`

Mapeia um nome lido para uma chave e grava em `data/stat_aliases.json`. Idempotente.

```json
{ "categoria": "sets", "chave": "Moonlit Clouds", "alias": "Nuvens ao Luar" }
```

`204` sem corpo. `422` se a chave não existe, o alias está vazio ou já aponta para outra chave.

## `POST /api/dados/recarregar`

Relê `data/*.json` depois de edição manual. `204` se ok; `422` com a lista de erros (arquivo › campo: motivo)
se algo estiver inválido. Nesse caso o servidor mantém os dados anteriores.
