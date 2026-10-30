// Tela 3 · Captura: liga os atalhos no servidor e acompanha os 5 espaços de echo + o do personagem pelos eventos (SSE).

import { ICONES, api, avisoErro, el, icone, lembrarPagina, miniaturaAmpliavel, moldura, parametro, silhueta } from "./comum.js";

const TOTAL_ECHOS = 5;
const TIPOS_EVENTO = ["estado", "print_recebido", "leitura_iniciada", "lido", "falhou", "ir_para_analise", "erro_captura", "encerrada"];
const PENDENTES = new Set(["recebido", "lendo"]);
const CHAVE_UPLOAD = "wuwastats:upload";

const VISUAL = {
  vazio: { classe: "vazio", tom: "c-muted", titulo: "Aguardando captura", detalhe: "" },
  recebido: { classe: "", tom: "c-muted", titulo: "Print recebido", detalhe: "Na fila para leitura" },
  lendo: { classe: "", tom: "c-read", titulo: "Lendo com IA…", detalhe: "Identificando status e set" },
  lido: { classe: "", tom: "c-ok", titulo: "✓ Lido", detalhe: "" },
  falhou: { classe: "fail", tom: "c-fail", titulo: "Falhou ao ler", detalhe: "Preencha à mão na análise ou use Refazer" },
};

const estado = {
  builds: [],
  teclas: { echo: "F8", personagem: "F9", analise: "F10" },
  nomePorPersonagem: new Map(),
  build: parametro("build"),
  sessao: null,
  fonte: null,
  ultimoPrint: null,
  erro: null,
  ocupado: false,
  arrastando: null,
  sobre: null,
  redesenharDepoisDeArrastar: false,
};

const principal = moldura("captura");
setInterval(atualizarRelogio, 1000);
carregar();

async function carregar() {
  try {
    const [builds, personagens, teclas] = await Promise.all([api.builds(), api.personagens(), api.captura.teclas()]);
    estado.teclas = teclas;
    estado.builds = builds;
    estado.nomePorPersonagem = new Map(personagens.map((p) => [p.chave, p.nome]));
    await retomarSessao(parametro("sessao"));
    estado.build ??= builds[0]?.chave ?? null;
    atualizarUrl(estado.sessao?.id ?? null);
    desenhar();
  } catch (erro) {
    principal.replaceChildren(el("div", { class: "wrap" }, avisoErro(erro)));
  }
}

async function retomarSessao(id) {
  if (!id) return;
  try {
    estado.sessao = await api.captura.estado(id);
    estado.build = estado.sessao.build;
    if (estado.sessao.ativa) conectar(id);
  } catch (erro) {
    if (erro.status !== 404) throw erro;
    atualizarUrl(null); // sessão antiga (servidor reiniciado ou outra sessão iniciada): começa do zero
  }
}

// ---------- Ações ----------

async function executar(acao) {
  estado.ocupado = true;
  estado.erro = null;
  desenhar();
  try {
    await acao();
  } catch (erro) {
    estado.erro = erro.message;
  } finally {
    estado.ocupado = false;
    desenhar();
  }
}

const iniciar = () =>
  executar(async () => {
    desconectar();
    estado.sessao = await api.captura.iniciar(estado.build);
    estado.ultimoPrint = null;
    atualizarUrl(estado.sessao.id);
    conectar(estado.sessao.id);
  });

const parar = () => executar(() => api.captura.parar());

const alterar = (chamada) =>
  executar(async () => {
    estado.sessao = await chamada(estado.sessao.id);
  });

function atualizarUrl(sessaoId) {
  const url = new URL(location.href);
  url.searchParams.set("build", estado.build ?? "");
  if (sessaoId) url.searchParams.set("sessao", sessaoId);
  else url.searchParams.delete("sessao");
  history.replaceState(null, "", url);
  lembrarPagina("captura", `captura.html${url.search}`);
}

// ---------- Eventos do servidor ----------

function conectar(id) {
  desconectar();
  const fonte = api.captura.eventos(id);
  for (const tipo of TIPOS_EVENTO) fonte.addEventListener(tipo, (e) => aoEvento(JSON.parse(e.data)));
  fonte.onerror = () => {
    if (fonte.readyState === EventSource.CLOSED) estado.erro = "Conexão com o servidor perdida. Recarregue a página.";
    desenhar();
  };
  estado.fonte = fonte;
}

