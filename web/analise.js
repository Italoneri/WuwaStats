// Tela 4 · Análise: POST /api/analisar a cada mudança na entrada. A entrada vem da sessão de captura ou do envio manual.

import {
  ICONES, QUALIDADES, ampliar, api, avisoErro, carregarImagens, corNota, el, figura, elemento, estrelas, formatarValor, icone, iconeStat, lembrarPagina, moldura,
  parametro, perguntaCondicao, qualidade, rotulador, rotuloCondicao, silhueta,
} from "./comum.js";

const TOTAL_ECHOS = 5;
const MAX_SUBSTATUS = 5;
const CANDIDATOS_EXIBIDOS = 3;
const CHAVE_UPLOAD = "wuwastats:upload";
const CATEGORIAS = { stats: "status", echoes: "echos", sets: "sets" };

const estado = {
  fonte: null, // { tipo: "sessao", id } | { tipo: "upload" }
  entrada: null,
  leitura: null, // leitura da tela do personagem, se houver
  prints: null, // { echos: [{ espaco, captura } | null], personagem } — de onde veio cada echo na sessão de captura
  analise: null,
  build: null,
  personagem: null,
  rotulo: null,
  edicao: null, // { echo, sub } (sub = índice novo para adicionar) | { echo, completo: true } | { novo: true }
  mapeados: [],
  erro: null,
};

const principal = moldura("analise");
carregar();

// ---------- Carga e persistência ----------

async function carregar() {
  try {
    estado.fonte = fonteDaUrl();
    if (!estado.fonte) return desenharSemEntrada();
    const [builds, personagens, catalogo, origem] = await Promise.all([api.builds(), api.personagens(), api.catalogo(), carregarOrigem(), carregarImagens()]);
    Object.assign(estado, origem);
    estado.rotulo = rotulador(catalogo);
    estado.build = builds.find((b) => b.chave === estado.entrada.build);
    estado.personagem = personagens.find((p) => p.chave === estado.build?.personagem);
    lembrarPagina("analise", `analise.html${location.search}`);
    await reanalisar();
  } catch (erro) {
    principal.replaceChildren(el("div", { class: "wrap pilha" }, voltar(), avisoErro(erro)));
  }
}

function fonteDaUrl() {
  const sessao = parametro("sessao");
  if (sessao) return { tipo: "sessao", id: sessao };
  return parametro("origem") === "upload" ? { tipo: "upload" } : null;
}

function chaveEdicoes() {
  return `wuwastats:analise:${estado.fonte.tipo === "sessao" ? estado.fonte.id : "upload"}`;
}

/** Edições anteriores (mesma sessão/envio) têm prioridade sobre o que veio do servidor. */
async function carregarOrigem() {
  const salvo = lerSessao(chaveEdicoes());
  if (salvo) return salvo;
  if (estado.fonte.tipo === "upload") {
    const extracao = lerSessao(CHAVE_UPLOAD);
    if (!extracao?.entrada) throw new Error("O envio manual não está mais disponível. Envie os prints de novo na Captura.");
    return { entrada: extracao.entrada, leitura: extracao.personagem?.tipo === "ok" ? extracao.personagem.leitura : null, prints: null };
  }
  const [entrada, sessao] = await Promise.all([api.captura.entrada(estado.fonte.id), api.captura.estado(estado.fonte.id)]);
  return { entrada, leitura: sessao.personagem.estado === "lido" ? sessao.personagem.leitura : null, prints: printsDaSessao(sessao) };
}

/** A entrada da sessão traz só os echos lidos, na ordem dos espaços: o k-ésimo echo é o k-ésimo espaço lido. */
function printsDaSessao(sessao) {
  const echos = sessao.echos.flatMap((e, i) => (e.estado === "lido" ? [{ espaco: String(i), captura: e.captura }] : []));
  const personagem = sessao.personagem.estado === "vazio" ? null : { espaco: "personagem", captura: sessao.personagem.captura };
  return { echos, personagem };
}

function verPrint(print, legenda) {
  if (!print || estado.fonte.tipo !== "sessao") return null;
  const src = `/api/captura/${encodeURIComponent(estado.fonte.id)}/imagens/${print.espaco}?captura=${print.captura}`;
  return () => ampliar(src, legenda);
}

function lerSessao(chave) {
  try {
    const texto = sessionStorage.getItem(chave);
    return texto ? JSON.parse(texto) : null;
  } catch (erro) {
    console.warn("análise: não consegui ler", chave, erro);
    return null;
  }
}

