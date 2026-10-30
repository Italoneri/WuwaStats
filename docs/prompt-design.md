# Prompt — WuwaStats (Claude Design)

Crie o design de um web app chamado **WuwaStats**, um analisador de echos (equipamentos) do jogo Wuthering Waves. Interface em português (PT-BR), desktop primeiro (1920px), mas responsiva. São 4 telas em sequência: **Personagens → Personagem → Captura → Análise**.

## Identidade visual (vale para todas as telas)

- Tema escuro: fundo quase preto puxado para o roxo (~#0D0A16); cards e painéis num tom um pouco mais claro (~#16121F); divisórias finas roxo-acinzentadas.
- Bordas arredondadas discretas (8–12px).
- Fonte sem serifa; títulos e nomes em negrito.
- Destaque principal: roxo/lilás. Estado selecionado = fundo roxo translúcido + borda lilás.
- Estrelas e notas altas em amarelo dourado.
- Cores dos elementos: Glacio azul-claro, Fusão vermelho, Eletro roxo, Aero verde, Espectro amarelo, Devastação rosa.
- Menu lateral fixo e estreito à esquerda, só com ícones; item ativo num quadrado roxo com um traço na borda.
- Use placeholders genéricos para retratos de personagens e ícones de echos/armas.

## Tela 1 — Personagens (página inicial)

- Título grande "Personagens" com linha divisória fina embaixo.
- Campo de busca largo com ícone de lupa, sempre visível.
- Ao lado da busca, botão **"Filtros"** com ícone de funil e contador de filtros ativos (ex.: "Filtros · 2"). **O painel de filtros começa fechado** e só abre ao clicar (com animação suave). Dentro dele, grupos de chips: **Elemento** (Todos, Glacio, Fusão, Eletro, Aero, Espectro, Devastação, cada um com bolinha da cor), **Arma** (Todos, Lâmina larga, Espada, Pistolas, Manoplas, Retificador, com ícone), **Raridade** (Todos, 5★, 4★) e o botão "Redefinir filtros".
- Grade de cards de personagem (~8 por linha): retrato, ícone do elemento no canto superior direito, ícone da arma no canto inferior direito, nome e estrelas douradas. Hover levemente elevado. Clicar leva à tela 2.

## Tela 2 — Personagem (ex.: Suoming)

- Topo: retrato maior da personagem, nome, elemento (Eletro), tipo de arma e estrelas.
- Uma seção por build, empilhadas. Exemplo com 3 builds:
  1. "Construção Electro Sub-DPS"
  2. "Construção de DPS Electro Unison"
  3. "Construção de Sub-DPS Nuvens Iluminadas pela Lua"
- Título de cada seção com barrinha vertical lilás à esquerda e, **à direita do título, o botão "Avaliar meus echos →"** (estilo chip selecionado), que leva à tela 3 com essa build já escolhida.
- Cada seção tem duas tabelas no estilo de card (cabeçalho num tom mais destacado que as células, divisórias finas):
  - **Construção:** Melhor arma (ícone + nome em lilás: "Rua Silenciosa"), Armas alternativas (lista: Primavera Vermelha, Esmeralda do Gênesis, Lumingloss), Efeito Sonata ("Conjunto de 5 peças: Coração da Vigília Jurada", com ícone), Padrão de custo ("4 3 3 1 1"), Eco Principal (ícone com o custo no canto + nome: "Recordações: Suhsin, a Inevitável").
  - **Estatísticas do echo:** status principal por custo em 3 colunas (4 CUSTO: Dano Crítico ou Taxa Crítica · 3 CUSTO: Dano Elétrico · 1 CUSTO: ATQ%) e a prioridade de substatus como lista numerada com estrelas douradas (1. Dano Crítico ★★★, 2. Taxa Crítica ★★★, 3. Regeneração de Energia ★★, 4. Bônus de Dano de Ataque Básico ★★, 5. ATQ% ★★, 6. ATQ Fixo ★).

## Tela 3 — Captura

O jogador usa um script em segundo plano: no jogo, aperta F8 em cada echo e F9 na tela do personagem; cada print aparece nesta página em tempo real.

1. **Cabeçalho:** título "Captura" + seletor de perfil com busca (já preenchido, ex.: "Suoming — DPS Electro Unison"). À direita, status do script:
   - Conectado: ponto verde + "Script conectado".
   - Desconectado: ponto cinza + "Script não detectado" + botão "Baixar script de captura".
2. **Faixa de atalhos** (discreta, sempre visível), teclas desenhadas como keycaps: **[F8]** Capturar echo · **[F9]** Tela do personagem · **[F10]** Ver análise.
3. **Espaços de captura:** 5 espaços de echo (o 1º com o selo "Echo principal") + 1 espaço "Personagem". Mostre os estados:
   - vazio ("Aperte F8 no jogo" / "Aperte F9 no jogo"), em contorno tracejado;
   - print recebido (miniatura);
   - lendo com IA (shimmer/spinner);
   - ok (check verde);
   - falhou (borda vermelha + motivo + "preencha à mão na análise").
   Cada print tem ações de remover e recapturar, e os espaços de echo podem ser arrastados para mudar a ordem.
4. **Alternativa sem script:** área discreta "Ou solte os prints aqui / escolher arquivos".
5. **Rodapé:** contador "3/5 echos · personagem ✓" à esquerda e botão de destaque **"Ir para a análise →"** com o keycap [F10] ao lado.

## Tela 4 — Análise

Visual de "card de build" compartilhável, no mesmo tema roxo escuro.

- **Coluna da esquerda:** retrato grande do personagem; card da arma (nome, nível "Nv. 90/90", "Rank 1", estrelas, ATQ base e status secundário); bloco **ECHO SCORE** com o valor total (ex.: 57.7) e a nota em letra estilizada.
- **Topo:** nome do personagem, ícone do elemento, nível e o nome da build analisada. Tabela de atributos em duas colunas com ícone, nome, linha pontilhada e valor em dourado (HP, ATQ, DEF, Regen. de Energia, Taxa CRIT, Dano CRIT, Hab. de Ressonância, ATQ Básico, ATQ Pesado, Lib. de Ressonância, Dano Elétrico, Bônus de Cura; valores zerados em cinza).
- **À direita do topo, painel "Resumo da build":**
  - Regen: "145% = 100 + echos 35 + sets 10 · mínimo 110%" com ✓ ou ⚠;
  - Custos: atual "4 3 3 1 1" vs. pedido pela build;
  - Set e Eco principal, cada um com ✓ ou ⚠.
- **Faixa de chips:** "CV: 157.2", "Score médio 57.7%", e o set ativo com ícone e contagem de peças, ex.: "Coração da Vigília Jurada (5)".
- **5 cards de echo lado a lado:**
  - cabeçalho com nome do echo em caixa alta pequena, imagem do echo, ícone do set, status principal com valor grande (ex.: "Dano CRIT 44%") e custo;
  - 5 linhas de substatus (ícone, nome, valor). **A cor do valor indica a qualidade da rolagem** (tier baixo → alto: cinza, verde, azul, roxo, dourado). **Linhas dos status importantes para a build têm fundo destacado.** Barrinha fina de posição entre mínimo e máximo. Clicar num valor ou status abre edição inline (input + seletor);
  - rodapé "SCORE 75.0" com a nota em letra (SSS, SS, S, A, B, C);
  - echo que precisa de revisão: borda vermelha + ícone ⚠ com tooltip do problema.
- **Abaixo dos cards:**
  - **Candidatos a troca:** lista do pior para o melhor echo, com motivos (ex.: "Principal HP%; a build pede ATQ% no custo 1. Score 6.3%");
  - **Nomes fora do dicionário** (só quando houver): "sets: 'Nuvens ao Luar' (echos 1, 2) → [seletor] [Mapear]";
  - **Condição pendente** (quando houver): "Está com a arma assinatura? [Sim] [Não]".
- **Ações no topo:** "← Voltar para a captura" e "Exportar imagem".

Entregue as 4 telas com dados de exemplo da Suoming, mantendo componentes consistentes entre elas (cards, chips, botões, keycaps, tabelas).