function desconectar() {
  estado.fonte?.close();
  estado.fonte = null;
}

function aoEvento(evento) {
  estado.sessao = evento.sessao;
  if (evento.tipo === "print_recebido") {
    estado.ultimoPrint = Date.now();
    estado.erro = null;
  }
  if (evento.tipo === "erro_captura") estado.erro = evento.motivo;
  if (evento.tipo === "encerrada") desconectar(); // sem isso o EventSource reconecta sozinho
  if (evento.tipo === "ir_para_analise") return irParaAnalise();
  desenhar();
}

function irParaAnalise() {
  const falta = motivoParaNaoAnalisar();
  if (falta) {
    estado.erro = `${estado.teclas.analise}: ${falta}`;
    return desenhar();
  }
  location.href = `analise.html?sessao=${encodeURIComponent(estado.sessao.id)}`;
}

/** Análise libera com os 5 espaços preenchidos e lidos (os que falharam se completam à mão lá). */
function motivoParaNaoAnalisar() {
  const echos = estado.sessao?.echos ?? [];
  const preenchidos = echos.filter((e) => e.estado !== "vazio").length;
  if (preenchidos < TOTAL_ECHOS) return `faltam ${TOTAL_ECHOS - preenchidos} prints de echo.`;
  if (echos.some((e) => PENDENTES.has(e.estado))) return "aguarde a leitura dos prints terminar.";
  if (!echos.some((e) => e.estado === "lido")) return "nenhum echo foi lido; use Refazer.";
  return null;
}

// ---------- Desenho ----------

function desenhar() {
  if (estado.arrastando !== null) {
    estado.redesenharDepoisDeArrastar = true;
    return;
  }
  principal.replaceChildren(
    el(
      "div",
      { class: "wrap pilha" },
      cabecalho(),
      estado.erro ? avisoErro(new Error(estado.erro)) : null,
      atalhos(),
      espacos(),
      envioManual(),
      rodape(),
    ),
  );
  atualizarRelogio();
}

function cabecalho() {
  const ativa = estado.sessao?.ativa ?? false;
  const seletor = el(
    "select",
    {
      class: "select",
      "aria-label": "Build da análise",
      disabled: ativa || estado.ocupado,
      onchange: (e) => {
        estado.build = e.target.value;
        estado.sessao = null;
        atualizarUrl(null);
        desenhar();
      },
    },
    estado.builds.map((b) =>
      el("option", { value: b.chave, selected: b.chave === estado.build }, `${estado.nomePorPersonagem.get(b.personagem) ?? b.personagem} — ${b.chave.replaceAll("_", " ")}`),
    ),
  );
  return el(
    "header",
    { class: "cabeca", style: { alignItems: "center" } },
    el("div", { style: { display: "flex", flexWrap: "wrap", alignItems: "center", gap: "24px" } }, el("h1", {}, "Captura"), seletor),
    ativa
      ? el(
          "div",
          { class: "status", role: "status" },
          el("span", { class: "sdot on", "aria-hidden": "true" }),
          el("span", {}, "Captura ligada"),
          el("span", { id: "relogio", style: { fontWeight: 500, color: "var(--mudo)" } }),
          el("button", { class: "btn", type: "button", disabled: estado.ocupado, onclick: parar }, "Parar captura"),
        )
      : el(
          "div",
          { class: "status", role: "status" },
          el("span", { class: "sdot", "aria-hidden": "true" }),
          el("span", { style: { color: "var(--texto-2)" } }, "Captura desligada"),
          el(
            "button",
            { class: "btn primary", type: "button", disabled: !estado.build || estado.ocupado, onclick: iniciar },
            icone(ICONES.captura, 18, { espessura: 2 }),
            "Iniciar captura",
          ),
        ),
  );
}

function atualizarRelogio() {
  const relogio = document.getElementById("relogio");
  if (!relogio) return;
  relogio.textContent = estado.ultimoPrint ? `· último print há ${Math.round((Date.now() - estado.ultimoPrint) / 1000)} s` : "· aguardando o primeiro print";
}

function atalhos() {
  const atalho = (tecla, texto) => el("span", { class: "sc" }, el("span", { class: "kbd" }, tecla), texto);
  return el(
    "div",
    { class: "strip", "aria-label": "Atalhos no jogo" },
    el("span", { class: "label" }, "Atalhos no jogo"),
    atalho(estado.teclas.echo, "Capturar echo"),
    atalho(estado.teclas.personagem, "Tela do personagem"),
    atalho(estado.teclas.analise, "Ver análise"),
  );
}

