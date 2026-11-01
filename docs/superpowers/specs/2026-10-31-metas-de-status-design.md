# Metas de status por build (Regen, crítico, HP…) — design e passagem de bastão

Data: 2026-10-31. Documento para continuar o trabalho em outro chat. Tudo o que está como **decidido** foi dito pelo
usuário; o que está como **palpite** ou **pendente** ainda precisa de confirmação dele antes de virar código.

## 1. Por que

Hoje cada build tem um número só, `regen_energia_min`, e o importador do Game8 grava o **menor** número da faixa
("105–130%" vira 105). O usuário acha isso errado: a faixa existe por um motivo, e o app deve mostrar esse motivo.
O objetivo do app é **dar um norte** para quem monta o personagem. O usuário tem uma regra pessoal (70% de Taxa CRIT /
270% de Dano CRIT) que usa quando não tem número nenhum, mas o app deve trazer o número **de cada personagem, caso a
caso**, pesquisado nas fontes.

## 2. O que foi decidido

1. **Metas de status por build.** Cada build passa a ter uma lista de metas. Cada meta tem:
   - `stat`: chave interna (`energy_regen`, `crit_rate`, `crit_dmg`, `hp`, `def`…);
   - faixa: mínimo e, se houver, máximo (ex.: 105–130);
   - **tipo do motivo**:
     - `escala`: o kit converte o status em dano/buff até um teto (Guardiã da Costa 250% Regen, Mornye 260% Regen,
       Sigrika 150% Regen, Jingran 50.000 HP). Abaixo do teto o personagem perde poder;
     - `rotacao`: o valor serve para ter a Liberação pronta toda rotação; a faixa vem do contexto (tipo de rotação,
       time, sequência). Bater o valor do seu contexto basta; acima disso é status sobrando;
   - **explicação curta** (uma frase, PT-BR, palavras próprias) dizendo o que muda de uma ponta à outra da faixa.
     Ex.: "105% na rotação otimizada, 130% na rotação simples". **Não** deve ser complexa;
   - **fonte**: `game8`, `prydwen`, … (para o usuário saber de onde veio).
2. **Metas são por build, não por personagem**: a Regen muda entre builds do mesmo personagem (Jingran com/sem
   assinatura, Qiuyuan).
3. **Crítico**: pesquisar Taxa CRIT e Dano CRIT de cada personagem. A regra 70/270 do usuário **não** é dado do app.
4. **HP / DEF**: entram quando o kit tem limiar (Jingran 50.000 HP) ou a fonte dá número.
5. **Comparação na análise** usando a **tela do personagem**. A extração por visão já lê todos os atributos totais
   (`LeituraPersonagem.atributos` em `src/wuwastats/vision/parse.py`: HP, ATQ, DEF, Taxa CRIT, Dano CRIT, Regen…), mas
   hoje só `regen_energia_total` é usado (`captura/sessao.py:montar_entrada`, `vision/extract.py`); o resto é
   descartado. A análise deve comparar cada meta com o atributo lido e dizer **abaixo / dentro / acima**. A Regen
   continua tendo também a conta pelos echos (`domain/conjunto.py:_regen`). Sem print da tela, as metas que não sejam
   Regen aparecem só como referência.
6. **Página do personagem** (`web/personagem.js`) mostra as metas de cada build (faixa + porquê + fonte).
7. **Aba de kit com comentários detalhados**: o usuário vai fazer **depois**. Fora do escopo agora. O texto das metas
   fica curto; o detalhe vai para essa aba futura.
8. **Ordem do trabalho**: primeiro implementar as metas e preencher as **52 builds que já têm `descricao`**; só depois
   continuar os textos das **25 que faltam** (já preenchendo as metas junto).

## 3. Pendente (perguntar ao usuário antes de implementar)

1. **Game8 × Prydwen discordam: qual vale?** Ex.: Iuno, Regen 120–125% (Game8) e crítico 70–80% / 250%+ (Game8).
   As builds seguem o Game8 (o usuário confia nele); o Prydwen é a fonte que mais traz crítico. Última pergunta feita,
   ainda sem resposta.
2. **Sem número em nenhuma fonte**: deixar sem meta com `status: "TODO"` (regra do projeto: não inventar dado de jogo)
   ou mostrar a regra 70/270 rotulada como "regra geral"? Palpite: TODO.
3. **Suportes** (Verina, Guardiã da Costa, Baizhi…): palpite = sem meta de crítico, a menos que a fonte dê. Não confirmado.
4. **Veredito de "escala" acima do máximo**: palpite = "no teto, o que passar sobra"; "dentro da faixa" = "rendendo,
   falta X% para o teto". Confirmar o texto.
5. **Condição da faixa** (ex.: Taoqi 126% antes da S5, 100% na S5; Jianxin 140% na S0): só texto na explicação, ou um
   campo de condição ligado às `variantes`/`condicoes` que já existem (sequência, arma assinatura)? Palpite: só texto
   por enquanto.

## 4. Impacto no código (mapa do que toca hoje `regen_energia_min`)

