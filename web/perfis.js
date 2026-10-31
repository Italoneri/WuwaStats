// Editor de builds: edita os perfis de characters.json. A validação é a do servidor (mesmo loader dos dados).

import { ICONES, api, avisoErro, el, icone, moldura, parametro, rotulador, rotuloCondicao } from "./comum.js";

const ESCALAS = ["ATQ", "DEF", "HP"];
const CUSTOS = [4, 3, 1];
const CHAVES_CUSTO = ["4", "3", "1"];
const ESTRELAS_MAXIMAS = 3;
const SETA_ACIMA = "m6 15 6-6 6 6";
const SETA_ABAIXO = "m6 9 6 6 6-6";
const CAMPOS_VARIANTE = [
  { campo: "set", rotulo: "Set" },
  { campo: "echo_principal", rotulo: "Eco principal" },
  { campo: "regen_energia_min", rotulo: "Regen mínima" },
  { campo: "custos", rotulo: "Padrão de custo" },
  { campo: "principais", rotulo: "Status principais" },
  { campo: "estrelas", rotulo: "Estrelas" },
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
    estrelas: {},
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
  }
  if (limpo.armas && !limpo.armas.melhor && !limpo.armas.alternativas.length) limpo.armas = null;
  return limpo;
}

/** "characters.json › Suoming_DPS › estrelas › X: motivo" e "body › variantes › 0 › set: motivo" → campo do formulário. */
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
    el("div", { class: "tcard" }, el("div", { class: "thead" }, "Prioridade dos substatus"), el("div", { class: "subhead" }, "3 estrelas = o mais importante · clique de novo para tirar · setas mudam a ordem entre iguais"), editorEstrelas(p, "estrelas")),
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

/** Com estrela primeiro (mais estrelas no topo, na ordem da build); sem estrela no fim, por nome: a build ignora. */
function editorEstrelas(alvo, campo) {
  const r = estado.rotulo;
  const estrelas = alvo.estrelas ?? {};
  const ordem = Object.keys(estrelas);
  const livres = [...r.stats.values()]
    .filter((s) => s.substatus !== null && !(s.chave in estrelas))
    .map((s) => s.chave)
    .sort((a, b) => r.stat(a).localeCompare(r.stat(b), "pt-BR"));
  const mesmoNivel = (vizinho, stat) => vizinho !== undefined && estrelas[vizinho] === estrelas[stat];
  const erros = estado.erros.get(campo) ?? [];
  return el(
    "div",
    { class: "estrelas-editor" },
    ordem.map((stat, i) => linhaEstrelas(alvo, stat, { acima: mesmoNivel(ordem[i - 1], stat) && ordem[i - 1], abaixo: mesmoNivel(ordem[i + 1], stat) && ordem[i + 1] })),
    livres.length ? el("div", { class: "estrelas-separador" }, "Sem estrela · a build ignora") : null,
    livres.map((stat) => linhaEstrelas(alvo, stat, {})),
    erros.map((m) => el("span", { class: "erro-campo" }, m)),
  );
}

function linhaEstrelas(alvo, stat, { acima, abaixo }) {
  const nome = estado.rotulo.stat(stat);
  const quantas = alvo.estrelas?.[stat] ?? 0;
  const seta = (vizinho, d, rotulo) =>
    el("button", { type: "button", class: "ibtn seta", disabled: !vizinho, "aria-label": `${rotulo} ${nome}`, onclick: () => trocarOrdem(alvo, stat, vizinho) }, icone(d, 14, { espessura: 2.2 }));
  return el(
    "div",
    { class: `estrela-linha${quantas ? "" : " sem-estrela"}` },
    el("span", { class: "setas" }, quantas ? [seta(acima, SETA_ACIMA, "Subir"), seta(abaixo, SETA_ABAIXO, "Descer")] : null),
    el("span", { class: "estrela-nome" }, nome),
    el(
      "span",
      { class: "estrela-botoes", role: "group", "aria-label": `Estrelas de ${nome}` },
      Array.from({ length: ESTRELAS_MAXIMAS }, (_, i) => i + 1).map((n) =>
        el(
          "button",
          {
            type: "button",
            class: `estrela${n <= quantas ? " acesa" : ""}`,
            "aria-label": `${n} de ${ESTRELAS_MAXIMAS} estrelas`,
            "aria-pressed": String(n === quantas),
            title: n === quantas ? "Clique de novo para tirar" : `${n} de ${ESTRELAS_MAXIMAS}`,
            onclick: () => darEstrelas(alvo, stat, n),
          },
          "★",
        ),
      ),
    ),
  );
}

/** Clicar na estrela que já está marcada tira as estrelas. Quem muda de nível entra no fim do novo nível. */
function darEstrelas(alvo, stat, quantas) {
  const { [stat]: atual, ...resto } = alvo.estrelas ?? {};
  alvo.estrelas = ordenarPorEstrelas(quantas === atual ? resto : { ...resto, [stat]: quantas });
  desenhar();
}

function trocarOrdem(alvo, stat, vizinho) {
  const chaves = Object.keys(alvo.estrelas);
  const [i, j] = [chaves.indexOf(stat), chaves.indexOf(vizinho)];
  [chaves[i], chaves[j]] = [chaves[j], chaves[i]];
  alvo.estrelas = Object.fromEntries(chaves.map((c) => [c, alvo.estrelas[c]]));
  desenhar();
}

const ordenarPorEstrelas = (estrelas) => Object.fromEntries(Object.entries(estrelas).sort(([, a], [, b]) => b - a));

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
    ...camposDeBuild(v, prefixo, marcados.filter((c) => c !== "estrelas")),
    marcados.includes("estrelas") ? linha("Estrelas", `${prefixo}estrelas`, editorEstrelas(v, `${prefixo}estrelas`)) : null,
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
