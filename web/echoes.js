// Echos: todos de GET /api/echoes com a imagem, para conferir à mão. Clicar abre o que o echo faz.

import { ICONES, api, avisoErro, carregarImagens, el, figura, icone, moldura, temImagem } from "./comum.js";

const TODOS = "todos";
const filtros = { custo: TODOS, semImagem: false, q: "" };
let echoes = [];
let contagem = null;
let grade = null;

const principal = moldura("echo");
carregar();

async function carregar() {
  try {
    const [lista] = await Promise.all([api.echoes(), carregarImagens()]);
    echoes = ordenar(lista);
    desenhar();
  } catch (erro) {
    principal.replaceChildren(el("div", { class: "wrap" }, avisoErro(erro)));
  }
}

/** Custo maior primeiro (sem custo no fim); depois o nome. */
function ordenar(lista) {
  return [...lista].sort((a, b) => (b.custo ?? 0) - (a.custo ?? 0) || a.nome.localeCompare(b.nome, "pt-BR"));
}

function visiveis() {
  const termo = filtros.q.trim().toLocaleLowerCase("pt-BR");
  return echoes.filter(
    (e) =>
      (filtros.custo === TODOS || String(e.custo) === filtros.custo) &&
      (!filtros.semImagem || !temImagem("echoes", e.chave)) &&
      (!termo || e.nome.toLocaleLowerCase("pt-BR").includes(termo) || e.chave.toLocaleLowerCase("pt-BR").includes(termo)),
  );
}

function desenhar() {
  contagem = el("p", {});
  grade = el("div", { class: "grid" });
  principal.replaceChildren(
    el(
      "div",
      { class: "wrap" },
      el("header", { class: "cabeca" }, el("h1", {}, "Echos"), contagem),
      busca(),
      el("div", { class: "fpanel" }, grupoCusto(), grupoImagem()),
      grade,
    ),
  );
  atualizarGrade();
}

/** Só a lista muda ao digitar: a busca não perde o foco. */
function atualizarGrade() {
  const lista = visiveis();
  const semImagem = echoes.filter((e) => !temImagem("echoes", e.chave)).length;
  const semHabilidade = echoes.filter((e) => !e.habilidade).length;
  contagem.textContent = `${lista.length} de ${echoes.length} echos · ${semImagem} sem imagem · ${semHabilidade} sem descrição`;
  grade.replaceChildren(...(lista.length ? lista.map(cartao) : [vazio()]));
}

function busca() {
  const campo = el("input", {
    type: "search",
    placeholder: "Buscar echo pelo nome…",
    value: filtros.q,
    oninput: (e) => {
      filtros.q = e.target.value;
      atualizarGrade();
    },
  });
  return el(
    "label",
    { class: "busca", style: { marginTop: "28px" } },
    icone(ICONES.busca, 20, { espessura: 2 }),
    el("span", { class: "sr" }, "Buscar echo"),
    campo,
  );
}

function grupoCusto() {
  const custos = [...new Set(echoes.map((e) => e.custo).filter((c) => c !== null))].sort((a, b) => b - a);
  const opcoes = [[TODOS, "Todos"], ...custos.map((c) => [String(c), `Custo ${c}`])];
  return el(
    "div",
    { class: "fgroup", role: "group", "aria-label": "Custo" },
    el("span", { class: "flabel" }, "Custo"),
    opcoes.map(([valor, rotulo]) => chip(rotulo, filtros.custo === valor, () => (filtros.custo = valor))),
  );
}

function grupoImagem() {
  return el(
    "div",
    { class: "fgroup", role: "group", "aria-label": "Imagem" },
    el("span", { class: "flabel" }, "Imagem"),
    chip("Todas", !filtros.semImagem, () => (filtros.semImagem = false)),
    chip("Só sem imagem", filtros.semImagem, () => (filtros.semImagem = true)),
  );
}

function chip(rotulo, ligado, escolher) {
  const aoClicar = () => {
    escolher();
    desenhar();
  };
  return el("button", { type: "button", class: `chip${ligado ? " on" : ""}`, "aria-pressed": String(ligado), onclick: aoClicar }, rotulo);
}

function vazio() {
  return el("div", { class: "vazio-msg" }, el("strong", {}, "Nenhum echo encontrado"), el("p", {}, "Tente outro nome ou outro filtro."));
}

const reserva = () => el("div", { class: "ph echo-ph" }, icone(ICONES.echo, 44));

function cartao(echo) {
  const tem = temImagem("echoes", echo.chave);
  return el(
    "button",
    { type: "button", class: "card echo-card", "aria-haspopup": "dialog", "aria-label": `${echo.nome}, custo ${echo.custo ?? "desconhecido"}`, onclick: () => abrir(echo) },
    el(
      "div",
      { class: "echo-arte" },
      figura("echoes", echo.chave, reserva(), { rotulo: echo.nome }),
      el("span", { class: "cost sm echo-custo", title: "Custo" }, echo.custo ?? "?"),
    ),
    el(
      "div",
      { class: "cbody" },
      el("span", { class: "cname" }, echo.nome),
      echo.nome === echo.chave ? null : el("span", { class: "cnota" }, echo.chave),
      tem ? null : el("span", { class: "cnota warn" }, "Sem imagem"),
    ),
  );
}

/** Janela com o que o echo faz. A imagem pode ser trocada daqui; a grade se atualiza ao fechar. */
function abrir(echo) {
  const fechar = () => dialogo.close();
  const dialogo = el(
    "dialog",
    {
      class: "echo-dialogo",
      "aria-labelledby": "echo-titulo",
      onclose: () => {
        dialogo.remove();
        atualizarGrade();
      },
      onclick: (e) => e.target === dialogo && fechar(),
    },
    el(
      "div",
      { class: "echo-detalhe" },
      el("button", { class: "ibtn lightbox-fechar", type: "button", "aria-label": "Fechar", onclick: fechar }, icone(ICONES.fechar, 20, { espessura: 2 })),
      el("div", { class: "echo-arte grande" }, figura("echoes", echo.chave, reserva(), { trocavel: true, rotulo: echo.nome })),
      detalhes(echo),
    ),
  );
  document.body.append(dialogo);
  dialogo.showModal();
}

function detalhes(echo) {
  return el(
    "div",
    { class: "echo-info" },
    el("h2", { id: "echo-titulo" }, echo.nome),
    echo.nome === echo.chave ? null : el("p", { class: "c-muted" }, echo.chave),
    el(
      "div",
      { class: "echo-tags" },
      el("span", { class: "chip" }, `Custo ${echo.custo ?? "?"}`),
      echo.sets.map((s) => el("span", { class: "chip" }, icone(ICONES.sonata, 16), s.nome)),
    ),
    el("span", { class: "label" }, "Habilidade"),
    echo.habilidade
      ? el("p", { class: "echo-habilidade" }, echo.habilidade)
      : el("p", { class: "c-muted" }, "Os dados do jogo não trazem a descrição deste echo."),
    echo.habilidade ? el("p", { class: "dica" }, "Valores no nível mais alto da habilidade.") : null,
  );
}
