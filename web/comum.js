// Peças compartilhadas pelas páginas: API, DOM, ícones e a moldura. Nenhuma regra de negócio aqui.

// ---------- API ----------

export async function pedir(url, opcoes = {}) {
  const resposta = await fetch(url, opcoes);
  const corpo = resposta.status === 204 ? null : await resposta.json().catch(() => null);
  if (!resposta.ok) {
    const detalhes = corpo?.erros?.length ? `\n- ${corpo.erros.join("\n- ")}` : "";
    const erro = new Error(`${corpo?.mensagem ?? `HTTP ${resposta.status}`}${detalhes}`);
    erro.status = resposta.status;
    throw erro;
  }
  return corpo;
}

const json = (metodo, corpo) => ({
  method: metodo,
  headers: { "Content-Type": "application/json" },
  body: corpo === undefined ? undefined : JSON.stringify(corpo),
});

export const api = {
  personagens: () => pedir("/api/personagens"),
  builds: () => pedir("/api/builds"),
  catalogo: () => pedir("/api/catalogo"),
  echoes: () => pedir("/api/echoes"),
  analisar: (entrada) => pedir("/api/analisar", json("POST", entrada)),
  extrair: (form) => pedir("/api/extrair", { method: "POST", body: form }),
  mapear: (pedido) => pedir("/api/aliases", json("POST", pedido)),
  historico: {
    salvar: (pedido) => pedir("/api/historico", json("POST", pedido)),
    listar: (build) => pedir(build ? `/api/historico?build=${encodeURIComponent(build)}` : "/api/historico"),
    ler: (id) => pedir(`/api/historico/${encodeURIComponent(id)}`),
    apagar: (id) => pedir(`/api/historico/${encodeURIComponent(id)}`, { method: "DELETE" }),
  },
  perfis: {
    listar: () => pedir("/api/perfis"),
    salvar: (chave, perfil) => pedir(`/api/perfis/${encodeURIComponent(chave)}`, json("PUT", perfil)),
    apagar: (chave) => pedir(`/api/perfis/${encodeURIComponent(chave)}`, { method: "DELETE" }),
  },
  imagens: () => pedir("/api/imagens"),
  kit: (chave) => pedir(`/api/kits/${encodeURIComponent(chave)}`),
  enviarImagem: (categoria, chave, arquivo) => {
    const form = new FormData();
    form.append("arquivo", arquivo);
    return pedir(`/api/imagens/${categoria}/${encodeURIComponent(chave)}`, { method: "PUT", body: form });
  },
  fanarts: () => pedir("/api/fanarts"),
  enviarFanart: (chave, { arquivo, artista, link, enquadramento }) => {
    const form = new FormData();
    if (arquivo) form.append("arquivo", arquivo);
    form.append("artista", artista);
    form.append("link", link);
    form.append("posicao_x", enquadramento.x);
    form.append("posicao_y", enquadramento.y);
    form.append("zoom", enquadramento.zoom);
    return pedir(`/api/fanarts/${encodeURIComponent(chave)}`, { method: "PUT", body: form });
  },
  captura: {
    teclas: () => pedir("/api/captura/teclas"),
    iniciar: (build) => pedir("/api/captura/iniciar", json("POST", { build })),
    parar: () => pedir("/api/captura/parar", { method: "POST" }),
    estado: (sessao) => pedir(`/api/captura/${encodeURIComponent(sessao)}`),
    entrada: (sessao) => pedir(`/api/captura/${encodeURIComponent(sessao)}/entrada`),
    reordenar: (sessao, ordem) => pedir(`/api/captura/${encodeURIComponent(sessao)}/reordenar`, json("POST", { ordem })),
    esvaziarEcho: (sessao, i) => pedir(`/api/captura/${encodeURIComponent(sessao)}/echos/${i}`, { method: "DELETE" }),
    esvaziarPersonagem: (sessao) => pedir(`/api/captura/${encodeURIComponent(sessao)}/personagem`, { method: "DELETE" }),
    refazer: (sessao, i) => pedir(`/api/captura/${encodeURIComponent(sessao)}/echos/${i}/refazer`, { method: "POST" }),
    eventos: (sessao) => new EventSource(`/api/captura/${encodeURIComponent(sessao)}/eventos`),
  },
};

