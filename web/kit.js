// Aba Kit da tela do personagem: o kit oficial (GET /api/kits/{chave}) na ordem do jogo, com os destaques do texto.

import { ICONES, api, avisoErro, el, elemento, icone, urlImagemKit } from "./comum.js";

/** Conteúdo da aba; sem kit importado vira um aviso, nunca um erro que derruba a página. */
export async function desenharKit(personagem) {
  try {
    const { kit, resumo } = await api.kit(personagem.chave);
    return conteudoKit(personagem.chave, kit, resumo);
  } catch (erro) {
    return erro.status === 404 ? semKit(personagem) : avisoErro(erro);
  }
}

function conteudoKit(chave, kit, resumo) {
  return el(
    "div",
    { class: "kit" },
    cabecaDoKit(kit.tags, resumo),
    grupo("Habilidades", kit.habilidades.map((h) => cartaoHabilidade(chave, h))),
    grupo("Habilidades Inerentes", [...kit.inerentes.map((h) => cartaoHabilidade(chave, h)), linhaDeBonus(kit.bonus)]),
    grupo("Cadeia de Ressonância", el("div", { class: "kit-sequencias" }, kit.sequencias.map((s) => cartaoSequencia(chave, s)))),
  );
}

function cabecaDoKit(tags, resumo) {
  const listaDeTags = tags.length ? el("div", { class: "kit-tags" }, tags.map(tagDoJogo)) : null;
  if (!resumo) return listaDeTags;
  return el("section", { class: "kit-resumo", "aria-label": "Resumo do kit" }, el("p", { class: "label" }, "Resumo do kit"), el("p", { class: "kit-resumo-texto" }, resumo), listaDeTags);
}

const COR_HEX = /^[0-9a-f]{6}$/i;

function tagDoJogo(tag) {
  const cor = COR_HEX.test(tag.cor) ? `#${tag.cor}` : null;
  return el("span", { class: "kit-tag", title: tag.descricao, style: cor ? { color: cor, borderColor: `${cor}55` } : {} }, tag.nome);
}

function grupo(titulo, conteudo) {
  return el("section", { class: "kit-grupo" }, el("h2", { class: "kit-grupo-titulo" }, titulo), conteudo);
}

function cartaoHabilidade(chave, habilidade) {
  return el(
    "article",
    { class: "kit-card" },
    topoDoCartao(imagemKit(chave, habilidade.imagem), habilidade.tipo, habilidade.nome),
    habilidade.ilustracoes.length ? el("div", { class: "kit-ilustracoes" }, habilidade.ilustracoes.map((nome) => ilustracao(chave, nome))) : null,
    descricao(habilidade.descricao),
    habilidade.multiplicadores.length ? tabelaMultiplicadores(habilidade.multiplicadores) : null,
  );
}

function cartaoSequencia(chave, sequencia) {
  return el("article", { class: "kit-card" }, topoDoCartao(imagemKit(chave, sequencia.imagem), `S${sequencia.numero}`, sequencia.nome), descricao(sequencia.descricao));
}

function topoDoCartao(imagem, tipo, nome) {
  return el("header", { class: "kit-card-topo" }, imagem, el("div", {}, el("p", { class: "kit-tipo" }, tipo), el("h3", { class: "kit-nome" }, nome)));
}

const placeholder = () => el("span", { class: "kit-icone ph" }, icone(ICONES.imagem, 18));

function imagemKit(chave, nome) {
  if (!nome) return placeholder();
  const img = el("img", { class: "kit-icone", src: urlImagemKit(chave, nome), alt: "", loading: "lazy" });
  img.addEventListener("error", () => img.replaceWith(placeholder()), { once: true });
  return img;
}

/** Ilustração do forte que não existe na fonte some: um placeholder largo só ocuparia espaço. */
function ilustracao(chave, nome) {
  const img = el("img", { class: "kit-ilustracao", src: urlImagemKit(chave, nome), alt: "Ilustração do Circuito Ressonante", loading: "lazy" });
  img.addEventListener("error", () => img.remove(), { once: true });
  return img;
}

/** Parágrafo de um subtítulo só vira título; os outros trechos ganham a cor do estilo. Só nós de texto. */
function descricao(paragrafos) {
  return el(
    "div",
    { class: "kit-descricao" },
    paragrafos.map((trechos) =>
      trechos.length === 1 && trechos[0].estilo === "subtitulo" ? el("p", { class: "kit-subtitulo" }, trechos[0].texto) : el("p", {}, trechos.map(trecho)),
    ),
  );
}

const ESTILOS_DE_TEXTO = new Set(["destaque", "subtitulo"]);

function trecho({ texto, estilo }) {
  if (estilo === "normal") return texto;
  if (ESTILOS_DE_TEXTO.has(estilo)) return el("span", { class: "kit-destaque" }, texto);
  return el("span", { class: "kit-elemento", style: { color: elemento(estilo).cor } }, texto);
}

function tabelaMultiplicadores(multiplicadores) {
  const maximo = Math.max(...multiplicadores.map((m) => m.valores.length));
  const celulas = multiplicadores.map(() => el("td", { class: "mono" }));
  const rotuloNivel = el("strong", { class: "mono" });
  const mostrarNivel = (nivel) => {
    rotuloNivel.textContent = String(nivel);
    multiplicadores.forEach((m, i) => {
      celulas[i].textContent = m.valores[nivel - 1] ?? "—";
    });
  };
  const seletor = el("input", { type: "range", min: 1, max: maximo, value: maximo, "aria-label": "Nível da habilidade", oninput: (e) => mostrarNivel(Number(e.target.value)) });
  mostrarNivel(maximo);
  return el(
    "div",
    { class: "kit-multiplicadores" },
    el("label", { class: "kit-nivel" }, "Nível", seletor, rotuloNivel),
    el("table", {}, el("tbody", {}, multiplicadores.map((m, i) => el("tr", {}, el("td", {}, m.nome), celulas[i])))),
  );
}

function linhaDeBonus(bonus) {
  if (!bonus.length) return null;
  return el("p", { class: "kit-bonus" }, el("span", { class: "label" }, "Bônus da árvore"), bonus.map((b) => el("span", { class: "kit-bonus-item" }, `${b.nome} +${b.valor}`)));
}

function semKit(personagem) {
  return el(
    "div",
    { class: "vazio-msg" },
    el("strong", {}, "Kit ainda não importado"),
    el("p", {}, `Kit ainda não importado para ${personagem.nome}. Rode scripts/importar_kits.py --personagens "${personagem.chave}".`),
  );
}
