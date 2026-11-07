// Tela 1 · Personagens: lista de GET /api/personagens com busca e filtros.

import { ICONES, api, avisoErro, carregarImagens, el, elemento, estrelas, figura, icone, iconeArma, iconeElemento, moldura, silhueta } from "./comum.js";

const TODOS = "todos";
const filtros = { el: TODOS, wp: TODOS, rar: TODOS, q: "", aberto: false };
let personagens = [];

const principal = moldura("personagens");
carregar();

async function carregar() {
  try {
    const [lista] = await Promise.all([api.personagens(), carregarImagens()]);
    personagens = ordenar(lista);
    desenhar();
  } catch (erro) {
    principal.replaceChildren(el("div", { class: "wrap" }, avisoErro(erro)));
  }
}

/** Quem tem build primeiro; depois 5★ antes de 4★; depois o nome. */
function ordenar(lista) {
  return [...lista].sort(
    (a, b) => Number(b.tem_perfil) - Number(a.tem_perfil) || b.raridade - a.raridade || a.nome.localeCompare(b.nome, "pt-BR"),
  );
}

function visiveis() {
  const termo = filtros.q.trim().toLocaleLowerCase("pt-BR");
  return personagens.filter(
    (p) =>
      (filtros.el === TODOS || p.elemento.chave === filtros.el) &&
      (filtros.wp === TODOS || p.tipo_arma.chave === filtros.wp) &&
      (filtros.rar === TODOS || String(p.raridade) === filtros.rar) &&
      (!termo || p.nome.toLocaleLowerCase("pt-BR").includes(termo) || p.chave.toLocaleLowerCase("pt-BR").includes(termo)),
  );
}

function desenhar() {
  const lista = visiveis();
  const ativos = ["el", "wp", "rar"].filter((k) => filtros[k] !== TODOS).length;
  principal.replaceChildren(
    el(
      "div",
      { class: "wrap" },
      el(
        "header",
        { class: "cabeca" },
        el("h1", {}, "Personagens"),
        el("p", {}, `${lista.length} de ${personagens.length} personagens`),
      ),
      barraDeBusca(ativos),
      painelDeFiltros(),
      lista.length ? null : vazio(),
      el("div", { class: "grid" }, lista.map(cartao)),
    ),
  );
}

function barraDeBusca(ativos) {
  const busca = el("input", {
    type: "search",
    placeholder: "Buscar personagem pelo nome…",
    value: filtros.q,
    oninput: (e) => {
      filtros.q = e.target.value;
      desenhar();
      const campo = principal.querySelector(".busca input");
      campo.focus();
      campo.setSelectionRange(campo.value.length, campo.value.length);
    },
  });
  return el(
    "div",
    { style: { display: "flex", flexWrap: "wrap", gap: "12px", marginTop: "28px" } },
    el("label", { class: "busca" }, icone(ICONES.busca, 20, { espessura: 2 }), el("span", { class: "sr" }, "Buscar personagem"), busca),
    el(
      "button",
      {
        class: `fbtn${filtros.aberto || ativos ? " on" : ""}`,
        type: "button",
        "aria-expanded": String(filtros.aberto),
        "aria-controls": "painel-filtros",
        onclick: () => {
          filtros.aberto = !filtros.aberto;
          desenhar();
        },
      },
      icone(ICONES.filtro, 18, { espessura: 2 }),
      "Filtros",
      ativos ? el("span", { class: "contagem" }, `· ${ativos}`) : null,
    ),
  );
}

function painelDeFiltros() {
  const unicos = (campo) => [...new Map(personagens.map((p) => [p[campo].chave, p[campo].nome])).entries()];
  const elementos = unicos("elemento").map(([chave, nome]) => ({ chave, nome, extra: el("span", { class: "dot", style: { background: elemento(chave).cor } }) }));
  const armas = unicos("tipo_arma").map(([chave, nome]) => ({ chave, nome, extra: icone(iconeArma(chave), 16) }));
  const raridades = [...new Set(personagens.map((p) => p.raridade))].sort((a, b) => b - a).map((r) => ({ chave: String(r), nome: `${r}★` }));
  return el(
    "div",
    { id: "painel-filtros", class: `filtros${filtros.aberto ? " open" : ""}` },
    el(
      "div",
      {},
      el(
        "div",
        { class: "fpanel" },
        grupo("Elemento", "el", elementos),
        grupo("Arma", "wp", armas),
        grupo("Raridade", "rar", raridades),
        el("button", { type: "button", class: "reset", onclick: () => redefinir(false) }, icone(ICONES.redefinir, 16, { espessura: 2 }), "Redefinir filtros"),
      ),
    ),
  );
}

function grupo(rotulo, chave, opcoes) {
  const chip = (valor, nome, extra = null) =>
    el(
      "button",
      {
        type: "button",
        class: `chip${filtros[chave] === valor ? " on" : ""}`,
        "aria-pressed": String(filtros[chave] === valor),
        onclick: () => {
          filtros[chave] = valor;
          desenhar();
        },
      },
      extra,
      nome,
    );
  return el(
    "div",
    { class: "fgroup", role: "group", "aria-label": rotulo },
    el("span", { class: "flabel" }, rotulo),
    chip(TODOS, "Todos"),
    opcoes.map((o) => chip(o.chave, o.nome, o.extra)),
  );
}

function redefinir(limparBusca) {
  Object.assign(filtros, { el: TODOS, wp: TODOS, rar: TODOS }, limparBusca ? { q: "" } : {});
  desenhar();
}

function vazio() {
  return el(
    "div",
    { class: "vazio-msg" },
    el("strong", {}, "Nenhum personagem encontrado"),
    el("p", {}, "Tente outro nome ou redefina os filtros."),
    el("button", { type: "button", class: "chip on", onclick: () => redefinir(true) }, "Redefinir filtros"),
  );
}

function cartao(p) {
  const cor = elemento(p.elemento.chave);
  const descricao = `${p.nome}, ${p.elemento.nome}, ${p.tipo_arma.nome}, ${p.raridade} estrelas${p.tem_perfil ? "" : ", sem build cadastrada"}`;
  return el(
    "a",
    { class: `card${p.tem_perfil ? "" : " sem-perfil"}`, href: `personagem.html?nome=${encodeURIComponent(p.chave)}`, "aria-label": descricao },
    el(
      "div",
      { class: `portrait${p.raridade === 5 ? " r5" : ""}` },
      figura("personagens", p.chave, silhueta(cor.cor), { trocavel: true, rotulo: p.nome }),
      el("span", { class: "badge el", title: p.elemento.nome }, iconeElemento(p.elemento.chave, 18)),
      el("span", { class: "badge wp", title: p.tipo_arma.nome }, icone(iconeArma(p.tipo_arma.chave), 16)),
    ),
    el(
      "div",
      { class: "cbody" },
      el("span", { class: "cname" }, p.nome),
      el("span", { class: "estrelas", style: { fontSize: "13px" } }, estrelas(p.raridade)),
      p.tem_perfil ? null : el("span", { class: "cnota" }, "Sem build cadastrada"),
    ),
  );
}