export const parametro = (nome) => new URLSearchParams(location.search).get(nome);

// ---------- DOM ----------

export function el(tag, atributos = {}, ...filhos) {
  const elemento = document.createElement(tag);
  aplicar(elemento, atributos);
  elemento.append(...filhos.flat().filter((f) => f !== null && f !== undefined && f !== false));
  return elemento;
}

function aplicar(elemento, atributos) {
  for (const [nome, valor] of Object.entries(atributos)) {
    if (nome.startsWith("on")) elemento.addEventListener(nome.slice(2), valor);
    else if (nome === "style" && typeof valor === "object") Object.assign(elemento.style, valor);
    else if (valor === true) elemento.setAttribute(nome, "");
    else if (valor !== null && valor !== undefined && valor !== false) elemento.setAttribute(nome, valor);
  }
}

const SVG = "http://www.w3.org/2000/svg";

/** Ícone de traço (estilo do design). `d` pode ser um caminho ou uma lista deles. */
export function icone(d, tamanho = 16, { espessura = 1.8, cor = null, preenchido = false } = {}) {
  const svg = document.createElementNS(SVG, "svg");
  const atributos = { width: tamanho, height: tamanho, viewBox: "0 0 24 24", "aria-hidden": "true" };
  if (preenchido) Object.assign(atributos, { fill: "currentColor" });
  else Object.assign(atributos, { fill: "none", stroke: "currentColor", "stroke-width": espessura, "stroke-linecap": "round", "stroke-linejoin": "round" });
  for (const [nome, valor] of Object.entries(atributos)) svg.setAttribute(nome, valor);
  if (cor) svg.style.color = cor;
  for (const caminho of [d].flat()) {
    const path = document.createElementNS(SVG, "path");
    path.setAttribute("d", caminho);
    svg.append(path);
  }
  return svg;
}

export function silhueta(cor, classe = "sil", largura = null) {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", "0 0 100 110");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("class", classe);
  svg.style.color = cor;
  if (largura) svg.style.width = largura;
  const cabeca = document.createElementNS(SVG, "circle");
  Object.entries({ cx: 50, cy: 38, r: 22, fill: "currentColor" }).forEach(([k, v]) => cabeca.setAttribute(k, v));
  const corpo = document.createElementNS(SVG, "path");
  corpo.setAttribute("d", "M8 110c4-30 22-44 42-44s38 14 42 44z");
  corpo.setAttribute("fill", "currentColor");
  svg.append(cabeca, corpo);
  return svg;
}

export const ICONES = {
  logo: "M3 5l4 14 5-10 5 10 4-14",
  personagens: ["M2.5 20a6.5 6.5 0 0 1 13 0", "M16 4.5a3.5 3.5 0 0 1 0 7M18 14.5a6 6 0 0 1 3.5 5.5", "M9 4.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z"],
  captura: ["M4 8h3l2-3h6l2 3h3v11H4z", "M12 9.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z"],
  analise: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  builds: ["M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3", "M1 14h6M9 8h6M17 16h6"],
  voltar: "M19 12H5M11 6l-6 6 6 6",
  busca: ["M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z", "m20 20-3.5-3.5"],
  filtro: "M3 5h18l-7 8.5V20l-4-2v-4.5z",
  redefinir: ["M3 12a9 9 0 1 0 3-6.7L3 8", "M3 3v5h5"],
  echo: "M12 3 20 7.5v9L12 21l-8-4.5v-9z",
  sonata: ["M9 18V5l11-2v13", "M6 15a3 3 0 1 0 0 6 3 3 0 0 0 0-6z", "M17 13a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"],
  ok: "m5 12 5 5 9-10",
  atencao: "M12 3 2 20h20zM12 10v4M12 17v.5",
  refazer: ["M21 12a9 9 0 1 1-3-6.7L21 8", "M21 3v5h-5"],
  fechar: "M6 6l12 12M18 6 6 18",
  enviar: "M12 16V4M7 9l5-5 5 5M4 16v4h16v-4",
  imagem: ["M5 4h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z", "M9 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4z", "m21 16-5-5-9 9"],
  girando: "M21 12a9 9 0 1 1-9-9",
  externo: ["M14 4h6v6", "M20 4l-9 9", "M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"],
  grip: ["M9 6h.01M15 6h.01M9 12h.01M15 12h.01M9 18h.01M15 18h.01"],
};

