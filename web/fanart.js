// Banner do cabeçalho do personagem: a fanart com o crédito do artista ou, sem ela, a foto padrão da galeria.

import { ICONES, api, el, elemento, figura, icone, silhueta } from "./comum.js";

const urlFanart = (chave, versao) => `/api/fanarts/${encodeURIComponent(chave)}?v=${versao}`;
const ENQUADRAMENTO_PADRAO = Object.freeze({ x: 50, y: 25, zoom: 1 });
const PROPORCAO_RESERVA = 3;

/** `info` é o bloco com nome e chips; o banner redesenha só a arte e o crédito quando a fanart muda. */
export function bannerDoPersonagem(personagem, info, creditoInicial) {
  const banner = el("header", { class: "cab-personagem" });
  banner.style.setProperty("--cor-elemento", elemento(personagem.elemento.chave).cor);
  let versao = 0; // muda a URL depois de trocar a imagem, senão o navegador mostra a antiga
  const desenhar = (credito) => {
    banner.classList.toggle("com-fanart", credito !== null);
    const aoSalvar = (novo) => {
      versao = Date.now();
      desenhar(novo);
    };
    // A prévia do editor copia o formato atual do banner para o recorte sair igual ao da página.
    const proporcao = () => (banner.clientHeight > 0 ? banner.clientWidth / banner.clientHeight : PROPORCAO_RESERVA);
    const abrir = () => abrirEditor({ personagem, credito, aoSalvar, proporcao: proporcao() });
    banner.replaceChildren(arte(personagem, credito, versao), info, rodape(credito, abrir));
  };
  desenhar(creditoInicial);
  return banner;
}

function arte(personagem, credito, versao) {
  if (credito) {
    const alt = `Fanart de ${personagem.nome} por ${credito.artista}`;
    const imagem = el("img", { class: "cab-fanart", src: urlFanart(personagem.chave, versao), alt });
    aplicarEnquadramento(imagem, credito.enquadramento ?? ENQUADRAMENTO_PADRAO);
    return el("div", { class: "cab-arte" }, imagem);
  }
  const reserva = silhueta(elemento(personagem.elemento.chave).cor, "", "78%");
  return el("div", { class: "cab-arte" }, el("div", { class: "cab-foto" }, figura("personagens", personagem.chave, reserva, { rotulo: personagem.nome })));
}

/** O zoom parte do mesmo ponto focal do recorte, então ampliar não tira do quadro o que foi enquadrado. */
function aplicarEnquadramento(imagem, { x, y, zoom }) {
  const ponto = `${x}% ${y}%`;
  imagem.style.objectPosition = ponto;
  imagem.style.transformOrigin = ponto;
  imagem.style.transform = `scale(${zoom})`;
}

function rodape(credito, abrir) {
  const editar = el(
    "button",
    { type: "button", class: "cab-editar-arte", onclick: abrir },
    icone(ICONES.imagem, 15, { espessura: 2 }),
    credito ? "Trocar fanart" : "Adicionar fanart",
  );
  return el("div", { class: "cab-arte-rodape" }, credito ? linhaDeCredito(credito) : null, editar);
}

function linhaDeCredito({ artista, link }) {
  const nome = link
    ? el("a", { href: link, target: "_blank", rel: "noopener noreferrer" }, artista, icone(ICONES.externo, 12, { espessura: 2 }))
    : el("strong", {}, artista);
  return el("p", { class: "cab-credito" }, "Arte: ", nome);
}