- Schema/validação: `src/wuwastats/gamedata/schemas.py` (`BuildSpecRaw.regen_energia_min`, `VarianteRaw`, `PerfilRaw`).
- Carga: `src/wuwastats/gamedata/loader.py` (≈ linhas 203–244).
- Domínio: `domain/tables.py` (`BuildSpec`), `domain/conjunto.py` (`_regen`, `RegenAnalise.minimo/atinge`),
  `domain/report.py` (`PerfilAplicado`), `domain/analyze.py`.
- API: `api/contracts.py`, `api/app.py`, testes em `api/test_app.py` (vários usam `regen_energia_min`), `docs/api.md`.
- Front: `web/analise.js` (bloco da Regen ≈ linha 324; comparação antes/depois ≈ 783), `web/perfis.js` (editor de
  perfil, campo "Regen mínima"), `web/personagem.js` (página do personagem; hoje só mostra `descricao`).
- Importador: `scripts/importar_builds_game8.py` (`meta_de_regen` devolve só o menor número; mudar para faixa) e
  `scripts/test_importar_builds_game8.py`.
- Dados: `data/characters.json` (77 builds) e `fixtures/gamedata/characters.json`.
- README (seção do importador cita "fica 100").

Decisão de modelagem ainda livre: manter `regen_energia_min` como derivado (mínimo da meta de Regen) para não quebrar
a análise atual, ou migrar tudo. Regras do usuário: tipos fortes, sem `any`, discriminated unions, validar na borda,
testes table-driven, funções puras no domínio (ver `~/.claude/CLAUDE.md`).

## 5. Dados: o que já se sabe

### 5.1 Metas de Regen corrigidas nesta sessão (hoje gravadas como número único)

| Build | Gravado | Faixa / detalhe da fonte | Fonte |
|---|---|---|---|
| `Sanhua_Basic_ATK_Sub_DPS` | 120 | "120%+" (seção de combo, fora do bloco) | Game8 |
| `Jingran_Fusion_HP_Heavy_Attack_DPS_w_o_Sig` | 125 | 125% vem do bloco **com** assinatura; o bloco sem assinatura não cita | Game8 (dedução) |
| `Mornye_Rejuvenating_Glow` | 260 | limiares do kit (Interfered Marker +40% dano recebido; Critical Protocol crítico da Liberação), citados no bloco do Halo | Game8 |
| `Rover_Electro_Negative_Status_Sub_DPS` | 120 | "igual à build Electro Flare" | Game8 |
| `Encore_Fusion_DPS` | 105 | **105–130%** (otimizada × simples) | Prydwen |
| `Lumi_Resonance_Skill_Sub_DPS` | 142 | **142–150%** (Carlotta+Guardiã × Phrolova+Guardiã) | Prydwen |
| `Taoqi_Tank_Sub_DPS` | 126 | **100–126%**: 126 antes da S5; S5 com Nuvens Enluaradas não precisa | Prydwen |
| `Verina_Full_Support` | 220 | **220–230%**; ~200% se a habilidade acertar o inimigo | Prydwen |

Outras faixas conhecidas: Iuno 120–125% (Game8); Mornye 260% (escala); Guardiã da Costa 250% (escala);
Sigrika 150% (escala: +2% Dano de Hab. de Eco por 1% acima de 125%); Jianxin ~140% na S0 (rotação lenta).

Metas de crítico já vistas: Iuno 70–80% Taxa / 250%+ Dano (Game8); Prydwen Encore 60–75% / 215–285%, Lumi 65%+ /
210%+, Taoqi 60–80% / 210–260%, Verina 60%+ / 210%+ (dano próprio irrelevante). HP: Jingran 50.000 (escala do kit).

### 5.2 Inconsistência a corrigir

Estas builds têm Regen ≠ 100 mas o `status` ainda diz "o Game8 não cita meta de Regen. de Energia; ficou 100"
(sobra de correção antiga; provável bug de separar o status por `"; "`, já que o próprio aviso contém `"; "`):
`Camellya_Havoc_Main_DPS` (115), `Hiyuki_Glacio_Chafe_DPS` (120), `Lucy_Heavy_Attack_DMG_DPS` (120),
`Aemeath_Tune_Rupture_Fusion_Burst_DPS` (120), `Buling_Full_Healer_Support` (150). Conferir a faixa e trocar o status.

### 5.3 Builds com `descricao` (52) — retrofit das metas primeiro

Ainda com TODO de Regen (pesquisar Game8 na página inteira, depois Prydwen): Aalto, Cantarella (2), Cartethyia sem
Ciaccona, Ciaccona, Danjin, Jinhsi, Jiyan, Lingyang, Lucilla (2), Phoebe DPS, Rover: Havoc, Phrolova, Qiuyuan Aero
Heavy Attack + os 3 da seção 5.2 (Camellya, Hiyuki, Lucy).