// Chaves vêm de /api/personagens (elemento.chave, tipo_arma.chave).
// Glifos oficiais do jogo (elementinfo.json → Icon4Pure, UIResources/Common/Image/IconElement128), baixados de static.nanoka.cc.
export const ELEMENTOS = {
  glacio: { cor: "#7FD3F7", glifo: "elementos/glacio.webp" },
  fusion: { cor: "#F2665A", glifo: "elementos/fusion.webp" },
  electro: { cor: "#B57BFF", glifo: "elementos/electro.webp" },
  aero: { cor: "#5BD6A0", glifo: "elementos/aero.webp" },
  spectro: { cor: "#F2D45C", glifo: "elementos/spectro.webp" },
  havoc: { cor: "#E66BB0", glifo: "elementos/havoc.webp" },
};
const ELEMENTO_DESCONHECIDO = { cor: "#A39BB6", glifo: null };
export const elemento = (chave) => ELEMENTOS[chave] ?? ELEMENTO_DESCONHECIDO;

/** Glifo branco do jogo usado como máscara: assume a cor do elemento. */
export function iconeElemento(chave, tamanho = 16) {
  const { cor, glifo } = elemento(chave);
  if (!glifo) return icone("M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", tamanho, { espessura: 2, cor });
  const mascara = `url("${glifo}") center / contain no-repeat`;
  return el("span", {
    "aria-hidden": "true",
    style: { display: "block", width: `${tamanho}px`, height: `${tamanho}px`, background: cor, mask: mascara, webkitMask: mascara },
  });
}

// Glifos oficiais de tipo de arma (SP_IconNor*), baixados de static.nanoka.cc/assets/ww/Static.
// O jogo chama a montante de "Sword", a espada de "Knife" e o retificador de "Magic".
const ARMAS = {
  broadblade: "armas/broadblade.webp",
  sword: "armas/sword.webp",
  pistols: "armas/pistols.webp",
  gauntlets: "armas/gauntlets.webp",
  rectifier: "armas/rectifier.webp",
};

/** Glifo branco do jogo usado como máscara: assume a cor do texto ao redor. */
export function iconeArma(chave, tamanho = 16) {
  const glifo = ARMAS[chave];
  if (!glifo) return icone("M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", tamanho, { espessura: 2 });
  const mascara = `url("${glifo}") center / contain no-repeat`;
  return el("span", {
    "aria-hidden": "true",
    style: { display: "block", flexShrink: "0", width: `${tamanho}px`, height: `${tamanho}px`, background: "currentColor", mask: mascara, webkitMask: mascara },
  });
}

export const estrelas = (n) => "★".repeat(n);

// ---------- Notas e qualidade da rolagem ----------

const COR_NOTA = { SSS: "#F5C451", SS: "#F5C451", S: "#C4B1FF", A: "#6AA8FF", B: "#5BD6A0" };
export const corNota = (nota) => COR_NOTA[nota] ?? "#A39BB6";

export const QUALIDADES = [
  { nome: "baixa", cor: "#8A8499" },
  { nome: "razoável", cor: "#5BD6A0" },
  { nome: "boa", cor: "#6AA8FF" },
  { nome: "ótima", cor: "#B57BFF" },
  { nome: "máxima", cor: "#F5C451" },
];

/** 8 tiers (ou 4, nos fixos) → 5 cores: só o valor máximo é "máxima"; os outros se dividem em 4 faixas iguais. */
export function qualidade(tier, total) {
  if (tier >= total) return QUALIDADES[4];
  const faixa = Math.floor(((tier - 1) * 4) / (total - 1));
  return QUALIDADES[Math.min(3, faixa)];
}

