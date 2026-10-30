// Editor de builds: edita os perfis de characters.json. A validação é a do servidor (mesmo loader dos dados).

import { ICONES, api, avisoErro, el, icone, moldura, parametro, rotulador, rotuloCondicao } from "./comum.js";

const ESCALAS = ["ATQ", "DEF", "HP"];
const CUSTOS = [4, 3, 1];
const CHAVES_CUSTO = ["4", "3", "1"];
const PASSO_PESO = 0.05;
const CAMPOS_VARIANTE = [
  { campo: "set", rotulo: "Set" },
  { campo: "echo_principal", rotulo: "Eco principal" },
  { campo: "regen_energia_min", rotulo: "Regen mínima" },
  { campo: "custos", rotulo: "Padrão de custo" },
  { campo: "principais", rotulo: "Status principais" },
  { campo: "pesos", rotulo: "Pesos" },
];

const estado = {
  perfis: {},
  personagens: [],
  rotulo: null,
  catalogo: null,
  chave: null,
  novo: false,
  perfil: null, // cópia em edição
  original: "", // JSON do perfil salvo, para saber se há alteração
  erros: new Map(), // campo -> mensagens
  errosGerais: [],
  aviso: null,
  ocupado: false,
  confirmarApagar: false,
};

const principal = moldura("builds");
carregar();

async function carregar() {
  try {
    const [perfis, personagens, catalogo] = await Promise.all([api.perfis.listar(), api.personagens(), api.catalogo()]);
    Object.assign(estado, { perfis, personagens, catalogo, rotulo: rotulador(catalogo) });
    const novo = parametro("novo");
    if (novo) abrirNova(novo);
    else abrir(parametro("build") ?? Object.keys(perfis)[0]);
  } catch (erro) {
    principal.replaceChildren(el("div", { class: "wrap" }, avisoErro(erro)));
  }
}

// ---------- Navegação entre builds ----------

function abrir(chave) {
  if (!chave || !estado.perfis[chave]) return abrirNova(estado.personagens.find((p) => p.tem_perfil)?.chave ?? estado.personagens[0]?.chave);
  Object.assign(estado, { chave, novo: false, perfil: structuredClone(estado.perfis[chave]), original: JSON.stringify(estado.perfis[chave]) });
  limparMensagens();
  atualizarUrl(`build=${encodeURIComponent(chave)}`);
  desenhar();
}

function abrirNova(personagem) {
  const perfil = {
    personagem,
    escala: "ATQ",
    regen_energia_min: 100,
    custos: [4, 3, 3, 1, 1],
    principais: { 4: [], 3: [], 1: [] },
    pesos: {},
    armas_assinatura: [],
    variantes: [],
  };
  Object.assign(estado, { chave: `${personagem ?? "Nova"}_Build`.replace(/[^\w-]+/g, "_"), novo: true, perfil, original: "" });
  limparMensagens();
  atualizarUrl(`novo=${encodeURIComponent(personagem ?? "")}`);
  desenhar();
}

function atualizarUrl(busca) {
  history.replaceState(null, "", `perfis.html?${busca}`);
}

function limparMensagens() {
  Object.assign(estado, { erros: new Map(), errosGerais: [], aviso: null, confirmarApagar: false });
}

const alterado = () => estado.novo || JSON.stringify(estado.perfil) !== estado.original;

// ---------- Salvar e apagar ----------

async function salvar() {
  estado.ocupado = true;
  limparMensagens();
  desenhar();
  try {
    const salvo = await api.perfis.salvar(estado.chave, semCamposVazios(estado.perfil));
    estado.perfis[estado.chave] = salvo;
    Object.assign(estado, { novo: false, perfil: structuredClone(salvo), original: JSON.stringify(salvo) });
    estado.aviso = "✓ Salvo. O arquivo anterior foi copiado para data/backups/.";
    atualizarUrl(`build=${encodeURIComponent(estado.chave)}`);
  } catch (erro) {
    distribuirErros(erro);
  } finally {
    estado.ocupado = false;
    desenhar();
  }
}

