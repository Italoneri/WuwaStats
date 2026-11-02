"""Imagens de personagens, echos, armas e sets enviadas pelo usuário: data/imagens/<categoria>/<chave>.png.

Toda imagem aceita é decodificada e regravada como PNG: o que fica no disco é sempre uma imagem válida, sem metadados.
"""

import os
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal

from PIL import Image, UnidentifiedImageError

CategoriaImagem = Literal["personagens", "echoes", "armas", "sets"]
PASTA_IMAGENS = "imagens"
MAX_BYTES_IMAGEM = 5 * 1024 * 1024
LADO_MAXIMO_PX = 1024
FORMATOS_ACEITOS = {"PNG", "JPEG", "WEBP"}
# Proteção contra "bomba de descompressão": um arquivo pequeno que vira uma imagem gigante na memória.
MAX_PIXELS_ORIGINAL = 40_000_000


class ImagemRecusada(ValueError):
    pass


class ImagemInexistente(LookupError):
    pass


@dataclass(frozen=True)
class ImagensDoCatalogo:
    data_dir: Path

    def caminho(self, categoria: CategoriaImagem, chave: str) -> Path:
        return self.data_dir / PASTA_IMAGENS / categoria / f"{nome_de_arquivo(chave)}.png"

    def existe(self, categoria: CategoriaImagem, chave: str) -> bool:
        return self.caminho(categoria, chave).is_file()

    def salvar(self, categoria: CategoriaImagem, chave: str, conteudo: bytes) -> None:
        png = normalizar_imagem(conteudo)
        destino = self.caminho(categoria, chave)
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporario = destino.with_suffix(".png.tmp")
        temporario.write_bytes(png)
        os.replace(temporario, destino)


def nome_de_arquivo(chave: str) -> str:
    """Chaves têm ':', '#', espaços... (ex.: 'Reminiscence: Suhsin the Inevitable'); o Windows não aceita ':'."""
    return re.sub(r"[^\w\-]+", "_", chave).strip("_") or "_"


@dataclass(frozen=True)
class FormatoDeSaida:
    lado_maximo_px: int
    max_bytes: int
    formato: Literal["PNG", "WEBP"]


# PNG mantém a transparência das fotos do catálogo; WebP deixa leve a fanart, que é grande e não precisa de alfa.
SAIDA_CATALOGO = FormatoDeSaida(LADO_MAXIMO_PX, MAX_BYTES_IMAGEM, "PNG")


def normalizar_imagem(conteudo: bytes, saida: FormatoDeSaida = SAIDA_CATALOGO) -> bytes:
    if len(conteudo) > saida.max_bytes:
        raise ImagemRecusada(f"imagem maior que {saida.max_bytes // (1024 * 1024)} MB")
    try:
        with Image.open(BytesIO(conteudo)) as imagem:
            if imagem.format not in FORMATOS_ACEITOS:
                raise ImagemRecusada(f"formato {imagem.format} não aceito; envie PNG, JPEG ou WebP")
            if imagem.width * imagem.height > MAX_PIXELS_ORIGINAL:
                raise ImagemRecusada(f"imagem com {imagem.width}x{imagem.height} pixels é grande demais")
            imagem.thumbnail((saida.lado_maximo_px, saida.lado_maximo_px))
            return _gravar(imagem, saida.formato)
    except (UnidentifiedImageError, OSError) as erro:
        raise ImagemRecusada("o arquivo não é uma imagem legível") from erro


def _gravar(imagem: Image.Image, formato: Literal["PNG", "WEBP"]) -> bytes:
    buffer = BytesIO()
    if formato == "PNG":
        imagem.convert("RGBA").save(buffer, format="PNG", optimize=True)
    else:
        imagem.convert("RGB").save(buffer, format="WEBP", quality=90, method=6)
    return buffer.getvalue()
