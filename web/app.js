// Página provisória: só chama a API e desenha o JSON. Nenhuma regra de negócio aqui.

const $ = (id) => document.getElementById(id);

const estado = {
  catalogo: null,
  rotuloPorStat: new Map(),
  analise: null,
};

// ---------- API ----------

async function pedir(url, opcoes = {}) {
  const resposta = await fetch(url, opcoes);
  const corpo = resposta.status === 204 ? null : await resposta.json().catch(() => null);
  if (!resposta.ok) {
    const detalhes = corpo?.erros?.length ? `\n- ${corpo.erros.join("\n- ")}` : "";
    throw new Error(`${corpo?.mensagem ?? `HTTP ${resposta.status}`}${detalhes}`);
  }
  return corpo;
}

const api = {
  builds: () => pedir("/api/builds"),
  catalogo: () => pedir("/api/catalogo"),
  analisar: (entrada) => pedir("/api/analisar", jsonPost(entrada)),
  extrair: (form) => pedir("/api/extrair", { method: "POST", body: form }),
  mapear: (pedido) => pedir("/api/aliases", jsonPost(pedido)),
};

function jsonPost(corpo) {
  return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) };
}

// ---------- DOM ----------

function el(tag, atributos = {}, ...filhos) {
  const elemento = document.createElement(tag);
  for (const [nome, valor] of Object.entries(atributos)) {
    if (nome.startsWith("on")) elemento.addEventListener(nome.slice(2), valor);
    else if (valor !== null && valor !== undefined) elemento.setAttribute(nome, valor);
  }
  elemento.append(...filhos.flat().filter((f) => f !== null && f !== undefined));
  return elemento;
}

function status(mensagem, erro = false) {
  $("status").textContent = mensagem;
  $("status").className = erro ? "erro" : "";
}

const rotulo = (stat) => estado.rotuloPorStat.get(stat) ?? stat;

// ---------- Entrada (textarea é a fonte da verdade) ----------

function lerEntrada() {
  const entrada = JSON.parse($("entrada-json").value || "{}");
  entrada.build = $("build").value;
  entrada.regen_externa = Number($("regen-externa").value || 0);
  const informado = $("regen-informado").value;
  entrada.regen_total_informado = informado === "" ? entrada.regen_total_informado ?? null : Number(informado);
  entrada.condicoes = entrada.condicoes ?? {};
  if ($("arma").value) entrada.condicoes.arma_assinatura = $("arma").value === "sim";
  entrada.echos = entrada.echos ?? [];
  return entrada;
}

function escreverEntrada(entrada) {
  $("entrada-json").value = JSON.stringify(entrada, null, 2);
}

function editarEntrada(mudar) {
  const entrada = lerEntrada();
  mudar(entrada);
  escreverEntrada(entrada);
  return analisarEntrada();
}

// ---------- Ações ----------

async function analisarEntrada() {
  try {
    estado.analise = await api.analisar(lerEntrada());
    desenharAnalise(estado.analise);
    status(estado.analise.revisao ? "Há echos marcados para revisão." : "Análise atualizada.");
  } catch (erro) {
    status(erro.message, true);
  }
}

async function extrairPrints() {
  const prints = $("prints-echo").files;
  if (!prints.length) return status("Escolha de 1 a 5 prints de echo.", true);
  const form = new FormData();
  form.append("build", $("build").value);
  form.append("regen_externa", $("regen-externa").value || "0");
  if ($("arma").value) form.append("arma_assinatura", $("arma").value);
  for (const arquivo of prints) form.append("echos", arquivo);
  if ($("print-personagem").files[0]) form.append("personagem", $("print-personagem").files[0]);

  status("Extraindo com a IA de visão...");
  try {
    const { extracao, analise } = await api.extrair(form);
    desenharExtracao(extracao, [...prints].map((p) => p.name));
    if (extracao.entrada) escreverEntrada(extracao.entrada);
    if (analise) desenharAnalise((estado.analise = analise));
    status("Extração concluída. Revise a entrada e os echos marcados.");
  } catch (erro) {
    status(erro.message, true);
  }
}