Com Regen já ok (falta faixa + crítico + HP/DEF se houver): Suoming (3), Hsin (2), Guardiã da Costa, Brant, Carlotta,
Cartethyia, Changli, Encore, Jianxin, Jingran (2), Lumi, Luuk Herssen, Mornye (2), Phoebe Sub, Qingxiao, Roccia,
Rover: Electro (2), Sanhua, Sigrika, Taoqi, Verina, Yangyang: Xuanling, Yinlin, Zani, Iuno, Qiuyuan (2), Rebecca.

As builds feitas à mão (`Suoming_*`, `Hsin_*`, `Shorekeeper_Suporte`) têm chaves que não batem com `chave_da_build`
do importador.

### 5.4 Builds sem `descricao` (25) — depois

Aemeath, Baizhi, Buling, Calcharo, Chixia, Denia (3), Lupa, Lynae (2), Mortefi, Rover: Aero (2), Rover: Spectro,
Suisui, Xiangli Yao, Yangyang, Youhu, Yuanwu, Zhezhi, Augusta, Chisa (2), Galbrena.

## 6. Como pesquisar (processo que funcionou)

1. **Game8, bloco da build**: importar `scripts/importar_builds_game8.py` e usar `_baixador(False)`, `links_da_home`,
   `blocos_do_personagem(personagem, links, baixar)`; casar o bloco com `chave_da_build(personagem, bloco.titulo)`;
   ler `bloco.texto` e `meta_de_regen(bloco.texto)`. Páginas ficam em `cache/game8/` (não baixar de novo).
2. **Game8, página inteira**: a meta às vezes aparece **fora do bloco** (seção de combo, de arma, ou no bloco irmão do
   mesmo personagem). Tirar `<script>/<style>`, tirar tags e procurar `Energy Regen|\bER\b` com número; ignorar
   "Con. Energy Regen", "Res. Energy Cost", "Increases Energy Regen by", a linha "Stats Lv. 1".
3. **Prydwen**: `https://www.prydwen.gg/wuthering-waves/characters/<nome>`. WebFetch dá 403 e o Firecrawl dá erro de
   schema; **curl com user-agent de Chrome funciona**. A seção útil começa em "Energy Regen requirements are estimated"
   e traz "HP: … DEF: … ATK: … CRIT Rate: … CRIT DMG: … Energy Regen: X-Y%" e uma frase explicando a faixa. Salvar o
   HTML no scratchpad e rodar Python com `-I`.
4. Rodar scripts com `uv run python` (precisa do pacote `wuwastats`); saída com `PYTHONIOENCODING=utf-8` (terminal
   cp1252 quebra com ★).
5. Gravar com `wuwastats.gamedata.perfis.gravar_perfis` (valida, faz backup em `data/backups/`, escrita atômica).
   Depois: `uv run wuwastats check-data`; recarregar o servidor com `POST http://127.0.0.1:8000/api/dados/recarregar`
   (→ 204); commitar por lote (conventional commits, sem mencionar Claude).

Armadilhas:
- **Nunca** rodar o importador com `--substituir` em quem já tem `descricao` (`mesclar` troca a build inteira e apaga o texto).
- O aviso de Regen contém `"; "`: não separar `status` por `"; "`; comparar a string inteira.
- O Game8 às vezes põe "Energy Regen" como principal de **custo 1** (não existe no jogo): ignorar.
- Faixa com condição (sequência, rotação, time) precisa da condição na explicação.

## 7. Glossário PT-BR usado nos textos

Elementos (`resonators.json › elementos`): Glacio = Criogênico, Fusion = Térmico, Electro = Voltaico,
Aero = Pneumático, Spectro = Fotônico, Havoc = Aniquilante. Status: Energy Regen = Regen. de Energia,
Healing Bonus = Bônus de Cura, Crit Rate/DMG = Taxa CRIT / Dano CRIT. Mecânicas: Tune Strain = Tensão de Sintonia,
Havoc Bane = Ruína Aniquilante, Electro Flare = Clarão Voltaico, Spectro Frazzle = Estridência Fotônica,
Aero Erosion = Erosão Pneumática, Glacio Chafe = Esfoladura Criogênica, Echo Skill = Habilidade de Eco,
Coordinated Attack = ATQ Coordenado. Shorekeeper = Guardiã da Costa. Nomes de sets, echos e armas: `nome_pt` em
`data/sets.json`, `data/echoes.json`, `data/weapons.json`.

Textos: PT-BR, palavras próprias (nunca traduzir literal), 2–3 parágrafos separados por `\n\n`, `**negrito**` nos
termos-chave; tom e tamanho como os já escritos (ex.: `Changli_Fusion_DMG`, `Shorekeeper_Suporte`).

## 8. Próximo passo sugerido

1. Responder as pendências da seção 3 com o usuário (começar pela 1).
2. Escrever o plano de implementação (skill `superpowers:writing-plans`) a partir deste documento.
3. Implementar o modelo de metas + comparação com a tela do personagem + exibição; migrar `regen_energia_min`.
4. Preencher as metas das 52 builds (seção 5.3), corrigindo a 5.2 junto; depois os textos e metas das 25 (5.4).