function espacos() {
  const echos = estado.sessao?.echos ?? Array.from({ length: TOTAL_ECHOS }, () => ({ estado: "vazio" }));
  return el(
    "section",
    { "aria-label": "Espaços de captura", style: { display: "flex", flexDirection: "column", gap: "14px" } },
    el(
      "div",
      { style: { display: "flex", flexWrap: "wrap", alignItems: "baseline", justifyContent: "space-between", gap: "12px" } },
      el("h2", { style: { margin: 0, fontSize: "18px", fontWeight: 800 } }, "Prints recebidos"),
      el("p", { style: { margin: 0, fontSize: "13px", color: "var(--mudo)" } }, "Arraste os echos para mudar a ordem. O 1º espaço é o echo principal."),
    ),
    el(
      "div",
      { class: "slots" },
      echos.map((espaco, i) => espacoEcho(espaco, i)),
      el("div", { class: "sep", "aria-hidden": "true" }),
      espacoPersonagem(estado.sessao?.personagem ?? { estado: "vazio" }),
    ),
  );
}

function espacoEcho(espaco, i) {
  const visual = VISUAL[espaco.estado];
  const rotulo = `Echo ${i + 1}`;
  const alvo = estado.sessao?.alvo_f8 === i;
  const comSessao = Boolean(estado.sessao);
  const classes = ["slot", visual.classe, estado.sobre === i ? "over" : "", alvo ? "alvo" : ""].filter(Boolean).join(" ");
  return el(
    "div",
    {
      class: classes,
      draggable: comSessao ? "true" : null,
      ondragstart: (e) => {
        estado.arrastando = i;
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", String(i));
      },
      ondragover: (e) => {
        if (estado.arrastando === null) return;
        e.preventDefault();
        marcarSobre(i);
      },
      ondragleave: () => marcarSobre(null),
      ondrop: (e) => {
        if (estado.arrastando === null) return;
        e.preventDefault();
        mover(estado.arrastando, i);
      },
      ondragend: terminarArraste,
    },
    el(
      "div",
      { class: "shead" },
      el("span", { class: "slot-nome" }, rotulo),
      i === 0 ? el("span", { class: "selo" }, "Echo principal") : null,
      alvo ? el("span", { class: "selo lilas" }, "Próximo F8") : null,
      comSessao ? el("span", { class: "grip", title: "Arraste para reordenar", "aria-hidden": "true" }, icone(ICONES.grip, 16, { espessura: 3 })) : null,
    ),
    espaco.estado === "vazio" ? el("div", { class: "emptybox" }, el("span", { class: "kbd" }, estado.teclas.echo), `Aperte ${estado.teclas.echo} no jogo`) : miniatura(espaco, rotulo, String(i)),
    el(
      "div",
      { class: "sfoot" },
      textoEspaco(visual, detalheEcho(espaco)),
      espaco.estado === "vazio"
        ? null
        : [
            el(
              "button",
              { class: "ibtn", type: "button", title: `Refazer: o próximo ${estado.teclas.echo} vem para este espaço`, "aria-label": `Refazer ${rotulo}`, disabled: estado.ocupado, onclick: () => alterar((id) => api.captura.refazer(id, i)) },
              icone(ICONES.refazer, 16, { espessura: 2 }),
            ),
            el(
              "button",
              { class: "ibtn", type: "button", title: "Remover", "aria-label": `Remover print do ${rotulo}`, disabled: estado.ocupado, onclick: () => alterar((id) => api.captura.esvaziarEcho(id, i)) },
              icone(ICONES.fechar, 16, { espessura: 2 }),
            ),
          ],
    ),
  );
}

function detalheEcho(espaco) {
  if (espaco.estado === "falhou") return espaco.motivo;
  if (espaco.estado !== "lido") return VISUAL[espaco.estado].detalhe;
  const { nome, principal: p } = espaco.echo;
  return `${nome ?? "Echo sem nome"} · ${p.stat} ${p.valor}${p.percentual === false ? "" : "%"}`;
}