async function mapearNome(categoria, nomeLido, chave) {
  try {
    await api.mapear({ categoria, chave, alias: nomeLido });
    await carregarCatalogo();
    await analisarEntrada();
  } catch (erro) {
    status(erro.message, true);
  }
}

// ---------- Desenho ----------

function desenharExtracao(extracao, nomesOriginais) {
  const linhas = extracao.echos.map((r, i) => {
    const origem = r.do_cache ? " (cache)" : "";
    const texto = r.tipo === "ok" ? "ok" : `FALHOU: ${r.motivo} — preencha à mão`;
    return el("li", {}, `${nomesOriginais[i] ?? r.arquivo}: ${texto}${origem}`);
  });
  if (extracao.personagem) {
    const p = extracao.personagem;
    const texto = p.tipo === "ok" ? `arma ${p.leitura.arma ?? "?"}, regen ${p.leitura.regen_energia_total ?? "?"}%` : `FALHOU: ${p.motivo}`;
    linhas.push(el("li", {}, `Tela do personagem: ${texto}`));
  }
  $("resultado-extracao").replaceChildren(...linhas);
}

function desenharAnalise(analise) {
  $("analise").hidden = false;
  $("avisos").replaceChildren(...desenharAvisos(analise));
  $("echos").replaceChildren(...analise.echos.map(desenharEcho));
  $("conjunto").replaceChildren(desenharConjunto(analise));
  $("desconhecidos").replaceChildren(...desenharDesconhecidos(analise.nomes_desconhecidos));
}

function desenharAvisos(analise) {
  const avisos = [el("p", {}, `${analise.personagem} — ${analise.build}`, analise.variante === null ? "" : ` (variante ${analise.variante})`)];
  if (analise.condicoes_pendentes.length) {
    avisos.push(el("p", { class: "problema build" }, `Informe: ${analise.condicoes_pendentes.join(", ")} (use o seletor de arma acima).`));
  }
  return avisos;
}

function desenharEcho(echo) {
  const p = echo.principal;
  return el(
    "article",
    { class: echo.revisao ? "echo revisao" : "echo" },
    el("h3", {}, `${echo.indice + 1}. ${echo.nome ?? echo.nome_lido ?? "(sem nome)"}`),
    el("div", {}, `Custo ${echo.custo} · ${echo.set ?? echo.set_lido ?? "sem set"}`),
    el("div", {}, `Principal: ${p.stat ? rotulo(p.stat) : p.stat_lido} ${p.valor}`, p.valor_esperado === null ? "" : ` / ${p.valor_esperado}`),
    el("div", {}, el("strong", {}, `Score ${echo.score_pct}%`), ` · CV ${echo.cv}`),
    echo.substatus.map((sub, j) => desenharSubstat(sub, echo.indice, j)),
    echo.problemas.map(desenharProblema),
  );
}

function desenharSubstat(sub, indiceEcho, indiceSub) {
  const editarValor = (evento) =>
    editarEntrada((entrada) => {
      entrada.echos[indiceEcho].substatus[indiceSub].valor = Number(evento.target.value);
    });
  const editarStat = (evento) =>
    editarEntrada((entrada) => {
      const lido = entrada.echos[indiceEcho].substatus[indiceSub];
      lido.stat = evento.target.value;
      delete lido.percentual;
    });
  const valorInput = el("input", { type: "number", step: "0.1", value: sub.valor_lido, onchange: editarValor });
  const statSelect = seletorStat(sub.tipo === "valido" ? sub.stat : null, sub.stat_lido, editarStat);

  if (sub.tipo === "invalido") {
    return el("div", { class: "sub" }, statSelect, " ", valorInput, el("div", { class: "problema revisao" }, `inválido: ${sub.motivo}`));
  }
  const ajuste = sub.valor === sub.valor_lido ? "" : ` → ${sub.valor}`;
  return el(
    "div",
    { class: "sub" },
    el("div", {}, statSelect, " ", valorInput, ajuste, ` · tier ${sub.tier}/${sub.tiers_total} · peso ${sub.peso}`),
    el("div", { class: "barra", title: `${sub.posicao_pct}%` }, el("div", { style: `width: ${sub.posicao_pct}%` })),
    el("div", { class: "limites" }, el("span", {}, sub.min), el("span", {}, `${sub.posicao_pct}%`), el("span", {}, sub.max)),
  );
}