// ---------- Catálogo ----------

/** Rótulos PT de stats, sets, echos e armas: primeiro nome do catálogo, ou a própria chave. */
export function rotulador(catalogo) {
  const mapa = (itens) => new Map(itens.map((i) => [i.chave, i]));
  const stats = mapa(catalogo.stats);
  const sets = mapa(catalogo.sets);
  const echoes = mapa(catalogo.echoes);
  const armas = mapa(catalogo.armas);
  const nome = (item, chave) => item?.nomes?.[0] ?? chave;
  return {
    stats, sets, echoes, armas,
    stat: (chave) => {
      const item = stats.get(chave);
      if (!item) return chave;
      const base = nome(item, chave);
      const ambiguo = /^(ATQ|HP|DEF)$/i.test(base);
      return ambiguo ? `${base}${item.percentual ? "%" : " fixo"}` : base;
    },
    set: (chave) => (chave ? nome(sets.get(chave), chave) : null),
    echo: (chave) => (chave ? nome(echoes.get(chave), chave) : null),
    arma: (chave) => (chave ? nome(armas.get(chave), chave) : null),
  };
}

export function formatarValor(valor, percentual) {
  if (valor === null || valor === undefined) return "—";
  return percentual ? `${Number(valor).toFixed(1)}%` : String(Math.round(valor));
}

// ---------- Metas de status (Regen, crítico, HP...) ----------

export const ROTULO_TIPO_META = { escala: "Escala do kit", rotacao: "Rotação" };
export const ROTULO_FONTE = { game8: "Game8", prydwen: "Prydwen" };
const ROTULO_TOTAL = { hp_flat: "HP total", atk_flat: "ATQ total", def_flat: "DEF total" };

/** "Rotação" só faz sentido na Regen (Liberação pronta a cada rotação); nos demais stats a faixa é só a meta. */
export const tagDaMeta = (meta) =>
  meta.tipo === "rotacao" && meta.stat !== "energy_regen" ? "Meta" : ROTULO_TIPO_META[meta.tipo];

/** Na meta, HP/ATQ/DEF são os totais da tela, não o substatus fixo. */
export const rotuloMeta = (stat, rotulo) => ROTULO_TOTAL[stat] ?? rotulo.stat(stat);

const valorDaMeta = (stat, valor) => (stat in ROTULO_TOTAL ? Math.round(valor).toLocaleString("pt-BR") : `${valor}%`);

/** "105–130%", "120%+" (rotação sem máximo), "250%" (teto de escala), "50.000". */
export function faixaDaMeta(meta) {
  if (meta.max !== null && meta.max !== undefined) {
    const sufixo = meta.stat in ROTULO_TOTAL ? "" : "%";
    return `${valorDaMeta(meta.stat, meta.min).replace("%", "")}–${valorDaMeta(meta.stat, meta.max).replace("%", "")}${sufixo}`;
  }
  return meta.tipo === "rotacao" ? `${valorDaMeta(meta.stat, meta.min)}+` : valorDaMeta(meta.stat, meta.min);
}

const ICONE_STAT = {
  crit: "M12 3v4M12 17v4M3 12h4M17 12h4M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
  atk: "M14.5 4H20v5.5L9 20.5 3.5 15zM6 13l5 5",
  hp: "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z",
  def: "M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z",
  regen: "M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5",
  dmg: "M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z",
  heal: "M12 5v14M5 12h14",
};

/** Ícone por chave interna (crit_rate, atk_pct...) ou por nome lido na tela (Taxa CRIT, ATQ...). */
export function iconeStat(stat) {
  const s = (stat ?? "").toLowerCase();
  if (s.includes("crit")) return ICONE_STAT.crit;
  if (s.includes("regen") || s.includes("energy")) return ICONE_STAT.regen;
  if (s.includes("cura") || s.includes("heal")) return ICONE_STAT.heal;
  if (/(^|[^a-z])(atq|atk)/.test(s) && !s.includes("dano") && !s.includes("dmg") && !s.includes("básico") && !s.includes("pesado")) return ICONE_STAT.atk;
  if (s.startsWith("hp")) return ICONE_STAT.hp;
  if (s.startsWith("def")) return ICONE_STAT.def;
  return ICONE_STAT.dmg;
}