async function apagar() {
  if (!estado.confirmarApagar) {
    estado.confirmarApagar = true;
    return desenhar();
  }
  estado.ocupado = true;
  try {
    await api.perfis.apagar(estado.chave);
    delete estado.perfis[estado.chave];
    estado.ocupado = false;
    abrir(Object.keys(estado.perfis)[0]);
    estado.aviso = "✓ Build apagada. O arquivo anterior foi copiado para data/backups/.";
    desenhar();
  } catch (erro) {
    estado.ocupado = false;
    distribuirErros(erro);
    desenhar();
  }
}

/** O servidor recusa set "" e armas sem nada: troca por null/ausente antes de enviar. */
function semCamposVazios(perfil) {
  const limpo = structuredClone(perfil);
  for (const alvo of [limpo, ...limpo.variantes]) {
    if (alvo.set === "") alvo.set = null;
    if (alvo.echo_principal === "") alvo.echo_principal = null;
    if (alvo.pesos) alvo.pesos = Object.fromEntries(Object.entries(alvo.pesos).filter(([, peso]) => peso > 0));
  }
  if (limpo.armas && !limpo.armas.melhor && !limpo.armas.alternativas.length) limpo.armas = null;
  return limpo;
}

/** "characters.json › Suoming_DPS › pesos › X: motivo" e "body › variantes › 0 › set: motivo" → campo do formulário. */
function distribuirErros(erro) {
  const mensagens = erro.message.split("\n- ");
  const lista = mensagens.length > 1 ? mensagens.slice(1) : [];
  estado.errosGerais = [mensagens[0], ...lista.filter((m) => !campoDoErro(m))];
  for (const mensagem of lista) {
    const campo = campoDoErro(mensagem);
    if (campo) estado.erros.set(campo, [...(estado.erros.get(campo) ?? []), mensagem.split(": ").slice(1).join(": ") || mensagem]);
  }
}

function campoDoErro(mensagem) {
  let partes = mensagem.split(": ")[0].split(" › ");
  const inicio = partes.indexOf(estado.chave);
  if (inicio >= 0) partes = partes.slice(inicio + 1);
  else if (partes[0] === "body") partes = partes.slice(1);
  else return null;
  if (partes[0] === "variantes" && partes.length >= 2) return `variantes.${partes[1]}.${partes[2] ?? ""}`;
  return partes[0] || null;
}

// ---------- Desenho ----------

function desenhar() {
  principal.replaceChildren(
    el(
      "div",
      { class: "wrap pilha", style: { gap: "24px" } },
      cabecalho(),
      estado.errosGerais.length ? avisoErro(new Error(estado.errosGerais.join("\n"))) : null,
      estado.aviso ? el("p", { class: "aviso-ok" }, estado.aviso) : null,
      estado.perfil ? formulario() : null,
      estado.perfil ? rodape() : null,
    ),
  );
}

function cabecalho() {
  const opcoes = Object.keys(estado.perfis).map((chave) => el("option", { value: chave, selected: !estado.novo && chave === estado.chave }, chave.replaceAll("_", " ")));
  const seletor = el(
    "select",
    { class: "select", "aria-label": "Build em edição", onchange: (e) => (e.target.value === "" ? abrirNova(estado.perfil?.personagem) : abrir(e.target.value)) },
    opcoes,
    el("option", { value: "", selected: estado.novo }, "+ Nova build…"),
  );
  const personagem = estado.personagens.find((p) => p.chave === estado.perfil?.personagem);
  return el(
    "header",
    { class: "cabeca", style: { alignItems: "center" } },
    el("div", { style: { display: "flex", flexWrap: "wrap", alignItems: "center", gap: "24px" } }, el("h1", {}, "Editor de builds"), seletor),
    personagem && !estado.novo ? el("a", { class: "chip", href: `personagem.html?nome=${encodeURIComponent(personagem.chave)}` }, `Ver ${personagem.nome} →`) : null,
  );
}

