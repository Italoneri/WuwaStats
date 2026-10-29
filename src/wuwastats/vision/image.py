"""Carrega prints e, opcionalmente, recorta só o painel do echo antes de enviar à IA."""

import base64
import hashlib
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image

from wuwastats.config import Recorte

MIME_POR_EXTENSAO = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


class ImagemInvalida(ValueError):
    pass


@dataclass(frozen=True)
class Imagem:
    conteudo: bytes
    mime: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.conteudo).hexdigest()

    @property
    def data_url(self) -> str:
        return f"data:{self.mime};base64,{base64.b64encode(self.conteudo).decode('ascii')}"


def e_imagem(arquivo: Path) -> bool:
    return arquivo.suffix.lower() in MIME_POR_EXTENSAO


def carregar_imagem(arquivo: Path, recorte: Recorte | None = None) -> Imagem:
    mime = MIME_POR_EXTENSAO.get(arquivo.suffix.lower())
    if mime is None:
        raise ImagemInvalida(f"formato não suportado: {arquivo.suffix or 'sem extensão'}")
    imagem = Imagem(conteudo=arquivo.read_bytes(), mime=mime)
    return imagem if recorte is None else recortar(imagem, recorte)


def recortar(imagem: Imagem, recorte: Recorte) -> Imagem:
    x0, y0, x1, y1 = recorte
    try:
        with Image.open(BytesIO(imagem.conteudo)) as original:
            largura, altura = original.size
            caixa = (round(x0 * largura), round(y0 * altura), round(x1 * largura), round(y1 * altura))
            saida = BytesIO()
            original.crop(caixa).save(saida, format="PNG")
    except OSError as erro:
        raise ImagemInvalida(f"imagem ilegível: {erro}") from erro
    return Imagem(conteudo=saida.getvalue(), mime="image/png")