// ---------- Condições das variantes ----------

const ROTULO_CONDICAO = {
  arma_assinatura: { true: "Com arma assinatura", false: "Sem arma assinatura", pergunta: "Está com a arma assinatura?" },
};

export function rotuloCondicao(condicao) {
  return Object.entries(condicao)
    .map(([chave, valor]) => ROTULO_CONDICAO[chave]?.[String(valor)] ?? `${chave}: ${valor}`)
    .join(" · ");
}

export const perguntaCondicao = (chave) => ROTULO_CONDICAO[chave]?.pergunta ?? `${chave}?`;

// ---------- Moldura ----------

const PAGINAS = [
  { id: "personagens", href: "index.html", rotulo: "Personagens" },
  { id: "echo", href: "echoes.html", rotulo: "Echos" },
  { id: "captura", href: "captura.html", rotulo: "Captura" },
  { id: "analise", href: "analise.html", rotulo: "Análise" },
  { id: "builds", href: "perfis.html", rotulo: "Editor de builds" },
];

/** Monta a barra lateral e devolve o <main> onde a página desenha. */
export function moldura(ativa) {
  const hrefs = hrefsMemorizados();
  const lateral = el(
    "nav",
    { class: "side", "aria-label": "Navegação principal" },
    el("div", { class: "logo", "aria-hidden": "true" }, icone(ICONES.logo, 22, { espessura: 2 })),
    PAGINAS.map((p) =>
      el(
        "a",
        {
          class: `nav${p.id === ativa ? " active" : ""}`,
          href: hrefs[p.id] ?? p.href,
          "aria-label": p.rotulo,
          title: p.rotulo,
          "aria-current": p.id === ativa ? "page" : null,
        },
        icone(ICONES[p.id], 22),
      ),
    ),
  );
  const principal = el("main", { class: "main" });
  document.body.replaceChildren(el("div", { class: "app" }, lateral, principal));
  return principal;
}

export function avisoErro(erro) {
  return el("div", { class: "aviso", role: "alert" }, icone(ICONES.atencao, 18, { cor: "#FF8A94" }), el("span", {}, erro.message ?? String(erro)));
}

// O menu lateral volta para a última captura/análise aberta (com a build ou sessão na URL).
const CHAVE_LINKS = "wuwastats:links";

export function lembrarPagina(id, href) {
  try {
    const links = JSON.parse(sessionStorage.getItem(CHAVE_LINKS) ?? "{}");
    sessionStorage.setItem(CHAVE_LINKS, JSON.stringify({ ...links, [id]: href }));
  } catch (erro) {
    console.warn("menu: não consegui guardar o link", erro);
  }
}

export function hrefsMemorizados() {
  try {
    return JSON.parse(sessionStorage.getItem(CHAVE_LINKS) ?? "{}");
  } catch (erro) {
    console.warn("menu: não consegui ler os links guardados", erro);
    return {};
  }
}

// ---------- Ampliar imagem ----------

/** Abre a imagem em tela cheia (Esc, clique fora ou no X fecham). */
export function ampliar(src, legenda) {
  const fechar = () => dialogo.close();
  const dialogo = el(
    "dialog",
    { class: "lightbox", "aria-label": legenda, onclose: () => dialogo.remove(), onclick: (e) => e.target === dialogo && fechar() },
    el("button", { class: "ibtn lightbox-fechar", type: "button", "aria-label": "Fechar", onclick: fechar }, icone(ICONES.fechar, 20, { espessura: 2 })),
    el("img", { src, alt: legenda, onerror: (e) => e.target.replaceWith(el("p", {}, "O print não está mais disponível (o servidor apaga os prints ao iniciar outra captura ou desligar).")) }),
    el("p", {}, legenda),
  );
  document.body.append(dialogo);
  dialogo.showModal();
}