function formulario() {
  const p = estado.perfil;
  return el(
    "div",
    { class: "tables" },
    el(
      "div",
      { class: "tcard" },
      el("div", { class: "thead" }, "Construção"),
      estado.novo ? linha("Chave da build", "chave", el("input", { class: "campo", value: estado.chave, oninput: (e) => { estado.chave = e.target.value.trim(); } })) : null,
      linha("Personagem", "personagem", seletorPersonagem(p)),
      linha("Escala", "escala", seletor(ESCALAS.map((e) => [e, e]), p.escala, (v) => { p.escala = v; })),
      ...camposDeBuild(p, ""),
    ),
    el("div", { class: "tcard" }, el("div", { class: "thead" }, "Pesos dos substatus"), el("div", { class: "subhead" }, "0 = a build ignora · 1 = o mais importante"), editorPesos(p, "pesos")),
    el("div", { class: "tcard" }, el("div", { class: "thead" }, "Armas"), ...camposDeArmas(p)),
    el("div", { class: "tcard" }, el("div", { class: "thead" }, "Variantes por condição"), variantes(p)),
  );
}

function linha(rotulo, campo, ...controles) {
  const erros = estado.erros.get(campo) ?? [];
  return el(
    "div",
    { class: `trow${erros.length ? " com-erro" : ""}` },
    el("div", { class: "tl" }, rotulo),
    el("div", { class: "tv", style: { flexDirection: "column", alignItems: "stretch" } }, ...controles, erros.map((m) => el("span", { class: "erro-campo" }, m))),
  );
}

function seletor(opcoes, valor, mudar, rotuloVazio = null) {
  return el(
    "select",
    { class: "campo", onchange: (e) => { mudar(e.target.value); desenhar(); } },
    rotuloVazio !== null ? el("option", { value: "", selected: !valor }, rotuloVazio) : null,
    opcoes.map(([v, r]) => el("option", { value: v, selected: String(v) === String(valor) }, r)),
  );
}

function seletorPersonagem(p) {
  const opcoes = [...estado.personagens].sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR")).map((x) => [x.chave, x.nome]);
  return seletor(opcoes, p.personagem, (v) => { p.personagem = v; });
}

const ordenar = (pares) => pares.sort((a, b) => a[1].localeCompare(b[1], "pt-BR"));

/** Campos que a base e as variantes têm em comum. prefixo = "" (base) ou "variantes.N." (para os erros). */
function camposDeBuild(alvo, prefixo, apenas = null) {
  const r = estado.rotulo;
  const usar = (campo) => !apenas || apenas.includes(campo);
  return [
    usar("regen_energia_min") ? linha("Regen mínima (%)", `${prefixo}regen_energia_min`, el("input", { class: "campo mono", type: "number", step: "1", min: "100", value: alvo.regen_energia_min, onchange: (e) => { alvo.regen_energia_min = Number(e.target.value); desenhar(); } })) : null,
    usar("custos") ? linha("Padrão de custo", `${prefixo}custos`, el("div", { style: { display: "flex", gap: "6px" } }, alvo.custos.map((c, i) => seletorCusto(alvo, i, c)))) : null,
    usar("set") ? linha("Set", `${prefixo}set`, seletor(ordenar([...r.sets.keys()].map((k) => [k, r.set(k)])), alvo.set, (v) => { alvo.set = v || null; }, "Livre")) : null,
    usar("echo_principal") ? linha("Eco principal", `${prefixo}echo_principal`, seletor(ordenar([...r.echoes.keys()].map((k) => [k, r.echo(k)])), alvo.echo_principal, (v) => { alvo.echo_principal = v || null; }, "Livre")) : null,
    usar("principais") ? linha("Status principais", `${prefixo}principais`, editorPrincipais(alvo)) : null,
  ];
}

function seletorCusto(alvo, i, valor) {
  return el(
    "select",
    { class: "campo mono", "aria-label": `Custo do echo ${i + 1}`, style: { width: "64px" }, onchange: (e) => { alvo.custos[i] = Number(e.target.value); desenhar(); } },
    CUSTOS.map((c) => el("option", { value: c, selected: c === valor }, String(c))),
  );
}

