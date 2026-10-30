"""Rotas das imagens do catálogo (personagens, echos, armas). Erros viram HTTP pelos handlers de app.py."""

from collections.abc import Callable, Mapping
from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse

from wuwastats.domain.tables import GameData
from wuwastats.gamedata.imagens import MAX_BYTES_IMAGEM, CategoriaImagem, ImagemInexistente, ImagensDoCatalogo

CATEGORIAS: tuple[CategoriaImagem, ...] = ("personagens", "echoes", "armas")


def rotas_imagens(imagens: ImagensDoCatalogo, dados_atuais: Callable[[], GameData]) -> APIRouter:
    rotas = APIRouter(prefix="/api/imagens", tags=["imagens"])

    def chaves(categoria: CategoriaImagem) -> Mapping[str, object]:
        dados = dados_atuais()
        por_categoria: dict[CategoriaImagem, Mapping[str, object]] = {
            "personagens": dados.ressonadores,
            "echoes": dados.echoes,
            "armas": dados.armas,
        }
        return por_categoria[categoria]

    def exigir_chave(categoria: CategoriaImagem, chave: str) -> None:
        if chave not in chaves(categoria):
            raise ImagemInexistente(f"'{chave}' não existe em {categoria}")

    @rotas.get("")
    def listar() -> dict[CategoriaImagem, list[str]]:
        """Chaves que têm imagem; as outras a página desenha com placeholder."""
        return {c: sorted(chave for chave in chaves(c) if imagens.existe(c, chave)) for c in CATEGORIAS}

    @rotas.get("/{categoria}/{chave}", response_class=FileResponse)
    def baixar(categoria: CategoriaImagem, chave: str) -> FileResponse:
        exigir_chave(categoria, chave)
        if not imagens.existe(categoria, chave):
            raise ImagemInexistente(f"'{chave}' não tem imagem")
        # no-cache = revalida pelo ETag: depois de trocar a imagem o navegador não mostra a antiga
        return FileResponse(imagens.caminho(categoria, chave), media_type="image/png", headers={"Cache-Control": "no-cache"})

    @rotas.put("/{categoria}/{chave}", status_code=204)
    def enviar(
        categoria: CategoriaImagem,
        chave: str,
        arquivo: Annotated[UploadFile, File(description=f"PNG, JPEG ou WebP até {MAX_BYTES_IMAGEM // (1024 * 1024)} MB")],
    ) -> None:
        exigir_chave(categoria, chave)
        imagens.salvar(categoria, chave, arquivo.file.read(MAX_BYTES_IMAGEM + 1))

    return rotas
