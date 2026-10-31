// Tela 2 · Personagem: perfis de GET /api/builds e, dentro de cada um, as variantes por condição.

import {
  ICONES, api, avisoErro, carregarImagens, el, elemento, estrelas, figura, icone, iconeArma, moldura, parametro, rotulador, rotuloCondicao, silhueta,
} from "./comum.js";

// Peso → estrelas de prioridade. Peso 0 não aparece: a build ignora o status.
const ESTRELAS_POR_PESO = [
  { minimo: 0.9, estrelas: 3 },
  { minimo: 0.6, estrelas: 2 },
  { minimo: Number.MIN_VALUE, estrelas: 1 },
];
const CUSTOS = ["4", "3", "1"];

const principal = moldura("personagens");
const variantePorBuild = new Map();
carregar();

async function carregar() {
  try {
    const [personagens, builds, catalogo] = await Promise.all([api.personagens(), api.builds(), api.catalogo(), carregarImagens()]);
    const chave = parametro("nome");
    const personagem = personagens.find((p) => p.chave === chave);
    if (!personagem) throw new Error(`Personagem '${chave ?? ""}' não encontrado.`);
    document.title = `WuwaStats · ${personagem.nome}`;
    const contexto = { personagem, builds: builds.filter((b) => b.personagem === personagem.chave), rotulo: rotulador(catalogo) };
    desenhar(contexto);
  } catch (erro) {
    principal.replaceChildren(el("div", { class: "wrap" }, voltar(), avisoErro(erro)));
  }
}

const voltar = () => el("a", { class: "back", href: "index.html" }, icone(ICONES.voltar, 18, { espessura: 2 }), "Personagens");

function desenhar(contexto) {
  principal.replaceChildren(
    el(
      "div",
      { class: "wrap" },
      voltar(),
      cabecalho(contexto),
      contexto.builds.length ? contexto.builds.map((b) => secaoBuild(b, contexto)) : semBuild(contexto.personagem),
    ),
  );
}

function cabecalho({ personagem, builds }) {
  const cor = elemento(personagem.elemento.chave);
  const quantidade = builds.length === 1 ? "1 construção recomendada" : `${builds.length} construções recomendadas`;
  return el(
    "header",
    { style: { display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: "32px", marginTop: "16px", paddingBottom: "32px", borderBottom: "1px solid var(--borda)" } },
    el(
      "div",
      { class: "ph", style: { width: "208px", height: "260px", borderRadius: "14px", borderColor: personagem.raridade === 5 ? "#6B5A2E" : "#3A2F52", placeItems: "end center", overflow: "hidden" } },
      figura("personagens", personagem.chave, silhueta(cor.cor, "", "78%"), { trocavel: true, rotulo: personagem.nome }),
    ),
    el(
      "div",
      { style: { display: "flex", flexDirection: "column", gap: "16px", paddingBottom: "8px" } },
      el("p", { class: "label", style: { margin: 0, fontSize: "13px" } }, "Ressonador"),
      el("h1", { style: { margin: 0, fontSize: "56px", fontWeight: 800, letterSpacing: "-0.02em", lineHeight: 1 } }, personagem.nome),
      el(
        "div",
        { style: { display: "flex", flexWrap: "wrap", gap: "10px" } },
        el("span", { class: "chip" }, el("span", { class: "dot", style: { background: cor.cor } }), personagem.elemento.nome),
        el("span", { class: "chip" }, icone(iconeArma(personagem.tipo_arma.chave), 16), personagem.tipo_arma.nome),
        el("span", { class: "chip estrelas", style: { letterSpacing: "2px" }, "aria-label": `${personagem.raridade} estrelas` }, estrelas(personagem.raridade)),
      ),
      el("p", { style: { margin: 0, fontSize: "15px", color: "var(--mudo)" } }, builds.length ? quantidade : "Nenhuma construção cadastrada"),
    ),
  );
}

function semBuild(personagem) {
  return el(
    "div",
    { class: "vazio-msg" },
    el("strong", {}, "Sem build cadastrada"),
    el("p", {}, `${personagem.nome} ainda não tem perfil em data/characters.json, então os echos não podem ser avaliados.`),
    el(
      "span",
      { style: { display: "flex", flexWrap: "wrap", gap: "10px", justifyContent: "center" } },
      el("a", { class: "chip on", href: `perfis.html?novo=${encodeURIComponent(personagem.chave)}` }, "Criar build"),
      el("a", { class: "chip", href: "index.html" }, "Ver outros personagens"),
    ),
  );
}

function secaoBuild(build, contexto) {
  const secao = el("section", { class: "build", "aria-label": build.chave });
  const redesenhar = () => secao.replaceChildren(...conteudoBuild(build, contexto, redesenhar));
  redesenhar();
  return secao;
}

function conteudoBuild(build, { rotulo }, redesenhar) {
  const escolhida = variantePorBuild.get(build.chave) ?? (build.variantes.length ? 0 : null);
  const perfil = escolhida === null ? build.base : build.variantes[escolhida].perfil;
  return [
    el(
      "div",
      { class: "btitle" },
      el("h2", {}, el("span", { class: "bar", "aria-hidden": "true" }), build.chave.replaceAll("_", " ")),
      el(
        "span",
        { style: { display: "flex", flexWrap: "wrap", gap: "10px" } },
        el("a", { class: "chip", href: `perfis.html?build=${encodeURIComponent(build.chave)}` }, "Editar build"),
        el("a", { class: "chip on", href: `captura.html?build=${encodeURIComponent(build.chave)}` }, "Avaliar meus echos ", el("span", { "aria-hidden": "true" }, "→")),
      ),
    ),
    build.variantes.length ? seletorDeVariante(build, escolhida, redesenhar) : null,
    el("div", { class: "tables" }, tabelaConstrucao(build, perfil, rotulo), tabelaEstatisticas(perfil, rotulo)),
    textoDaBuild(build.descricao),
  ];
}