function editorPrincipais(alvo) {
  const r = estado.rotulo;
  return el(
    "div",
    { style: { display: "flex", flexDirection: "column", gap: "10px" } },
    CHAVES_CUSTO.map((custo) => {
      const escolhidos = new Set(alvo.principais[custo] ?? []);
      const candidatos = [...r.stats.values()].filter((s) => s.principal[custo] !== undefined);
      return el(
        "div",
        { class: "fgroup" },
        el("span", { class: "mhead", style: { background: "transparent", border: 0, padding: 0, width: "64px" } }, `${custo} CUSTO`),
        candidatos.map((s) =>
          el(
            "button",
            {
              type: "button",
              class: `chip${escolhidos.has(s.chave) ? " on" : ""}`,
              style: { minHeight: "32px", fontSize: "13px" },
              "aria-pressed": String(escolhidos.has(s.chave)),
              onclick: () => {
                escolhidos.has(s.chave) ? escolhidos.delete(s.chave) : escolhidos.add(s.chave);
                alvo.principais = { ...alvo.principais, [custo]: [...escolhidos] };
                desenhar();
              },
            },
            r.stat(s.chave),
          ),
        ),
      );
    }),
  );
}

function editorPesos(alvo, campo) {
  const r = estado.rotulo;
  const stats = [...r.stats.values()].filter((s) => s.substatus !== null).sort((a, b) => (alvo.pesos[b.chave] ?? 0) - (alvo.pesos[a.chave] ?? 0) || r.stat(a.chave).localeCompare(r.stat(b.chave), "pt-BR"));
  const erros = estado.erros.get(campo) ?? [];
  return el(
    "div",
    { class: "pesos" },
    stats.map((s) => {
      const valor = alvo.pesos[s.chave] ?? 0;
      const mostrador = el("span", { class: "mono peso-valor" }, valor.toFixed(2));
      return el(
        "label",
        { class: "peso" },
        el("span", {}, r.stat(s.chave)),
        el("input", {
          type: "range",
          min: "0",
          max: "1",
          step: String(PASSO_PESO),
          value: String(valor),
          // sem redesenhar a cada movimento: o slider perderia o arraste
          oninput: (e) => {
            alvo.pesos = { ...alvo.pesos, [s.chave]: Number(e.target.value) };
            mostrador.textContent = Number(e.target.value).toFixed(2);
          },
          onchange: () => desenhar(),
        }),
        mostrador,
      );
    }),
    erros.map((m) => el("span", { class: "erro-campo" }, m)),
  );
}

// ---------- Armas ----------

function camposDeArmas(p) {
  const r = estado.rotulo;
  const tipo = estado.personagens.find((x) => x.chave === p.personagem)?.tipo_arma.chave;
  const armas = [...r.armas.values()]
    .filter((a) => !tipo || a.tipo === tipo)
    .sort((a, b) => b.raridade - a.raridade || r.arma(a.chave).localeCompare(r.arma(b.chave), "pt-BR"))
    .map((a) => [a.chave, `${r.arma(a.chave)} (${a.raridade}★)`]);
  const recomendadas = p.armas ?? { melhor: null, alternativas: [] };
  const mudarArmas = (mudanca) => {
    p.armas = { ...recomendadas, ...mudanca };
  };
  return [
    linha("Melhor arma", "armas", seletor(armas, recomendadas.melhor, (v) => mudarArmas({ melhor: v || null }), "Não definida")),
    linha("Armas alternativas", "armas.alternativas", listaDeArmas(recomendadas.alternativas, armas, (lista) => mudarArmas({ alternativas: lista }))),
    linha("Armas assinatura", "armas_assinatura", listaDeArmas(p.armas_assinatura, armas, (lista) => { p.armas_assinatura = lista; }), el("span", { class: "dica" }, "Com a tela do personagem, a análise detecta se a arma equipada é uma destas.")),
  ];
}