function abrirEditor({ personagem, credito, aoSalvar, proporcao }) {
  const arquivo = el("input", { class: "campo", type: "file", accept: "image/png,image/jpeg,image/webp", required: credito === null });
  const artista = el("input", { class: "campo", type: "text", required: true, maxlength: 80, value: credito?.artista ?? "", placeholder: "@artista" });
  const link = el("input", { class: "campo", type: "url", maxlength: 500, value: credito?.link ?? "", placeholder: "https://www.pixiv.net/artworks/…" });
  const imagemAtual = credito ? urlFanart(personagem.chave, Date.now()) : null;
  const previa = editorDeEnquadramento(proporcao, imagemAtual, credito?.enquadramento ?? ENQUADRAMENTO_PADRAO);
  const erro = el("p", { class: "fanart-erro", role: "alert", hidden: true });
  const salvar = el("button", { type: "submit", class: "btn primary" }, "Salvar");
  const fechar = () => dialogo.close();

  arquivo.addEventListener("change", () => previa.trocarImagem(arquivo.files[0] ?? null, imagemAtual));

  const enviar = async (e) => {
    e.preventDefault();
    salvar.disabled = true;
    erro.hidden = true;
    try {
      const dados = { arquivo: arquivo.files[0], artista: artista.value, link: link.value, enquadramento: previa.enquadramento() };
      await api.enviarFanart(personagem.chave, dados);
      const creditos = await api.fanarts();
      fechar();
      aoSalvar(creditos[personagem.chave] ?? null);
    } catch (falha) {
      erro.textContent = falha.message;
      erro.hidden = false;
      salvar.disabled = false;
    }
  };

  const form = el(
    "form",
    { class: "fanart-form", onsubmit: enviar },
    el("h2", { id: "fanart-titulo" }, credito ? `Trocar fanart de ${personagem.nome}` : `Adicionar fanart de ${personagem.nome}`),
    campo(credito ? "Imagem (deixe vazio para manter a atual)" : "Imagem", arquivo, "PNG, JPEG ou WebP até 15 MB."),
    previa.elemento,
    campo("Artista", artista),
    campo("Link da postagem original", link, "Pixiv, X, Bluesky… Opcional, mas ajuda a dar o crédito certo."),
    erro,
    el(
      "div",
      { class: "fanart-acoes" },
      el(
        "a",
        { class: "fanart-busca", href: buscaNoPixiv(personagem.nome), target: "_blank", rel: "noopener noreferrer" },
        "Buscar fanarts horizontais no Pixiv",
        icone(ICONES.externo, 12, { espessura: 2 }),
      ),
      el("button", { type: "button", class: "btn", onclick: fechar }, "Cancelar"),
      salvar,
    ),
  );
  const dialogo = el(
    "dialog",
    {
      class: "fanart-dialogo",
      "aria-labelledby": "fanart-titulo",
      onclose: () => {
        previa.descartar();
        dialogo.remove();
      },
      onclick: (e) => e.target === dialogo && fechar(),
    },
    form,
  );
  document.body.append(dialogo);
  dialogo.showModal();
}

/** Busca por tag no Pixiv só com ilustrações horizontais (ratio=0.5) e para todas as idades (mode=safe). */
function buscaNoPixiv(nome) {
  const termos = `鳴潮 ${nome.replaceAll(":", " ")}`.replace(/\s+/g, " ").trim();
  const filtros = new URLSearchParams({ q: termos, s_mode: "tag", type: "illust_ugoira", mode: "safe", ratio: "0.5" });
  return `https://www.pixiv.net/search?${filtros}`;
}

