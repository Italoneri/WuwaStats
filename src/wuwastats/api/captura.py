"""Rotas da captura no servidor. Erros de domínio viram HTTP pelos handlers registrados em app.py."""

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Annotated

from fastapi import APIRouter
from fastapi import Path as Caminho
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from wuwastats.captura.servico import Evento, Local, ServicoCaptura
from wuwastats.captura.sessao import Sessao
from wuwastats.captura.teclas import Acao
from wuwastats.domain.models import MAX_ECHOS, EntradaBuild
from wuwastats.domain.tables import Perfil

PING_S = 15
IndiceEcho = Annotated[int, Caminho(ge=0, lt=MAX_ECHOS, description="Posição do espaço de echo (0 = echo principal)")]
Espaco = Annotated[str, Caminho(pattern=rf"^([0-{MAX_ECHOS - 1}]|personagem)$", description="0 a 4 ou 'personagem'")]


class PedidoCaptura(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    build: str = Field(min_length=1)


class PedidoOrdem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ordem: list[int] = Field(
        min_length=MAX_ECHOS, max_length=MAX_ECHOS, description="ordem[j] = índice atual do espaço que vai para a posição j"
    )


def rotas_captura(servico: ServicoCaptura, perfil_da_build: Callable[[str], Perfil], teclas: dict[Acao, str]) -> APIRouter:
    rotas = APIRouter(prefix="/api/captura", tags=["captura"])

    @rotas.get("/teclas")
    def atalhos() -> dict[Acao, str]:
        """Atalhos configurados no .env, para a página mostrar as teclas certas."""
        return teclas

    @rotas.post("/iniciar")
    def iniciar(pedido: PedidoCaptura) -> Sessao:
        perfil_da_build(pedido.build)
        return servico.iniciar(pedido.build)

    @rotas.post("/parar", status_code=204)
    def parar() -> None:
        servico.parar()

    @rotas.get("/{sessao}")
    def estado(sessao: str) -> Sessao:
        return servico.estado(sessao)

    @rotas.get("/{sessao}/eventos", response_class=StreamingResponse)
    async def eventos(sessao: str) -> StreamingResponse:
        loop = asyncio.get_running_loop()
        fila: asyncio.Queue[Evento] = asyncio.Queue()

        def enfileirar(evento: Evento) -> None:
            if not loop.is_closed():
                loop.call_soon_threadsafe(fila.put_nowait, evento)

        cancelar = servico.inscrever(sessao, enfileirar)
        cabecalhos = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        return StreamingResponse(_sse(fila, cancelar), media_type="text/event-stream", headers=cabecalhos)

    @rotas.post("/{sessao}/reordenar")
    def reordenar(sessao: str, pedido: PedidoOrdem) -> Sessao:
        return servico.reordenar(sessao, pedido.ordem)

    @rotas.delete("/{sessao}/echos/{indice}")
    def esvaziar_echo(sessao: str, indice: IndiceEcho) -> Sessao:
        return servico.esvaziar_echo(sessao, indice)

    @rotas.delete("/{sessao}/personagem")
    def esvaziar_personagem(sessao: str) -> Sessao:
        return servico.esvaziar_personagem(sessao)

    @rotas.post("/{sessao}/echos/{indice}/refazer")
    def refazer(sessao: str, indice: IndiceEcho) -> Sessao:
        return servico.refazer(sessao, indice)

    @rotas.get("/{sessao}/imagens/{espaco}", response_class=FileResponse)
    def imagem(sessao: str, espaco: Espaco) -> FileResponse:
        """O mesmo espaço muda de print: a página põe ?captura=N na URL para o cache do navegador não confundir."""
        local: Local = "personagem" if espaco == "personagem" else int(espaco)
        cabecalhos = {"Cache-Control": "private, max-age=3600"}
        return FileResponse(servico.imagem(sessao, local), media_type="image/png", headers=cabecalhos)

    @rotas.get("/{sessao}/entrada")
    def entrada(sessao: str) -> EntradaBuild:
        return servico.entrada(sessao, perfil_da_build)

    return rotas


async def _sse(fila: asyncio.Queue[Evento], cancelar: Callable[[], None]) -> AsyncIterator[str]:
    """Um evento por mensagem; comentário de ping mantém a conexão e detecta a página fechada."""
    try:
        while True:
            try:
                evento = await asyncio.wait_for(fila.get(), timeout=PING_S)
            except TimeoutError:
                yield ": ping\n\n"
                continue
            yield f"event: {evento.tipo}\ndata: {evento.model_dump_json()}\n\n"
            if evento.tipo == "encerrada":
                return
    finally:
        cancelar()