function listaDeArmas(lista, opcoes, mudar) {
  const r = estado.rotulo;
  const restantes = opcoes.filter(([chave]) => !lista.includes(chave));
  return el(
    "div",
    { class: "alts" },
    lista.map((chave) =>
      el(
        "span",
        { class: "alt", style: { paddingLeft: "12px" } },
        r.arma(chave),
        el("button", { type: "button", class: "ibtn", style: { width: "26px", height: "26px" }, "aria-label": `Remover ${r.arma(chave)}`, onclick: () => { mudar(lista.filter((a) => a !== chave)); desenhar(); } }, icone(ICONES.fechar, 13, { espessura: 2 })),
      ),
    ),
    restantes.length ? seletor(restantes, null, (v) => v && mudar([...lista, v]), "+ adicionar…") : null,
  );
}

// ---------- Variantes ----------

function variantes(p) {
  return el(
    "div",
    { style: { display: "flex", flexDirection: "column" } },
    el("div", { class: "subhead" }, "A primeira variante cuja condição bate substitui os campos marcados; o resto vem da base."),
    p.variantes.map((v, i) => cartaoVariante(p, v, i)),
    el("div", { style: { padding: "14px 20px" } }, el("button", { class: "btn sm", type: "button", onclick: () => { p.variantes.push({ condicao: { arma_assinatura: true } }); desenhar(); } }, "+ Adicionar variante")),
  );
}

function cartaoVariante(p, v, i) {
  const prefixo = `variantes.${i}.`;
  const marcados = CAMPOS_VARIANTE.filter(({ campo }) => v[campo] !== undefined).map(({ campo }) => campo);
  const alternar = (campo, ligado) => {
    if (ligado) v[campo] = structuredClone(p[campo] ?? "");
    else delete v[campo];
    desenhar();
  };
  return el(
    "div",
    { class: "variante" },
    el(
      "div",
      { class: "btitle", style: { padding: "14px 20px 0" } },
      el("strong", {}, `Variante ${i + 1}: ${rotuloCondicao(v.condicao)}`),
      el("button", { class: "btn sm", type: "button", onclick: () => { p.variantes.splice(i, 1); desenhar(); } }, "Remover variante"),
    ),
    linha("Condição", `${prefixo}condicao`, seletor([["true", "Com arma assinatura"], ["false", "Sem arma assinatura"]], String(v.condicao.arma_assinatura), (valor) => { v.condicao = { arma_assinatura: valor === "true" }; })),
    linha(
      "Substitui",
      `${prefixo}`,
      el(
        "div",
        { class: "fgroup" },
        CAMPOS_VARIANTE.map(({ campo, rotulo }) =>
          el("label", { class: "chip", style: { minHeight: "32px", fontSize: "13px" } }, el("input", { type: "checkbox", checked: marcados.includes(campo), onchange: (e) => alternar(campo, e.target.checked) }), rotulo),
        ),
      ),
    ),
    ...camposDeBuild(v, prefixo, marcados.filter((c) => c !== "pesos")),
    marcados.includes("pesos") ? linha("Pesos", `${prefixo}pesos`, editorPesos(v, `${prefixo}pesos`)) : null,
  );
}

// ---------- Rodapé ----------

function rodape() {
  return el(
    "footer",
    { class: "foot", style: { position: "sticky", bottom: "16px", zIndex: 3 } },
    el("span", { style: { fontSize: "14px", fontWeight: 700, color: alterado() ? "var(--laranja)" : "var(--mudo)" } }, estado.novo ? "Build nova, ainda não salva" : alterado() ? "Alterações não salvas" : "Sem alterações"),
    el(
      "div",
      { style: { display: "flex", flexWrap: "wrap", gap: "10px" } },
      estado.novo ? null : el("button", { class: "btn", type: "button", disabled: estado.ocupado, onclick: apagar }, estado.confirmarApagar ? "Confirmar: apagar build" : "Apagar build"),
      alterado() && !estado.novo ? el("button", { class: "btn", type: "button", disabled: estado.ocupado, onclick: () => abrir(estado.chave) }, "Descartar alterações") : null,
      el("button", { class: "btn primary", type: "button", disabled: estado.ocupado || !alterado(), onclick: salvar }, estado.ocupado ? "Salvando…" : "Salvar"),
    ),
  );
}