function seletorStat(atual, lido, aoMudar) {
  const opcoes = (estado.catalogo?.stats ?? [])
    .filter((s) => s.substatus)
    .map((s) => el("option", { value: s.chave, ...(s.chave === atual ? { selected: "" } : {}) }, rotulo(s.chave)));
  const desconhecido = atual ? [] : [el("option", { value: "", selected: "" }, `? ${lido}`)];
  return el("select", { onchange: aoMudar }, desconhecido, opcoes);
}

function desenharProblema(problema) {
  return el("div", { class: `problema ${problema.severidade}` }, `[${problema.severidade}] ${problema.mensagem}`);
}

function desenharConjunto(analise) {
  const c = analise.conjunto;
  const r = c.regen;
  const conferencia = r.informado === null ? "" : ` · tela ${r.informado}% (diferença ${r.diferenca_informado})`;
  return el(
    "div",
    {},
    el("h3", {}, "Conjunto"),
    el("p", {}, `Score médio ${c.score_medio_pct}% · CV ${c.cv} (com principais ${c.cv_com_principal})`),
    el("p", {}, `Regen ${r.total}% = ${r.base} + echos ${r.echos} + sets ${r.sets} + externa ${r.externa} · mínimo ${r.minimo}%${conferencia}`),
    el("p", {}, `Custos ${c.custos.atual.join("-")} (build: ${c.custos.esperado.join("-")})`),
    el("p", {}, `Set ${c.set.esperado ?? "livre"}: ${c.set.pecas_equipadas}/${c.set.pecas_necessarias ?? "?"} · bônus: ${c.set.bonus_ativos.map((b) => `${b.set} ${b.pecas}pç`).join(", ") || "nenhum"}`),
    el("p", {}, `Echo principal: ${c.echo_principal.atual ?? "?"}`, c.echo_principal.esperado ? ` (build: ${c.echo_principal.esperado})` : ""),
    c.problemas.map(desenharProblema),
    el("h3", {}, "Candidatos a troca (pior primeiro)"),
    el("ol", {}, analise.candidatos_troca.map((t) => el("li", {}, `${t.indice + 1}. ${t.nome ?? "(sem nome)"} — ${t.motivos.join(" ")}`))),
  );
}

function desenharDesconhecidos(desconhecidos) {
  if (!desconhecidos.length) return [];
  return [
    el("h3", {}, "Nomes fora do dicionário"),
    ...desconhecidos.map((d) => {
      const opcoes = (estado.catalogo?.[d.categoria] ?? []).map((item) => el("option", { value: item.chave }, item.chave));
      const seletor = el("select", {}, opcoes);
      const botao = el("button", { type: "button", onclick: () => mapearNome(d.categoria, d.nome_lido, seletor.value) }, "Mapear");
      return el("p", {}, `${d.categoria}: "${d.nome_lido}" (echos ${d.echos.map((i) => i + 1).join(", ")}) → `, seletor, botao);
    }),
  ];
}

// ---------- Início ----------

async function carregarCatalogo() {
  estado.catalogo = await api.catalogo();
  estado.rotuloPorStat = new Map(estado.catalogo.stats.map((s) => [s.chave, s.nomes[0] ?? s.chave]));
}

function adicionarEchoVazio() {
  const entrada = lerEntrada();
  entrada.echos.push({ nome: null, custo: 1, set: null, principal: { stat: "ATQ%", valor: 18 }, substatus: [] });
  escreverEntrada(entrada);
}

async function iniciar() {
  try {
    const [builds] = await Promise.all([api.builds(), carregarCatalogo()]);
    $("build").replaceChildren(...builds.map((b) => el("option", { value: b.chave }, `${b.personagem} — ${b.chave}`)));
    escreverEntrada({ build: $("build").value, condicoes: {}, regen_externa: 0, echos: [] });
  } catch (erro) {
    status(erro.message, true);
  }
  $("analisar").addEventListener("click", analisarEntrada);
  $("extrair").addEventListener("click", extrairPrints);
  $("adicionar-echo").addEventListener("click", adicionarEchoVazio);
}

iniciar();
