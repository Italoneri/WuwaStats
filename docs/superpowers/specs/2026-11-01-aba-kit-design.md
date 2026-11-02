# Aba Kit (e Rotação) na tela do personagem — design

Data: 2026-11-01. **Decidido** = dito pelo usuário. **Minha decisão** = escolha minha, o usuário pode trocar.

## 1. Por que

A tela do personagem (`web/personagem.html` + `personagem.js`) só mostra builds. O usuário quer consultar o **kit
oficial** do personagem no próprio app, com a organização e os destaques do nanoka.cc, mas **em português**, com o texto
oficial do jogo. Uma aba **Rotação** vem depois, com design do próprio usuário.

## 2. Decidido

1. Na tela do personagem, **à direita da foto, no canto superior direito do cabeçalho**, abas **Builds | Kit | Rotação**.
   Vale para todos os ressonadores. Layout aprovado: esboço em `.superpowers/brainstorm/*/content/kit-layout.html`.
2. **Kit** na ordem oficial do jogo, com destaque e organização do nanoka:
   1. **Resumo curto no topo**: 2–3 frases, escritas à mão, sem nada elaborado: papel do personagem e se a rotação é
      rápida/lenta, tempo em campo etc. Junto, as tags do jogo (ex.: "Dano Principal", "Eficiência de Concerto").
   2. Habilidades: Ataque Normal, Habilidade de Ressonância, Circuito Ressonante (com a **imagem da barra do forte**),
      Liberação de Ressonância, Habilidade Intro, Habilidade Outro.
   3. Habilidades Inerentes (2) e Ruptura de Sintonia.
   4. Cadeia de Ressonância: S1–S6 em grade, cada uma com ícone.
   - Cada habilidade: ícone, tipo, nome, descrição com subtítulos (`<size=40><color=Title>`), dano na **cor do elemento**,
     termos em destaque (`Highlight`, glossário `<te>`) em dourado.
   - **Multiplicadores** em tabela com seletor de nível, em toda habilidade que tem números.
3. **Texto em PT-BR, oficial do jogo.** Nada de nome ou valor chutado (regra do projeto).
4. **Imagens** (ícones das habilidades, das sequências, barra do forte) vêm do servidor do nanoka, como os ícones de
   echos/armas/sets já vêm.
5. **Rotação**: só a aba com aviso "em breve". O conteúdo é do usuário, depois.
6. **Primeira entrega: kit de Aemeath, Yangyang e Suoming.** Só o kit (a aba Rotação existe, vazia).

## 3. Fontes (recon feita em 2026-11-01)

Texto e números: `Arikatsu/WutheringWaves_Data`, o mesmo repositório e commit de `data/fonte_dados_jogo.json` (3.7),
com o textmap `Textmaps/pt/multi_text/MultiText.json` (~50 MB, chave `Id` → `Content`).

| O quê | Tabela | Ligação |
|---|---|---|
| Personagem | `BinData/role/roleinfo.json` (`RoleType == 1`) | `Name` (textmap), `Tag[]`, `SkillTreeGroupId`, `ResonantChainGroupId` |
| Nós do kit | `BinData/skillTree/skilltree.json` | `NodeGroup == SkillTreeGroupId`; `NodeType` 1/2/3 = habilidade (`SkillId`), 4 = bônus de status (`PropertyNodeTitle`, `PropertyNodeParam`) |
| Habilidade | `BinData/skill/skill.json` | `SkillType` → `skilltype.json` (`TypeName` no textmap = "ATQ Normal", "Circuito Ressonante"…), `SkillName`, `SkillDescribe`, `SkillDetailNum` (valores de `{0}`, `{1}`…), `Icon`, `SkillLevelGroupId` |
| Multiplicadores | `BinData/skill/skilldescription.json` | `SkillLevelGroupId`; `AttributeName` (textmap), `SkillDetailNum[].ArrayString` (20 níveis), `Order` |
| Sequências | `BinData/resonate_chain/resonantchain.json` | `GroupId == ResonantChainGroupId`, `GroupIndex` 1–6, `NodeName`, `AttributesDescription`, `AttributesDescriptionParams`, `NodeIcon` |
| Tags | `BinData/role/roletag.json` | `TagName`, `TagDesc` (textmap), `TagIcon`, `TagNameColor` |

Conferido no PT: Yangyang (1402), Aemeath (1210) e Suoming (1312) têm todos os nós, nomes e textos. Exemplo:
"Habilidade de Ressonância | Domínio Zéfiro", "S1 Céus Safirinos, Pardais Altíssimos".