function espacoPersonagem(espaco) {
  const visual = VISUAL[espaco.estado];
  return el(
    "div",
    { class: `slot ${visual.classe}` },
    el("div", { class: "shead" }, el("span", { class: "slot-nome" }, "Personagem"), el("span", { class: "selo lilas" }, estado.teclas.personagem)),
    espaco.estado === "vazio"
      ? el("div", { class: "emptybox wide" }, el("span", { class: "kbd" }, estado.teclas.personagem), `Aperte ${estado.teclas.personagem} no jogo`)
      : miniatura(espaco, "tela do personagem", "personagem", true),
    el(
      "div",
      { class: "sfoot" },
      textoEspaco(visual, detalhePersonagem(espaco)),
      espaco.estado === "vazio"
        ? null
        : el(
            "button",
            { class: "ibtn", type: "button", title: `Remover (ou aperte ${estado.teclas.personagem} de novo para substituir)`, "aria-label": "Remover print da tela do personagem", disabled: estado.ocupado, onclick: () => alterar((id) => api.captura.esvaziarPersonagem(id)) },
            icone(ICONES.fechar, 16, { espessura: 2 }),
          ),
    ),
  );
}

function detalhePersonagem(espaco) {
  if (espaco.estado === "falhou") return espaco.motivo;
  if (espaco.estado !== "lido") return VISUAL[espaco.estado].detalhe;
  const l = espaco.leitura;
  const partes = [l.personagem, l.nivel ? `Nv. ${l.nivel}` : null, l.arma].filter(Boolean);
  return partes.length ? partes.join(" · ") : "Nada legível na tela";
}

function textoEspaco(visual, detalhe) {
  return el("div", { class: "stext" }, el("span", { class: `stitle ${visual.tom}` }, visual.titulo), detalhe ? el("span", { class: "sdet" }, detalhe) : null);
}

/** Print real servido pela sessão; o desenho de placeholder fica de reserva se a imagem não carregar. */
function miniatura(espaco, rotulo, idEspaco, larga = false) {
  const lendo = PENDENTES.has(espaco.estado);
  const barras = [70, 45, 82, 64, 76, 58, 70].map((largura) => el("i", { style: { width: `${largura}%` } }));
  const reserva = el(
    "div",
    { style: { display: "flex", flexDirection: larga ? "row" : "column", gap: larga ? "14px" : "9px", padding: "18px 16px", height: "100%" } },
    larga
      ? [
          el("div", { style: { flex: "0 0 42%", borderRadius: "6px", background: "#241D33", display: "grid", placeItems: "end center", overflow: "hidden" } }, silhueta("#B57BFF", "", "80%")),
          el("div", { style: { flex: 1, display: "flex", flexDirection: "column", gap: "9px", paddingTop: "6px" } }, barras),
        ]
      : [icone(ICONES.echo, 34, { espessura: 1.6, cor: "#5A4C78" }), ...barras],
  );
  const src = `/api/captura/${encodeURIComponent(estado.sessao.id)}/imagens/${idEspaco}?captura=${espaco.captura}`;
  return el(
    "div",
    { class: `shot com-imagem${larga ? " wide" : ""}${espaco.estado === "lendo" ? " reading" : ""}` },
    miniaturaAmpliavel(src, `Print do ${rotulo}`, reserva),
    lendo ? el("div", { class: "ov" }, el("span", { class: "spin", style: { display: "grid" } }, icone(ICONES.girando, 30, { espessura: 2.4, cor: "#C4B1FF" }))) : null,
    espaco.estado === "lido" ? el("span", { class: "okb", "aria-hidden": "true" }, icone(ICONES.ok, 16, { espessura: 3 })) : null,
  );
}

// ---------- Arrastar para reordenar ----------

function marcarSobre(i) {
  if (estado.sobre === i) return;
  estado.sobre = i;
  principal.querySelectorAll(".slots > .slot").forEach((slot, indice) => slot.classList.toggle("over", indice === i && i < TOTAL_ECHOS));
}

function mover(de, para) {
  terminarArraste();
  if (de === para) return;
  const ordem = [...Array(TOTAL_ECHOS).keys()];
  const [item] = ordem.splice(de, 1);
  ordem.splice(para, 0, item); // ordem[j] = índice atual do espaço que vai para a posição j
  alterar((id) => api.captura.reordenar(id, ordem));
}

function terminarArraste() {
  const pendente = estado.redesenharDepoisDeArrastar;
  Object.assign(estado, { arrastando: null, sobre: null, redesenharDepoisDeArrastar: false });
  if (pendente) desenhar();
  else marcarSobre(null);
}