/** Botão-miniatura que amplia ao clicar. Se a imagem falhar, mostra o conteúdo reserva. */
export function miniaturaAmpliavel(src, legenda, reserva, classe = "") {
  const botao = el("button", { type: "button", class: `mini ${classe}`.trim(), title: "Ampliar", "aria-label": `Ampliar ${legenda}`, onclick: () => ampliar(src, legenda) });
  const imagem = el("img", { src, alt: "", loading: "lazy", onerror: () => botao.replaceWith(reserva) });
  botao.append(imagem);
  return botao;
}

// ---------- Imagens do catálogo (personagens, echos, armas, sets) ----------

const imagensDisponiveis = { personagens: new Set(), echoes: new Set(), armas: new Set(), sets: new Set() };
const versaoImagem = new Map(); // força o navegador a buscar de novo depois de trocar

export async function carregarImagens() {
  try {
    const lista = await api.imagens();
    for (const [categoria, chaves] of Object.entries(lista)) imagensDisponiveis[categoria] = new Set(chaves);
  } catch (erro) {
    console.warn("imagens: lista indisponível; usando placeholders", erro);
  }
}

export const urlImagemKit = (chave, nome) => `/api/kits/${encodeURIComponent(chave)}/imagens/${encodeURIComponent(nome)}`;

export const temImagem = (categoria, chave) => imagensDisponiveis[categoria].has(chave);

export const srcImagem = (categoria, chave) => `/api/imagens/${categoria}/${encodeURIComponent(chave)}?v=${versaoImagem.get(`${categoria}/${chave}`) ?? 0}`;

// Retratos oficiais com o personagem fora do eixo da arte: onde fica o centro de rosto e tronco, em % da largura.
const CENTRO_DO_RETRATO = new Map([["Brant", 44], ["Buling", 46], ["Lupa", 54], ["Qiuyuan", 47], ["Shorekeeper", 55]]);

function foto(categoria, chave, rotulo) {
  const imagem = el("img", { class: "foto", src: srcImagem(categoria, chave), alt: rotulo ?? "", loading: "lazy" });
  const centro = categoria === "personagens" ? CENTRO_DO_RETRATO.get(chave) : undefined;
  if (centro !== undefined) imagem.style.setProperty("--desvio-x", `${50 - centro}%`);
  return imagem;
}

/** Imagem do catálogo quando existe, senão o placeholder. Com `trocavel`, um botão envia outra imagem. */
export function figura(categoria, chave, reserva, { trocavel = false, rotulo = chave } = {}) {
  const caixa = el("div", { class: "figura" });
  const desenhar = () => {
    const tem = chave && imagensDisponiveis[categoria].has(chave);
    const conteudo = tem ? foto(categoria, chave, rotulo) : reserva;
    const trocar = trocavel && chave ? botaoTrocar(categoria, chave, rotulo, caixa, desenhar) : null;
    caixa.replaceChildren(...[conteudo, trocar].filter(Boolean));
  };
  desenhar();
  return caixa;
}

function botaoTrocar(categoria, chave, rotulo, caixa, redesenhar) {
  const entrada = el("input", {
    class: "sr",
    type: "file",
    accept: "image/png,image/jpeg,image/webp",
    onchange: async (e) => {
      const arquivo = e.target.files[0];
      if (!arquivo) return;
      try {
        await api.enviarImagem(categoria, chave, arquivo);
        imagensDisponiveis[categoria].add(chave);
        versaoImagem.set(`${categoria}/${chave}`, Date.now());
        redesenhar();
      } catch (erro) {
        caixa.title = erro.message;
        caixa.classList.add("figura-erro");
      }
    },
  });
  // Dentro de um link (card da galeria) o clique no botão não pode navegar: cancela e abre o seletor à mão.
  const abrirSeletor = (e) => {
    e.stopPropagation();
    if (e.target === entrada) return;
    e.preventDefault();
    entrada.click();
  };
  return el(
    "label",
    { class: "trocar", title: "Trocar imagem", "aria-label": `Trocar imagem de ${rotulo}`, onclick: abrirSeletor },
    entrada,
    icone(ICONES.captura, 15, { espessura: 2 }),
  );
}