function salvarEdicoes() {
  try {
    sessionStorage.setItem(chaveEdicoes(), JSON.stringify({ entrada: estado.entrada, leitura: estado.leitura, prints: estado.prints }));
  } catch (erro) {
    console.warn("análise: edições não serão lembradas ao recarregar", erro);
  }
}

async function reanalisar() {
  try {
    estado.analise = await api.analisar(estado.entrada);
    estado.erro = null;
    salvarEdicoes();
  } catch (erro) {
    estado.erro = erro.message;
  }
  desenhar();
}

function mudarEntrada(mudanca) {
  const entrada = structuredClone(estado.entrada);
  mudanca(entrada);
  estado.entrada = entrada;
  estado.edicao = null;
  return reanalisar();
}

// ---------- Moldura da página ----------

function voltar() {
  const build = estado.entrada?.build ?? "";
  const sessao = estado.fonte?.tipo === "sessao" ? `&sessao=${encodeURIComponent(estado.fonte.id)}` : "";
  return el("a", { class: "back", href: `captura.html?build=${encodeURIComponent(build)}${sessao}` }, icone(ICONES.voltar, 18, { espessura: 2 }), "Voltar para a captura");
}

function desenharSemEntrada() {
  principal.replaceChildren(
    el(
      "div",
      { class: "wrap" },
      el("header", { class: "cabeca" }, el("h1", {}, "Análise")),
      el(
        "div",
        { class: "vazio-msg" },
        el("strong", {}, "Nenhuma análise aberta"),
        el("p", {}, "Capture os echos (F8/F9) ou envie os prints na página de Captura."),
        el("a", { class: "chip on", href: "captura.html" }, "Ir para a captura"),
      ),
    ),
  );
}

function desenhar() {
  const { analise } = estado;
  principal.replaceChildren(
    el(
      "div",
      { class: "wrap pilha", style: { gap: "24px" } },
      el(
        "div",
        { style: { display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: "12px" } },
        voltar(),
        el("button", { class: "btn", type: "button", disabled: true, title: "Em breve" }, icone(ICONES.imagem, 16, { espessura: 2 }), "Exportar imagem"),
      ),
      estado.erro ? avisoErro(new Error(estado.erro)) : null,
      analise ? folha(analise) : null,
      analise ? abaixo(analise) : null,
    ),
  );
}

// ---------- Folha (card da build) ----------

function folha(analise) {
  return el(
    "section",
    { class: "sheet", "aria-label": `Card de build ${estado.personagem?.nome ?? analise.personagem}` },
    colunaEsquerda(analise),
    el(
      "div",
      { style: { display: "flex", flexDirection: "column", gap: "22px", minWidth: 0 } },
      el(
        "div",
        { class: "top", style: { display: "grid", gridTemplateColumns: "minmax(0, 1fr) 400px", gap: "28px" } },
        el("div", { style: { display: "flex", flexDirection: "column", gap: "18px", minWidth: 0 } }, titulo(analise), atributos()),
        resumo(analise),
      ),
      etiquetas(analise),
      el("div", { class: "ecards" }, analise.echos.map(cartaoEcho), analise.echos.length < TOTAL_ECHOS ? cartaoNovo() : null),
      legenda(),
    ),
  );
}