// ---------- Envio manual (sem os atalhos) ----------

function envioManual() {
  const entrada = el("input", { class: "sr", type: "file", accept: "image/png,image/jpeg,image/webp", multiple: true, onchange: (e) => enviarArquivos(e.target.files) });
  return el(
    "label",
    {
      class: "drop",
      ondragover: (e) => {
        if (estado.arrastando !== null) return;
        e.preventDefault();
        e.currentTarget.classList.add("over");
      },
      ondragleave: (e) => e.currentTarget.classList.remove("over"),
      ondrop: (e) => {
        if (estado.arrastando !== null) return;
        e.preventDefault();
        e.currentTarget.classList.remove("over");
        enviarArquivos(e.dataTransfer.files);
      },
    },
    entrada,
    icone(ICONES.enviar, 20),
    el("span", {}, "Sem os atalhos? Solte os prints aqui"),
    el("span", { style: { color: "#4A4060" }, "aria-hidden": "true" }, "·"),
    el("span", { style: { color: "var(--lilas)", fontWeight: 700, textDecoration: "underline", textUnderlineOffset: "3px" } }, "escolher arquivos"),
    el("span", { style: { flexBasis: "100%", textAlign: "center", fontSize: "12px" } }, "Ordem dos echos = ordem alfabética dos nomes (o 1º é o principal). Um arquivo 'personagem.png' é a tela do personagem."),
  );
}

function enviarArquivos(lista) {
  const arquivos = [...lista].sort((a, b) => a.name.localeCompare(b.name, "pt-BR", { numeric: true }));
  const personagem = arquivos.find((a) => a.name.toLowerCase().startsWith("personagem"));
  const echos = arquivos.filter((a) => a !== personagem);
  if (!estado.build) return falhar("Escolha a build antes de enviar os prints.");
  if (!echos.length || echos.length > TOTAL_ECHOS) return falhar(`Envie de 1 a ${TOTAL_ECHOS} prints de echo; recebi ${echos.length}.`);
  const form = new FormData();
  form.append("build", estado.build);
  echos.forEach((a) => form.append("echos", a));
  if (personagem) form.append("personagem", personagem);
  executar(async () => {
    const resposta = await api.extrair(form);
    if (!resposta.extracao.entrada) {
      const motivos = resposta.extracao.echos.map((r, i) => `Echo ${i + 1}: ${r.tipo === "ok" ? "lido" : r.motivo}`);
      throw new Error(`Nenhum echo foi lido.\n${motivos.join("\n")}`);
    }
    sessionStorage.setItem(CHAVE_UPLOAD, JSON.stringify(resposta.extracao));
    location.href = "analise.html?origem=upload";
  });
}

function falhar(mensagem) {
  estado.erro = mensagem;
  desenhar();
}

function rodape() {
  const echos = estado.sessao?.echos ?? [];
  const preenchidos = echos.filter((e) => e.estado !== "vazio").length;
  const personagemLido = estado.sessao?.personagem?.estado === "lido";
  const falta = estado.sessao ? motivoParaNaoAnalisar() : "inicie a captura ou envie os prints.";
  return el(
    "footer",
    { class: "foot" },
    el(
      "p",
      { style: { margin: 0, display: "flex", alignItems: "center", gap: "14px", fontSize: "16px", fontWeight: 700 } },
      el("span", {}, el("span", { class: "mono" }, `${preenchidos}/${TOTAL_ECHOS}`), " echos"),
      el("span", { style: { color: "#4A4060" }, "aria-hidden": "true" }, "·"),
      el("span", { class: personagemLido ? "c-ok" : "c-muted" }, `personagem ${personagemLido ? "✓" : "—"}`),
    ),
    el(
      "div",
      { style: { display: "flex", alignItems: "center", gap: "12px" } },
      falta ? el("span", { style: { fontSize: "13px", color: "var(--mudo)" } }, falta) : null,
      el(
        "a",
        {
          class: `btn primary${falta ? " desligado" : ""}`,
          href: estado.sessao ? `analise.html?sessao=${encodeURIComponent(estado.sessao.id)}` : "#",
          "aria-disabled": falta ? "true" : null,
        },
        "Ir para a análise ",
        el("span", { "aria-hidden": "true" }, "→"),
      ),
      el("span", { class: "kbd", "aria-label": `Atalho ${estado.teclas.analise}` }, estado.teclas.analise),
    ),
  );
}