Imagens: caminho `/Game/Aki/UI/<resto>.<nome>` → `https://static.nanoka.cc/assets/ww/<resto>.webp` (mesma regra de
`ICONES` em `scripts/importar_dados_jogo.py`; testado com 200). A **barra do forte** não foi achada nas tabelas do
Arikatsu: o caminho vem de `forte.icon` do JSON do nanoka, `https://static.nanoka.cc/ww/<versão>/en/character/<id>.json`
(ex.: `T_RoleSkillTreeYangyang`). O nanoka só tem en/ja/ko/zh, por isso o texto vem do Arikatsu.

Marcações que aparecem no texto do jogo e precisam ser tratadas:
- `<size=40><color=Title>…</color></size>` = subtítulo; `<size=10> </size>` = espaçador;
- `<color=Wind|Fire|Thunder|Dark|Light|Ice>` = dano do elemento; `<color=Highlight>` e `<te href=N>…</te>` = destaque;
- `{0}`, `{1}`… = valor do parâmetro de mesmo índice;
- `{Cus:Ipt,Touch=Toque PC=Pressione Gamepad=Pressione}` = texto por plataforma → usar o de **PC**;
- quebras `\n` e linhas vazias.

## 4. Minhas decisões (o usuário pode trocar)

1. **Builds** continua sendo a aba que abre por padrão; a aba vai na URL (`personagem.html?nome=X&aba=kit`) para dar
   link direto e manter a aba no F5.
2. **Dados do kit num arquivo gerado**, `data/kits.json`, por chave de ressonador (a mesma de `resonators.json`),
   escrito por um script novo `scripts/importar_kits.py` que reaproveita o download/validação do importador atual.
   O script recebe os nomes (`--personagens Aemeath Yangyang Suoming`) ou importa todos. Grava o commit usado.
3. **O texto é convertido no servidor** (no import) para uma estrutura simples — parágrafos de trechos com estilo
   (`normal | subtitulo | elemento:<chave> | destaque`) e parâmetros já substituídos — para a página desenhar só com
   nós de texto, sem `innerHTML` (padrão de `textoDaBuild`).
4. **Resumos à mão num arquivo separado**, `data/kit_resumos.json` (chave → texto), para o reimport não apagar.
   **Eu escrevo** os três desta entrega (o usuário pediu "coloque um breve resumo"), com palavras próprias a partir
   do guia do Game8 de cada personagem (regra do projeto); o usuário confere na tela antes do commit final.
   Personagem sem resumo: a caixa do resumo some, as tags continuam.
9. **Texto PT faltando ou marcação desconhecida** (vale para o "importar todos" de depois): chave sem PT → usa o texto
   **oficial em inglês** do mesmo textmap e o import avisa no relatório (nada inventado); marcação fora da lista →
   mantém o texto de dentro como trecho normal e avisa. O import só falha para um personagem se faltar a estrutura
   (nó sem habilidade, tabela ausente); os outros seguem. Campos do `kits.json` não são nulos.
5. **Imagens baixadas no import** para `data/imagens/kit/<chave>/…` (pasta já no `.gitignore`), servidas por rota da
   API, como as demais imagens. Sem hotlink: o nanoka às vezes devolve 503. Imagem que faltar vira placeholder.
6. **API**: `GET /api/kits/{chave}` devolve o kit + resumo; 404 quando o personagem não tem kit importado. A aba Kit
   mostra "Kit ainda não importado" nesse caso.
7. **Multiplicadores**: níveis 1 a 10 (o máximo do jogo, `MaxSkillLevel`); a tabela traz 20 colunas, as extras ficam
   fora. Seletor começa no 10. Um seletor por habilidade.
8. **Bônus de status da árvore** (ex.: "ATQ+ 1,80%") entram no fim de Habilidades Inerentes como uma linha resumida
   ("ATQ +12%, Taxa CRIT +8%" somados) — o nanoka mostra, o esboço não tinha. Palpite: dá para tirar se o usuário não
   quiser.

## 5. Fora do escopo

- Conteúdo da aba Rotação.
- Kits dos outros personagens nesta entrega (o script já suporta; rodar depois).
- Histórias, voz, materiais de ascensão, skins.
- Versão 3.8 do jogo: o Arikatsu ainda não tem branch 3.8; fica no commit atual.

## 6. Anti-objetivos

- Texto traduzido por IA ou escrito à mão no lugar do oficial.
- `innerHTML` com texto vindo de fora.
- Página quebrar para personagem sem kit.