function colunaEsquerda(analise) {
  const cor = elemento(estado.personagem?.elemento.chave).cor;
  const { score_medio_pct: score, nota_media: nota } = analise.conjunto;
  return el(
    "div",
    { style: { display: "flex", flexDirection: "column", gap: "16px" } },
    el("div", { class: "ph", style: { width: "100%", aspectRatio: "4 / 5", borderRadius: "14px", placeItems: "end center", overflow: "hidden", borderColor: "#3A2F52" } }, figura("personagens", estado.personagem?.chave, silhueta(cor, "", "80%"), { trocavel: true, rotulo: estado.personagem?.nome })),
    painelArma(),
    botaoPrintPersonagem(),
    el(
      "div",
      { class: "panel", style: { padding: "18px 20px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "16px", borderColor: "var(--borda-hover)" } },
      el(
        "div",
        { style: { display: "flex", flexDirection: "column", gap: "4px" } },
        el("span", { class: "label", style: { color: "var(--lilas)" } }, "Echo Score"),
        el("span", { class: "mono", style: { fontSize: "44px", fontWeight: 700, lineHeight: 1 } }, score.toFixed(1)),
        el("span", { style: { fontSize: "13px", color: "var(--mudo)" } }, `média dos ${analise.echos.length} echos`),
      ),
      el("span", { class: "grade", style: { fontSize: "76px", color: corNota(nota) } }, nota),
    ),
  );
}

function botaoPrintPersonagem() {
  const abrir = verPrint(estado.prints?.personagem, "Print da tela do personagem");
  return abrir ? el("button", { class: "btn-print", type: "button", onclick: abrir }, icone(ICONES.imagem, 16), "Ver print da tela do personagem") : null;
}

function painelArma() {
  const leitura = estado.leitura;
  const arma = leitura?.arma ? armaDoCatalogo(leitura.arma) : null;
  const detalhes = [leitura?.arma_nivel ? `Nv. ${leitura.arma_nivel}` : null, leitura?.arma_rank ? `Rank ${leitura.arma_rank}` : null].filter(Boolean);
  return el(
    "div",
    { class: "panel", style: { padding: "16px", display: "flex", gap: "14px", alignItems: "center" } },
    el("span", { class: "ph", style: { width: "60px", height: "60px", borderRadius: "10px", overflow: "hidden" } }, figura("armas", arma?.chave, icone(ICONES.imagem, 24), { trocavel: true, rotulo: leitura?.arma })),
    el(
      "div",
      { style: { display: "flex", flexDirection: "column", gap: "3px", minWidth: 0 } },
      el("span", { style: { fontSize: "17px", fontWeight: 800, color: leitura?.arma ? "var(--lilas)" : "var(--mudo)" } }, leitura?.arma ?? "Arma não lida"),
      el("span", { style: { fontSize: "13px", color: "var(--mudo)" } }, detalhes.length ? detalhes.join(" · ") : leitura ? "Nível e rank não visíveis" : "Capture a tela do personagem"),
      arma ? el("span", { class: "estrelas", style: { fontSize: "13px" }, "aria-label": `${arma.raridade} estrelas` }, estrelas(arma.raridade)) : null,
    ),
  );
}

function armaDoCatalogo(nomeLido) {
  const alvo = nomeLido.trim().toLocaleLowerCase("pt-BR");
  return [...estado.rotulo.armas.values()].find((a) => [a.chave, ...a.nomes].some((n) => n.toLocaleLowerCase("pt-BR") === alvo)) ?? null;
}

function titulo(analise) {
  const personagem = estado.personagem;
  const cor = elemento(personagem?.elemento.chave);
  const variante = analise.variante === null ? "perfil base" : rotuloCondicao(estado.build.variantes[analise.variante].condicao);
  return el(
    "div",
    { style: { display: "flex", flexDirection: "column", gap: "8px" } },
    el(
      "div",
      { style: { display: "flex", flexWrap: "wrap", alignItems: "center", gap: "14px" } },
      el("h1", { style: { margin: 0, fontSize: "44px", fontWeight: 800, letterSpacing: "-0.02em", lineHeight: 1 } }, personagem?.nome ?? analise.personagem),
      personagem
        ? el("span", { title: personagem.elemento.nome, style: { width: "34px", height: "34px", borderRadius: "50%", display: "grid", placeItems: "center", border: `1px solid ${cor.cor}66`, background: `${cor.cor}1F` } }, icone(cor.d, 18, { espessura: 2, cor: cor.cor }))
        : null,
      estado.leitura?.nivel ? el("span", { class: "tag mono" }, `Nv. ${estado.leitura.nivel}`) : null,
    ),
    el(
      "p",
      { style: { margin: 0, fontSize: "15px", color: "var(--mudo)" } },
      "Build analisada: ",
      el("strong", { style: { color: "var(--lilas)" } }, analise.build.replaceAll("_", " ")),
      ` · ${variante}`,
    ),
  );
}

function atributos() {
  const lista = estado.leitura?.atributos ?? [];
  const conteudo = lista.length
    ? lista.map((a) =>
        el(
          "div",
          { class: "attr" },
          icone(iconeStat(a.stat), 16),
          el("span", {}, a.stat),
          el("span", { class: "lead", "aria-hidden": "true" }),
          el("span", { class: `mono ${a.valor === 0 ? "zero" : "gold"}` }, formatarValor(a.valor, a.percentual)),
        ),
      )
    : el("p", { style: { margin: 0, fontSize: "14px", color: "var(--mudo)", gridColumn: "1 / -1" } }, "Atributos totais aparecem aqui com o print da tela do personagem.");
  return el("div", { class: "attrs", style: { paddingTop: "14px", borderTop: "1px solid var(--borda)" } }, conteudo);
}

// ---------- Resumo da build ----------

const SINAL = {
  true: () => icone(ICONES.ok, 20, { espessura: 2.6, cor: "var(--verde)" }),
  false: () => icone(ICONES.atencao, 20, { espessura: 2.2, cor: "var(--laranja)" }),
  null: () => el("span", { "aria-hidden": "true", style: { color: "var(--mudo)" } }, "—"),
};
const ROTULO_SINAL = { true: "OK", false: "Atenção", null: "Sem o que conferir" };

function linhaResumo(ok, rotulo, ...conteudo) {
  return el("div", { class: "sumrow" }, el("span", { role: "img", "aria-label": ROTULO_SINAL[ok] }, SINAL[ok]()), el("strong", {}, rotulo), el("span", {}, ...conteudo));
}

const mudo = (texto) => el("span", { style: { color: "var(--mudo)" } }, texto);

function resumo(analise) {
  const { regen, custos, set, echo_principal: echoPrincipal } = analise.conjunto;
  const r = estado.rotulo;
  const partes = [`${regen.base}`, `echos ${regen.echos}`, `sets ${regen.sets}`, regen.externa ? `externa ${regen.externa}` : null].filter(Boolean);
  const fileira = (rotulo, lista) => el("span", { style: { display: "flex", alignItems: "center", gap: "4px" } }, el("span", { style: { width: "56px", color: "var(--mudo)", fontSize: "13px" } }, rotulo), lista.map((c) => el("span", { class: "cost sm" }, String(c))));
  return el(
    "aside",
    { class: "panel", style: { padding: "6px 20px 8px" }, "aria-label": "Resumo da build" },
    el("h2", { class: "label", style: { margin: 0, padding: "14px 0 6px", color: "#D9D0EE" } }, "Resumo da build"),
    linhaResumo(
      regen.atinge,
      "Regen",
      el("span", { class: "gold mono" }, `${regen.total}%`),
      ` = ${partes.join(" + ")} `,
      mudo(`· mínimo ${regen.minimo}%`),
      regen.informado !== null ? mudo(` · tela ${regen.informado}%`) : null,
      el("label", { style: { display: "flex", alignItems: "center", gap: "8px", marginTop: "6px", fontSize: "13px", color: "var(--mudo)" } }, "Regen externa (arma, cadeia)", el("input", { class: "campo", type: "number", step: "0.1", style: { width: "80px" }, value: estado.entrada.regen_externa ?? 0, onchange: (e) => mudarEntrada((en) => { en.regen_externa = Number(e.target.value) || 0; }) })),
    ),
    linhaResumo(custos.ok, "Custos", el("span", { style: { display: "flex", flexDirection: "column", gap: "6px" } }, fileira("atual", custos.atual), fileira("pedido", custos.esperado))),
    linhaResumo(set.ok, "Set", set.esperado ? r.set(set.esperado) : "Livre", " ", mudo(`· ${set.pecas_equipadas}/${set.pecas_necessarias ?? "?"} peças`)),
    linhaResumo(
      echoPrincipal.ok,
      "Eco principal",
      echoPrincipal.esperado ? r.echo(echoPrincipal.esperado) : "Livre",
      echoPrincipal.ok === false ? mudo(` · equipado: ${r.echo(echoPrincipal.atual) ?? "desconhecido"}`) : null,
    ),
  );
}

function etiquetas(analise) {
  const c = analise.conjunto;
  const r = estado.rotulo;
  const etiqueta = (rotulo, valor) => el("span", { class: "tag" }, el("span", { style: { color: "var(--mudo)" } }, rotulo), el("span", { class: "gold mono" }, valor));
  return el(
    "div",
    { class: "tags" },
    etiqueta("CV:", String(c.cv)),
    etiqueta("CV c/ principal:", String(c.cv_com_principal)),
    etiqueta("Score médio", `${c.score_medio_pct}%`),
    c.set.bonus_ativos.map((b) => el("span", { class: "tag" }, el("span", { class: "seti", style: { position: "static", width: "20px", height: "20px" } }, icone(ICONES.sonata, 11, { espessura: 2.4 })), `${r.set(b.set)} (${b.pecas})`)),
    analise.nomes_desconhecidos.map((n) => el("span", { class: "tag dash" }, `${n.nome_lido} (${n.echos.length}) · não mapeado`)),
  );
}

// ---------- Cards de echo ----------

function cartaoEcho(echo) {
  const r = estado.rotulo;
  const i = echo.indice;
  const nome = r.echo(echo.nome) ?? echo.nome_lido ?? "Echo sem nome";
  if (estado.edicao?.echo === i && estado.edicao.completo) return cartaoFormulario(`Editar echo ${i + 1}`, estado.entrada.echos[i], echo.principal.stat, (novo) => mudarEntrada((en) => { en.echos[i] = { ...novo, substatus: en.echos[i].substatus }; }));
  const avisos = echo.problemas.filter((p) => p.severidade === "revisao" || p.severidade === "mapeamento");
  const nomeSet = echo.set ? r.set(echo.set) : echo.set_lido ? `${echo.set_lido} (não mapeado)` : "Sem set";
  const principal = echo.principal;
  const percentualPrincipal = r.stats.get(principal.stat)?.percentual ?? true;
  return el(
    "article",
    { class: `ecard${echo.revisao ? " review" : ""}`, "aria-label": `Echo ${i + 1}: ${nome}, score ${echo.score_pct}` },
    el(
      "header",
      { class: "ehead" },
      el("span", { class: "ename", title: nome }, `${i + 1}. ${nome}`),
      avisos.length
        ? el("button", { class: "wbtn", type: "button", "aria-label": `Precisa de revisão: ${avisos.map((p) => p.mensagem).join(" ")}` }, icone(ICONES.atencao, 16, { espessura: 2.2 }), el("span", { class: "tip", "aria-hidden": "true" }, avisos.map((p) => p.mensagem).join("\n")))
        : null,
      botaoPrintEcho(i),
      el("button", { class: "ibtn", type: "button", title: "Editar nome, custo, set e principal", "aria-label": `Editar echo ${i + 1}`, onclick: () => editar({ echo: i, completo: true }) }, icone("M4 20h4L19 9l-4-4L4 16zM14 6l4 4", 15)),
    ),
    el(
      "div",
      { class: "etop" },
      el(
        "span",
        { class: "ph eimg" },
        figura("echoes", echo.nome, icone(ICONES.echo, 26, { espessura: 1.6, cor: "#6E5C96" }), { trocavel: true, rotulo: nome }),
        el("span", { class: `seti${echo.set ? "" : " unk"}`, title: nomeSet }, icone(ICONES.sonata, 11, { espessura: 2.4 })),
        el("span", { class: "costcorner" }, String(echo.custo)),
      ),
      el(
        "div",
        { class: "emain" },
        el("span", { class: "mlabel" }, principal.stat ? r.stat(principal.stat) : principal.stat_lido),
        el("span", { class: "mval" }, formatarValor(principal.valor, percentualPrincipal)),
        el("span", { class: "ecost" }, `Custo ${echo.custo} · ${nomeSet}`),
      ),
    ),
    el("ul", { class: "subs" }, echo.substatus.map((s, j) => el("li", {}, estado.edicao?.echo === i && estado.edicao.sub === j ? editorSubstat(i, j, s) : linhaSubstat(i, j, s))), estado.edicao?.echo === i && estado.edicao.sub === echo.substatus.length ? el("li", {}, editorSubstat(i, echo.substatus.length, null)) : null),
    echo.substatus.length < MAX_SUBSTATUS && estado.edicao?.echo !== i ? el("button", { class: "mais", type: "button", onclick: () => editar({ echo: i, sub: echo.substatus.length }) }, "+ substatus") : null,
    el(
      "footer",
      { class: "efoot" },
      el("span", { style: { fontSize: "12px", fontWeight: 800, letterSpacing: "0.1em", color: "var(--mudo)" } }, "SCORE ", el("span", { class: "mono", style: { fontSize: "16px", color: "var(--texto)", letterSpacing: 0 } }, echo.score_pct.toFixed(1))),
      el("span", { class: "grade", style: { color: corNota(echo.nota) } }, echo.nota),
    ),
  );
}

function botaoPrintEcho(i) {
  const abrir = verPrint(estado.prints?.echos[i], `Print do echo ${i + 1}`);
  return abrir ? el("button", { class: "ibtn", type: "button", title: "Ver o print", "aria-label": `Ver o print do echo ${i + 1}`, onclick: abrir }, icone(ICONES.imagem, 15)) : null;
}

function editar(edicao) {
  estado.edicao = edicao;
  desenhar();
}

function linhaSubstat(i, j, s) {
  const r = estado.rotulo;
  if (s.tipo === "invalido") {
    const motivo = s.motivo === "desconhecido" ? "nome desconhecido" : "não é substatus";
    return el(
      "button",
      { type: "button", class: "sub invalido", "aria-label": `${s.stat_lido} ${s.valor_lido}: ${motivo}. Editar`, onclick: () => editar({ echo: i, sub: j }) },
      el("span", { class: "sline" }, icone(ICONES.atencao, 14, { espessura: 2, cor: "var(--vermelho-claro)" }), el("span", { class: "sub-nome" }, s.stat_lido), el("span", { class: "sval c-fail" }, String(s.valor_lido))),
      el("span", { style: { fontSize: "11px", color: "var(--vermelho-claro)" } }, motivo),
    );
  }
  const q = qualidade(s.tier, s.tiers_total);
  const percentual = r.stats.get(s.stat)?.percentual ?? true;
  const valor = formatarValor(s.valor, percentual);
  return el(
    "button",
    { type: "button", class: `sub${s.peso > 0 ? " hl" : ""}`, "aria-label": `${r.stat(s.stat)} ${valor}, rolagem ${q.nome}. Editar`, onclick: () => editar({ echo: i, sub: j }) },
    el("span", { class: "sline" }, icone(iconeStat(s.stat), 14, { espessura: 2 }), el("span", { class: "sub-nome" }, r.stat(s.stat)), el("span", { class: "sval", style: { color: q.cor } }, valor)),
    el("span", { class: "track", "aria-hidden": "true" }, el("span", { class: "fill", style: { width: `${s.posicao_pct}%`, background: q.cor } })),
  );
}

function opcoesDeStat(filtro, selecionada) {
  const r = estado.rotulo;
  return [...r.stats.values()]
    .filter(filtro)
    .map((s) => ({ chave: s.chave, rotulo: r.stat(s.chave) }))
    .sort((a, b) => a.rotulo.localeCompare(b.rotulo, "pt-BR"))
    .map((o) => el("option", { value: o.chave, selected: o.chave === selecionada }, o.rotulo));
}

function editorSubstat(i, j, analisado) {
  const atual = estado.entrada.echos[i].substatus[j];
  const statAtual = analisado?.tipo === "valido" ? analisado.stat : null;
  const seletor = el("select", { "aria-label": "Status" }, el("option", { value: "" }, "Escolha o status"), opcoesDeStat((s) => s.substatus !== null, statAtual));
  const valor = el("input", { type: "number", step: "0.1", "aria-label": "Valor", value: atual?.valor ?? "" });
  const confirmar = () => {
    if (!seletor.value || valor.value === "") return;
    const percentual = estado.rotulo.stats.get(seletor.value).percentual;
    mudarEntrada((en) => {
      en.echos[i].substatus[j] = { stat: seletor.value, valor: Number(valor.value), percentual };
    });
  };
  return el(
    "div",
    { class: "edit", onkeydown: (e) => e.key === "Enter" && confirmar() },
    seletor,
    valor,
    el("button", { type: "button", onclick: confirmar }, "OK"),
    atual ? el("button", { type: "button", class: "secundario", title: "Remover substatus", onclick: () => mudarEntrada((en) => en.echos[i].substatus.splice(j, 1)) }, "Remover") : null,
    el("button", { type: "button", class: "secundario", onclick: () => editar(null) }, "Cancelar"),
  );
}

// ---------- Echo adicionado ou corrigido à mão ----------

function cartaoNovo() {
  if (estado.edicao?.novo) {
    return cartaoFormulario("Novo echo", null, null, (novo, posicao) => {
      estado.prints?.echos.splice(posicao, 0, null);
      return mudarEntrada((en) => en.echos.splice(posicao, 0, { ...novo, substatus: [] }));
    });
  }
  return el(
    "div",
    { class: "ecard novo" },
    icone(ICONES.echo, 28, { espessura: 1.6, cor: "#6E5C96" }),
    el("span", {}, `${TOTAL_ECHOS - estado.analise.echos.length} echo(s) não lido(s). Preencha à mão:`),
    el("button", { class: "btn sm on", type: "button", onclick: () => editar({ novo: true }) }, "Adicionar echo"),
  );
}

/** atual: echo da entrada (null = novo); statResolvido: chave do principal segundo a análise, se reconhecido. */
function cartaoFormulario(titulo, atual, statResolvido, salvar) {
  const r = estado.rotulo;
  const listas = el(
    "div",
    {},
    el("datalist", { id: "lista-echos" }, [...r.echoes.keys()].map((k) => el("option", { value: r.echo(k) }))),
    el("datalist", { id: "lista-sets" }, [...r.sets.keys()].map((k) => el("option", { value: r.set(k) }))),
  );
  const nome = el("input", { class: "campo", list: "lista-echos", value: atual?.nome ?? "" });
  const custo = el("select", { class: "campo" }, [4, 3, 1].map((c) => el("option", { value: c, selected: c === (atual?.custo ?? 1) }, String(c))));
  const set = el("input", { class: "campo", list: "lista-sets", value: atual?.set ?? "" });
  const statPrincipal = el("select", { class: "campo" }, el("option", { value: "" }, "Escolha…"), opcoesDeStat((s) => Object.keys(s.principal).length > 0, statResolvido));
  if (atual && !statResolvido) statPrincipal.append(el("option", { value: atual.principal.stat, selected: true }, `${atual.principal.stat} (lido)`));
  const valorPrincipal = el("input", { class: "campo mono", type: "number", step: "0.1", value: atual?.principal.valor ?? "" });
  const total = estado.entrada.echos.length;
  const posicao = el("select", { class: "campo" }, Array.from({ length: total + 1 }, (_, p) => el("option", { value: p, selected: p === total }, `Echo ${p + 1}`)));
  const confirmar = () => {
    if (!statPrincipal.value || valorPrincipal.value === "") return;
    const percentual = r.stats.get(statPrincipal.value)?.percentual ?? atual?.principal.percentual ?? null;
    salvar(
      {
        nome: nome.value.trim() || null,
        custo: Number(custo.value),
        set: set.value.trim() || null,
        principal: { stat: statPrincipal.value, valor: Number(valorPrincipal.value), percentual },
      },
      Number(posicao.value),
    );
  };
  const campo = (rotulo, controle) => el("label", {}, rotulo, controle);
  return el(
    "div",
    { class: "ecard", style: { padding: "14px", gap: "10px" } },
    listas,
    el("strong", { style: { fontSize: "13px" } }, titulo),
    el(
      "div",
      { class: "form-echo" },
      campo("Nome", nome),
      el("div", { class: "linha" }, campo("Custo", custo), atual ? null : campo("Posição", posicao)),
      campo("Set", set),
      el("div", { class: "linha" }, campo("Principal", statPrincipal), campo("Valor", valorPrincipal)),
      el(
        "div",
        { class: "edit", style: { border: 0, padding: 0, background: "transparent" } },
        el("button", { type: "button", onclick: confirmar }, atual ? "Salvar" : "Adicionar"),
        el("button", { type: "button", class: "secundario", onclick: () => editar(null) }, "Cancelar"),
      ),
    ),
  );
}

function legenda() {
  return el(
    "p",
    { class: "legenda" },
    el("span", {}, "Qualidade da rolagem:"),
    QUALIDADES.map((q) => el("span", { style: { color: q.cor } }, `● ${q.nome}`)),
    el("span", { style: { padding: "2px 8px", borderRadius: "6px", background: "rgba(182, 156, 255, 0.09)" } }, "fundo destacado = status com peso na build"),
    el("span", {}, "· clique num status para editar"),
  );
}

// ---------- Painéis de baixo ----------

function abaixo(analise) {
  return el("div", { class: "below" }, candidatos(analise), dicionario(analise), condicoes(analise));
}

function candidatos(analise) {
  const r = estado.rotulo;
  return el(
    "section",
    { class: "panel", "aria-labelledby": "cand-t" },
    el("h2", { id: "cand-t" }, "Candidatos a troca"),
    el("p", { style: { margin: "4px 0 0", fontSize: "13px", color: "var(--mudo)" } }, "Do pior para o melhor echo"),
    el(
      "ol",
      { class: "cand" },
      analise.candidatos_troca.slice(0, CANDIDATOS_EXIBIDOS).map((c, n) => {
        const echo = analise.echos[c.indice];
        return el(
          "li",
          {},
          el("span", { class: "mono", style: { fontSize: "14px", fontWeight: 700, color: "var(--mudo-2)", paddingTop: "2px" } }, `${n + 1}.`),
          el(
            "span",
            { style: { display: "flex", flexDirection: "column", gap: "4px", minWidth: 0 } },
            el("strong", { style: { fontSize: "15px" } }, r.echo(echo.nome) ?? c.nome ?? "Echo sem nome", " ", el("span", { style: { fontWeight: 600, color: "var(--mudo)" } }, `· Echo ${c.indice + 1} · custo ${echo.custo}`)),
            el("span", { style: { fontSize: "14px", color: "var(--texto-2)", lineHeight: 1.45 } }, c.motivos.join(" ")),
          ),
          el("span", { class: "grade", style: { fontSize: "22px", color: corNota(c.nota) } }, c.nota),
        );
      }),
    ),
  );
}

function dicionario(analise) {
  const pendentes = analise.nomes_desconhecidos;
  return el(
    "section",
    { class: "panel", "aria-labelledby": "dic-t", style: { borderColor: pendentes.length ? "#6B4A33" : "var(--borda)" } },
    el("h2", { id: "dic-t" }, pendentes.length ? icone(ICONES.atencao, 18, { espessura: 2.2, cor: "var(--laranja)" }) : icone(ICONES.ok, 18, { espessura: 2.6, cor: "var(--verde)" }), "Nomes fora do dicionário"),
    pendentes.length ? pendentes.map(mapeamento) : el("p", { style: { margin: "16px 0 0", fontSize: "14px", color: "var(--mudo)" } }, "Todos os nomes foram reconhecidos."),
    estado.mapeados.map((m) => el("p", { style: { margin: "12px 0 0", fontSize: "14px", color: "var(--verde)" } }, `✓ '${m.alias}' agora aponta para ${m.rotulo}.`)),
  );
}

function mapeamento(item) {
  const r = estado.rotulo;
  const fontes = { stats: [r.stats, r.stat], echoes: [r.echoes, r.echo], sets: [r.sets, r.set] };
  const [mapa, rotular] = fontes[item.categoria];
  const opcoes = [...mapa.keys()].map((k) => ({ chave: k, rotulo: rotular(k) })).sort((a, b) => a.rotulo.localeCompare(b.rotulo, "pt-BR"));
  const id = `map-${item.categoria}-${item.nome_lido}`.replace(/\W+/g, "-");
  const seletor = el("select", { id, class: "campo", style: { flex: "1 1 200px", height: "40px", fontSize: "14px" } }, el("option", { value: "" }, "Escolha…"), opcoes.map((o) => el("option", { value: o.chave }, o.rotulo)));
  const mapear = async () => {
    if (!seletor.value) return;
    try {
      await api.mapear({ categoria: item.categoria, chave: seletor.value, alias: item.nome_lido });
      estado.mapeados.push({ alias: item.nome_lido, rotulo: rotular(seletor.value) });
      await reanalisar();
    } catch (erro) {
      estado.erro = erro.message;
      desenhar();
    }
  };
  return el(
    "div",
    { style: { display: "flex", flexDirection: "column", gap: "12px", marginTop: "16px" } },
    el(
      "p",
      { style: { margin: 0, fontSize: "14px", lineHeight: 1.5 } },
      el("span", { class: "mono", style: { color: "var(--mudo)" } }, `${CATEGORIAS[item.categoria]}:`),
      " ",
      el("strong", { style: { color: "#FFC08F" } }, `'${item.nome_lido}'`),
      " ",
      mudo(`(echos ${item.echos.map((i) => i + 1).join(", ")})`),
      " →",
    ),
    el("div", { style: { display: "flex", flexWrap: "wrap", gap: "8px" } }, el("label", { class: "sr", for: id }, `Mapear '${item.nome_lido}' para`), seletor, el("button", { class: "btn sm on", type: "button", onclick: mapear }, "Mapear")),
  );
}

function condicoes(analise) {
  const chaves = estado.build?.condicoes ?? [];
  return el(
    "section",
    { class: "panel", "aria-labelledby": "cond-t" },
    el("h2", { id: "cond-t" }, analise.condicoes_pendentes.length ? "Condição pendente" : "Condições"),
    chaves.length ? chaves.map((chave) => condicao(chave, analise)) : el("p", { style: { margin: "16px 0 0", fontSize: "14px", color: "var(--mudo)" } }, "Esta build não tem variantes por condição."),
  );
}

function condicao(chave, analise) {
  const valor = estado.entrada.condicoes?.[chave] ?? null;
  const pendente = analise.condicoes_pendentes.includes(chave);
  const responder = (resposta) => mudarEntrada((en) => { en.condicoes = { ...(en.condicoes ?? {}), [chave]: resposta }; });
  const botao = (resposta, texto) => el("button", { class: `btn sm${valor === resposta ? " on" : ""}`, type: "button", "aria-pressed": String(valor === resposta), onclick: () => responder(resposta) }, texto);
  const nota = pendente
    ? "Responda para escolher a variante da build. Até lá vale o perfil base."
    : analise.variante === null
      ? "Usando o perfil base."
      : `Variante aplicada: ${rotuloCondicao(estado.build.variantes[analise.variante].condicao)}.`;
  return el(
    "div",
    {},
    el("p", { style: { margin: "16px 0 12px", fontSize: "15px" } }, perguntaCondicao(chave)),
    el("div", { style: { display: "flex", gap: "8px" }, role: "group", "aria-label": perguntaCondicao(chave) }, botao(true, "Sim"), botao(false, "Não")),
    el("p", { style: { margin: "12px 0 0", fontSize: "13px", color: "var(--mudo)" } }, nota),
  );
}