/** Prévia no formato do banner: arrastar move o recorte, o controle deslizante amplia. */
function editorDeEnquadramento(proporcao, imagemInicial, inicial) {
  const estado = { ...inicial };
  const imagem = el("img", { class: "cab-fanart", alt: "", draggable: "false" });
  const quadro = el(
    "div",
    { class: "fanart-previa com-fanart", tabindex: 0, role: "group", "aria-label": "Prévia do banner. Arraste ou use as setas para mover a imagem." },
    el("div", { class: "cab-arte" }, imagem),
    el("p", { class: "fanart-previa-vazia" }, "Escolha uma imagem para ajustar o enquadramento."),
  );
  quadro.style.aspectRatio = String(proporcao);
  const zoom = el("input", { type: "range", min: 1, max: 3, step: 0.01, "aria-label": "Zoom" });
  const valorDoZoom = el("output", { class: "fanart-zoom-valor" });
  const desenhar = () => {
    aplicarEnquadramento(imagem, estado);
    zoom.value = String(estado.zoom);
    valorDoZoom.textContent = `${Math.round(estado.zoom * 100)}%`;
  };
  const redefinir = () => {
    Object.assign(estado, ENQUADRAMENTO_PADRAO);
    desenhar();
  };
  zoom.addEventListener("input", () => {
    estado.zoom = Number(zoom.value);
    desenhar();
  });
  arrastarParaEnquadrar(quadro, imagem, estado, desenhar);
  quadro.addEventListener("keydown", (e) => moverComTeclado(e, estado, desenhar));

  let urlTemporaria = null;
  const mostrar = (src) => {
    quadro.classList.toggle("sem-imagem", src === null);
    if (src !== null) imagem.src = src;
  };
  imagem.addEventListener("error", () => quadro.classList.add("sem-imagem"));
  mostrar(imagemInicial);
  desenhar();

  const controles = el(
    "div",
    { class: "fanart-controles" },
    el("span", { class: "label" }, "Zoom"),
    zoom,
    valorDoZoom,
    el("button", { type: "button", class: "btn", onclick: redefinir }, "Centralizar"),
  );
  return {
    elemento: el("div", { class: "fanart-enquadramento" }, el("span", { class: "label" }, "Enquadramento no banner"), quadro, controles),
    enquadramento: () => ({ ...estado }),
    trocarImagem: (arquivoNovo, imagemAtual) => {
      if (urlTemporaria) URL.revokeObjectURL(urlTemporaria);
      urlTemporaria = arquivoNovo ? URL.createObjectURL(arquivoNovo) : null;
      mostrar(urlTemporaria ?? imagemAtual);
      redefinir();
    },
    descartar: () => urlTemporaria && URL.revokeObjectURL(urlTemporaria),
  };
}

const limitar = (valor, minimo, maximo) => Math.min(maximo, Math.max(minimo, Math.round(valor * 10) / 10));

/** Quanto da imagem (em px de tela) sobra para fora do quadro em cada eixo, já com o zoom. */
function sobraForaDoQuadro(quadro, imagem, zoom) {
  const escala = Math.max(quadro.clientWidth / imagem.naturalWidth, quadro.clientHeight / imagem.naturalHeight);
  return {
    x: imagem.naturalWidth * escala * zoom - quadro.clientWidth,
    y: imagem.naturalHeight * escala * zoom - quadro.clientHeight,
  };
}

// Arrastar a imagem para a direita mostra mais do lado esquerdo: o ponto focal anda no sentido oposto ao do ponteiro.
const deslocar = (inicio, deltaPx, sobraPx) => (sobraPx > 0.5 ? limitar(inicio - (deltaPx / sobraPx) * 100, 0, 100) : inicio);

function arrastarParaEnquadrar(quadro, imagem, estado, aoMudar) {
  let inicio = null;
  quadro.addEventListener("pointerdown", (e) => {
    if (!imagem.naturalWidth) return;
    inicio = { px: e.clientX, py: e.clientY, x: estado.x, y: estado.y };
    quadro.setPointerCapture(e.pointerId);
    quadro.classList.add("arrastando");
  });
  quadro.addEventListener("pointermove", (e) => {
    if (!inicio) return;
    const sobra = sobraForaDoQuadro(quadro, imagem, estado.zoom);
    estado.x = deslocar(inicio.x, e.clientX - inicio.px, sobra.x);
    estado.y = deslocar(inicio.y, e.clientY - inicio.py, sobra.y);
    aoMudar();
  });
  const soltar = () => {
    inicio = null;
    quadro.classList.remove("arrastando");
  };
  quadro.addEventListener("pointerup", soltar);
  quadro.addEventListener("pointercancel", soltar);
}

const PASSOS_DO_TECLADO = {
  ArrowLeft: { x: 1, y: 0 },
  ArrowRight: { x: -1, y: 0 },
  ArrowUp: { x: 0, y: 1 },
  ArrowDown: { x: 0, y: -1 },
};

function moverComTeclado(e, estado, aoMudar) {
  const passo = PASSOS_DO_TECLADO[e.key];
  if (!passo) return;
  e.preventDefault();
  const tamanho = e.shiftKey ? 10 : 2;
  estado.x = limitar(estado.x + passo.x * tamanho, 0, 100);
  estado.y = limitar(estado.y + passo.y * tamanho, 0, 100);
  aoMudar();
}

const campo = (rotulo, entrada, dica = null) =>
  el("label", { class: "fanart-campo" }, el("span", { class: "label" }, rotulo), entrada, dica ? el("small", {}, dica) : null);
