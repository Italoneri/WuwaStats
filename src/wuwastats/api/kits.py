"""Rotas do kit dos personagens (aba Kit da tela do personagem). Erros viram HTTP pelos handlers de app.py."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

from wuwastats.gamedata.imagens import ImagemInexistente
from wuwastats.gamedata.kits import ImagensDoKit, Kit, KitInexistente, ler_kit


class KitResposta(BaseModel):
    kit: Kit
    resumo: str | None


def rotas_kits(data_dir: Path) -> APIRouter:
    rotas = APIRouter(prefix="/api/kits", tags=["kits"])
    imagens = ImagensDoKit(data_dir)

    @rotas.get("/{chave}")
    def kit(chave: str) -> KitResposta:
        encontrado = ler_kit(data_dir, chave)
        if encontrado is None:
            raise KitInexistente(f"'{chave}' não tem kit importado")
        kit, resumo = encontrado
        return KitResposta(kit=kit, resumo=resumo)

    @rotas.get("/{chave}/imagens/{nome}", response_class=FileResponse)
    def imagem(chave: str, nome: str) -> FileResponse:
        if not imagens.existe(chave, nome):
            raise ImagemInexistente(f"'{chave}' não tem a imagem '{nome}' no kit")
        return FileResponse(imagens.caminho(chave, nome), media_type="image/png", headers={"Cache-Control": "no-cache"})

    return rotas
