"""Rotas das fanarts da tela do personagem. Erros viram HTTP pelos handlers de app.py."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse

from wuwastats.domain.tables import GameData
from wuwastats.gamedata.fanarts import MAX_BYTES_FANART, Credito, FanartsDoCatalogo, validar_credito
from wuwastats.gamedata.imagens import ImagemInexistente


def rotas_fanarts(fanarts: FanartsDoCatalogo, dados_atuais: Callable[[], GameData]) -> APIRouter:
    rotas = APIRouter(prefix="/api/fanarts", tags=["fanarts"])

    def exigir_personagem(chave: str) -> None:
        if chave not in dados_atuais().ressonadores:
            raise ImagemInexistente(f"'{chave}' não é um personagem")

    @rotas.get("")
    def listar() -> dict[str, Credito]:
        """Crédito de cada personagem que tem fanart; os outros usam a foto padrão."""
        creditos = {chave: fanarts.credito(chave) for chave in sorted(dados_atuais().ressonadores)}
        return {chave: credito for chave, credito in creditos.items() if credito is not None}

    @rotas.get("/{chave}", response_class=FileResponse)
    def baixar(chave: str) -> FileResponse:
        exigir_personagem(chave)
        if not fanarts.existe(chave):
            raise ImagemInexistente(f"'{chave}' não tem fanart")
        return FileResponse(fanarts.caminho(chave), media_type="image/webp", headers={"Cache-Control": "no-cache"})

    @rotas.put("/{chave}", status_code=204)
    def enviar(
        chave: str,
        artista: Annotated[str, Form(description="Nome ou @ do artista")],
        link: Annotated[str | None, Form(description="Postagem original (http/https)")] = None,
        arquivo: Annotated[
            UploadFile | None, File(description=f"PNG, JPEG ou WebP até {MAX_BYTES_FANART // (1024 * 1024)} MB; sem ele, troca só o crédito")
        ] = None,
        posicao_x: Annotated[float, Form(description="Ponto focal horizontal no banner, 0–100%")] = 50,
        posicao_y: Annotated[float, Form(description="Ponto focal vertical no banner, 0–100%")] = 25,
        zoom: Annotated[float, Form(description="Zoom a partir do preenchimento do banner, 1–3")] = 1,
    ) -> None:
        exigir_personagem(chave)
        credito = validar_credito(artista, link, {"x": posicao_x, "y": posicao_y, "zoom": zoom})
        conteudo = arquivo.file.read(MAX_BYTES_FANART + 1) if arquivo is not None else None
        fanarts.salvar(chave, conteudo, credito)

    return rotas
