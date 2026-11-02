# Site público: imagens, fanarts e direitos

Anotações de 2026-11-02 para quando o WuwaStats for colocado no ar. Ainda não há nada implementado disto além do que
está em "Estado atual". Não é consultoria jurídica; é a leitura das regras públicas e do que os sites de fã fazem.

## Decisões

- **O público só vê arte oficial da Kuro.** Retratos, banners e imagens do kit vêm do jogo ou do material oficial.
- **Fanart é pessoal.** Cada pessoa pode trocar a foto do personagem, mas só ela vê, vinculada à conta dela. Fanart
  de terceiros nunca aparece para outros visitantes.
- **Sem anúncios** nem qualquer monetização.

Ordem combinada:

1. Imagens oficiais da Kuro como padrão (vale para o app local e para o site).
2. Projeto próprio "colocar o site no ar" (ver "O que muda ao publicar").
3. Contas com foto/fanart personalizada por pessoa, depois que o item 2 estiver definido.

## Regras da Kuro para conteúdo de fã

Fonte: [Guidelines for Derivative Works of Wuthering Waves](https://wutheringwaves.kurogames.com/p/en/produce.html).

- A Kuro é dona de tudo do jogo: nomes, visual dos personagens, história, gráficos, música, vídeos.
- Fãs podem criar obras derivadas (textos, imagens, vídeos, objetos) com esse conteúdo, desde que:
  - não violem leis;
  - não prejudiquem a imagem ou os interesses da Kuro e do jogo;
  - **não usem material de terceiros** (por isso fanart de outros artistas não pode ser exibida publicamente).
- **Jogos, software e obras comerciais ficam fora** dessas regras. Um site como o WuwaStats provavelmente conta como
  software, então não é autorizado explicitamente, mas também não é proibido: fica na mesma área cinzenta tolerada
  em que vivem wikis, Game8 e trackers.
- A Kuro pode pedir a remoção de qualquer conteúdo a qualquer momento e pode mudar as regras sem aviso.

### Comparação com outros sites

Game8 e afins usam arte oficial sem autorização especial conhecida publicamente, e vários têm anúncio, o que é uso
comercial (ainda mais claramente fora das regras). Um site de fã **sem anúncio** fica numa posição melhor que a deles.
O risco realista é um pedido de remoção, não processo; isso costuma acontecer com vazamentos antes do lançamento,
sites que se passam por oficiais ou monetização agressiva.

### Checklist ao publicar

- [ ] Rodapé em todas as páginas: "Wuthering Waves e seus personagens © Kuro Games. Site de fã, sem vínculo oficial."
- [ ] Nome, logo e visual que não pareçam oficiais (nada de logo da Kuro como se fosse do site).
- [ ] Nenhum anúncio, assinatura ou venda.
- [ ] Nenhuma fanart de terceiros visível para outros visitantes.
- [ ] Contato visível para pedidos de remoção, e atender rápido.
- [ ] Nada de conteúdo vazado antes do lançamento oficial.

## Fanarts do Pixiv

- **Crédito não é permissão.** O direito é do artista; as regras do Pixiv não permitem repostar obra de outra pessoa
  sem autorização. Muitos perfis avisam `無断転載禁止` (proibido repostar sem permissão); alguns liberam com
  `転載OK` / "repost OK" / "free to use with credit".
- Uso pessoal, só no próprio computador ou visível só para a própria conta: na prática, sem problema.
- Busca de fanarts horizontais (formato de banner): `https://www.pixiv.net/search?q=鳴潮 <nome>&s_mode=tag&type=illust_ugoira&mode=safe&ratio=0.5`.
  - `ratio=0.5` = só horizontais (`-0.5` verticais, `0` quadradas); `mode=safe` = todas as idades.
  - O filtro de resolução mínima (`wlt=1920`) funciona na API interna, mas a página de busca o descarta.
  - O nome japonês do personagem traz uns 60% mais resultados que o inglês (ex.: `エイメス` para Aemeath), mas os
    dados do app não têm os nomes em japonês.

## Estado atual (app local)

- Fanart com crédito e enquadramento (arrastar + zoom, com prévia no formato do banner) por personagem:
  `data/imagens/fanarts/<chave>.webp` + `.json`, rotas em `/api/fanarts` (ver [api.md](api.md#fanarts)). O diálogo
  tem o link de busca no Pixiv acima.
- Fotos padrão da galeria (`data/imagens/personagens/`) foram enviadas à mão; imagens do kit vêm do nanoka (assets
  extraídos do jogo, também da Kuro). `data/imagens/` não vai para o git.
- **Tudo é global e sem login**: qualquer pessoa com acesso ao servidor troca a fanart de todos.

## O que muda ao publicar

- **Fanarts**: deixar de ser globais. Precisa de conta, armazenamento por usuário e a rota servir a imagem só ao dono;
  sem login, o banner usa a arte oficial.
- **Captura**: hoje roda no servidor e lê a tela do jogo (precisa de admin). No ar, o servidor não está no PC de quem
  joga; precisa de outra solução (envio de prints, app local separado etc.).
- **Edição de builds, aliases e dados**: hoje aberta; no ar, só o dono do site.
- **Chave da NVIDIA (leitura de imagens)**: cada análise de visitante custaria para o dono; precisa de limite,
  cota por conta ou chave do próprio usuário.
- **Hospedagem**: escolher onde e quanto custa.