/** Parágrafos separados por linha em branco; **trecho** vira negrito. Só nós de texto: nada de innerHTML. */
function textoDaBuild(descricao) {
  if (!descricao) return null;
  const paragrafos = descricao.split(/\n\s*\n/).map((p) => el("p", {}, negritos(p.trim())));
  return el("div", { class: "build-texto" }, paragrafos);
}

const negritos = (texto) => texto.split("**").map((trecho, i) => (i % 2 ? el("strong", {}, trecho) : trecho));

function seletorDeVariante(build, escolhida, redesenhar) {
  return el(
    "div",
    { class: "variantes", role: "group", "aria-label": "Variante da build" },
    el("span", {}, "Variante:"),
    build.variantes.map((v, i) =>
      el(
        "button",
        {
          type: "button",
          class: `chip${i === escolhida ? " on" : ""}`,
          "aria-pressed": String(i === escolhida),
          onclick: () => {
            variantePorBuild.set(build.chave, i);
            redesenhar();
          },
        },
        rotuloCondicao(v.condicao),
      ),
    ),
  );
}

function linha(rotulo, ...valor) {
  return el("div", { class: "trow" }, el("div", { class: "tl" }, rotulo), el("div", { class: "tv" }, ...valor));
}

const mudo = (texto) => el("span", { style: { color: "var(--mudo)" } }, texto);

function tabelaConstrucao(build, perfil, rotulo) {
  const armas = build.armas;
  const alternativas = armas?.alternativas ?? [];
  return el(
    "div",
    { class: "tcard" },
    el("div", { class: "thead" }, "Construção"),
    linha(
      "Melhor arma",
      el("span", { class: "ph", style: { width: "40px", height: "40px", borderRadius: "8px", overflow: "hidden" } }, figura("armas", armas?.melhor, icone(ICONES.imagem, 18), { trocavel: true, rotulo: rotulo.arma(armas?.melhor) })),
      armas?.melhor ? el("span", { class: "lilac" }, rotulo.arma(armas.melhor)) : mudo("Não cadastrada"),
    ),
    linha(
      "Armas alternativas",
      alternativas.length
        ? el("div", { class: "alts" }, alternativas.map((a) => el("span", { class: "alt" }, el("span", { class: "ph", style: { width: "26px", height: "26px", borderRadius: "6px", overflow: "hidden" } }, figura("armas", a, null)), rotulo.arma(a))))
        : mudo("Nenhuma cadastrada"),
    ),
    linha(
      "Efeito Sonata",
      el("span", { class: "ph", style: { width: "36px", height: "36px", borderRadius: "50%" } }, icone(ICONES.sonata, 16)),
      perfil.set ? el("strong", {}, rotulo.set(perfil.set)) : mudo("Livre"),
    ),
    linha("Padrão de custo", el("span", { style: { display: "flex", gap: "8px" } }, perfil.custos.map((c) => el("span", { class: "cost" }, String(c))))),
    linha(
      "Eco Principal",
      el("span", { class: "ph echoic" }, figura("echoes", perfil.echo_principal, icone(ICONES.echo, 18), { trocavel: true, rotulo: rotulo.echo(perfil.echo_principal) }), el("span", { class: "costcorner", "aria-label": "Custo 4" }, "4")),
      perfil.echo_principal ? el("strong", {}, rotulo.echo(perfil.echo_principal)) : mudo("Livre"),
    ),
  );
}

function tabelaEstatisticas(perfil, rotulo) {
  return el(
    "div",
    { class: "tcard" },
    el("div", { class: "thead" }, "Estatísticas do echo"),
    el("div", { class: "subhead" }, "Status principal por custo"),
    el(
      "div",
      { class: "mains" },
      CUSTOS.map((custo) =>
        el(
          "div",
          { class: "mcol" },
          el("div", { class: "mhead" }, `${custo} CUSTO`),
          el("div", { class: "mprin" }, (perfil.principais[custo] ?? []).map(rotulo.stat).join(" ou ") || mudo("Livre")),
        ),
      ),
    ),
    el("div", { class: "subhead" }, "Prioridade de substatus"),
    el("ol", { class: "prio" }, prioridade(perfil.pesos).map(({ stat, estrelas: n }, i) =>
      el(
        "li",
        {},
        el("span", { class: "pn" }, `${i + 1}.`),
        el("span", { style: { fontWeight: 600 } }, rotulo.stat(stat)),
        el("span", { class: "pstars", "aria-label": `${n} de 3 estrelas` }, "★".repeat(n), el("span", { class: "off" }, "★".repeat(3 - n))),
      ),
    )),
  );
}

function prioridade(pesos) {
  return Object.entries(pesos)
    .filter(([, peso]) => peso > 0)
    .sort(([, a], [, b]) => b - a)
    .map(([stat, peso]) => ({ stat, estrelas: ESTRELAS_POR_PESO.find((f) => peso >= f.minimo).estrelas }));
}
