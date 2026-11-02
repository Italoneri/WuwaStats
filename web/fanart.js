// Banner do cabeçalho do personagem: a fanart com o crédito do artista ou, sem ela, a foto padrão da galeria.

import { ICONES, api, el, elemento, figura, icone, silhueta } from "./comum.js";

const urlFanart = (chave, versao) => `/api/fanarts/${encodeURIComponent(chave)}?v=${versao}`;

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
    banner.replaceChildren(arte(personagem, credito, versao), info, rodape(personagem, credito, aoSalvar));
  };
  desenhar(creditoInicial);
  return banner;
}

function arte(personagem, credito, versao) {
  if (credito) {
    const alt = `Fanart de ${personagem.nome} por ${credito.artista}`;
    return el("div", { class: "cab-arte" }, el("img", { class: "cab-fanart", src: urlFanart(personagem.chave, versao), alt }));
  }
  const reserva = silhueta(elemento(personagem.elemento.chave).cor, "", "78%");
  return el("div", { class: "cab-arte" }, el("div", { class: "cab-foto" }, figura("personagens", personagem.chave, reserva, { rotulo: personagem.nome })));
}

function rodape(personagem, credito, aoSalvar) {
  const editar = el(
    "button",
    { type: "button", class: "cab-editar-arte", onclick: () => abrirEditor(personagem, credito, aoSalvar) },
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

function abrirEditor(personagem, credito, aoSalvar) {
  const arquivo = el("input", { class: "campo", type: "file", accept: "image/png,image/jpeg,image/webp", required: credito === null });
  const artista = el("input", { class: "campo", type: "text", required: true, maxlength: 80, value: credito?.artista ?? "", placeholder: "@artista" });
  const link = el("input", { class: "campo", type: "url", maxlength: 500, value: credito?.link ?? "", placeholder: "https://www.pixiv.net/artworks/…" });
  const erro = el("p", { class: "fanart-erro", role: "alert", hidden: true });
  const salvar = el("button", { type: "submit", class: "btn primary" }, "Salvar");
  const fechar = () => dialogo.close();

  const enviar = async (e) => {
    e.preventDefault();
    salvar.disabled = true;
    erro.hidden = true;
    try {
      await api.enviarFanart(personagem.chave, { arquivo: arquivo.files[0], artista: artista.value, link: link.value });
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
    campo("Artista", artista),
    campo("Link da postagem original", link, "Pixiv, X, Bluesky… Opcional, mas ajuda a dar o crédito certo."),
    erro,
    el("div", { class: "fanart-acoes" }, el("button", { type: "button", class: "btn", onclick: fechar }, "Cancelar"), salvar),
  );
  const dialogo = el(
    "dialog",
    { class: "fanart-dialogo", "aria-labelledby": "fanart-titulo", onclose: () => dialogo.remove(), onclick: (e) => e.target === dialogo && fechar() },
    form,
  );
  document.body.append(dialogo);
  dialogo.showModal();
}

const campo = (rotulo, entrada, dica = null) =>
  el("label", { class: "fanart-campo" }, el("span", { class: "label" }, rotulo), entrada, dica ? el("small", {}, dica) : null);
