"""API HTTP. Contrato documentado em docs/api.md; OpenAPI interativo em /docs."""

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from wuwastats.api.contracts import (
    BuildResumo,
    Catalogo,
    Erro,
    PedidoAlias,
    RespostaExtracao,
    montar_catalogo,
    resumir_build,
)
from wuwastats.api.repositorio import RepositorioDados
from wuwastats.config import PROJECT_ROOT, Settings
from wuwastats.domain.analyze import analisar
from wuwastats.domain.models import MAX_ECHOS, Condicoes, EntradaBuild
from wuwastats.domain.report import Analise
from wuwastats.domain.tables import GameData, Perfil
from wuwastats.gamedata.aliases import AliasInvalido
from wuwastats.gamedata.loader import GameDataError
from wuwastats.vision.cache import CacheVisao
from wuwastats.vision.client import ConfiguracaoAusente, ModeloVisao, criar_modelo_nvidia
from wuwastats.vision.extract import Extrator, PedidoExtracao, extrair_build

WEB_DIR = PROJECT_ROOT / "web"
MAX_BYTES_POR_PRINT = 15 * 1024 * 1024
RESPOSTA_ARMA = {"sim": True, "nao": False}

FabricaModelo = Callable[[Settings], ModeloVisao]
ERROS: dict[int | str, dict[str, object]] = {
    404: {"model": Erro, "description": "Build não encontrada"},
    422: {"model": Erro, "description": "Entrada inválida"},
}


class ErroApi(Exception):
    def __init__(self, status: int, mensagem: str, erros: list[str] | None = None) -> None:
        super().__init__(mensagem)
        self.status = status
        self.corpo = Erro(mensagem=mensagem, erros=erros or [])


def _dados_atuais(request: Request) -> GameData:
    repositorio: RepositorioDados = request.app.state.repositorio
    return repositorio.dados


Dados = Annotated[GameData, Depends(_dados_atuais)]


def criar_app(settings: Settings | None = None, fabrica_modelo: FabricaModelo = criar_modelo_nvidia) -> FastAPI:
    configuracao = settings or Settings()
    repositorio = RepositorioDados(configuracao.data_dir)
    app = FastAPI(title="WuwaStats", version="0.1.0", description="Analisador de echos de Wuthering Waves")
    app.state.repositorio = repositorio

    @app.exception_handler(ErroApi)
    def _erro_api(_request: Request, erro: ErroApi) -> JSONResponse:
        return JSONResponse(status_code=erro.status, content=erro.corpo.model_dump())

    @app.exception_handler(RequestValidationError)
    def _erro_validacao(_request: Request, erro: RequestValidationError) -> JSONResponse:
        detalhes = [f"{' › '.join(str(p) for p in e['loc'])}: {e['msg']}" for e in erro.errors()]
        return JSONResponse(status_code=422, content=Erro(mensagem="requisição inválida", erros=detalhes).model_dump())

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/builds")
    def builds(dados: Dados) -> list[BuildResumo]:
        return [resumir_build(chave, perfil) for chave, perfil in sorted(dados.perfis.items())]

    @app.get("/api/catalogo")
    def catalogo(dados: Dados) -> Catalogo:
        return montar_catalogo(dados)

    @app.post("/api/analisar", responses=ERROS)
    def analisar_entrada(entrada: EntradaBuild, dados: Dados) -> Analise:
        return analisar(entrada, _perfil(dados, entrada.build), dados)

    @app.post("/api/extrair", responses={**ERROS, 503: {"model": Erro, "description": "IA de visão não configurada"}})
    def extrair(
        dados: Dados,
        build: Annotated[str, Form()],
        echos: Annotated[list[UploadFile], File(description=f"1 a {MAX_ECHOS} prints, na ordem dos slots")],
        personagem: Annotated[UploadFile | None, File(description="print da tela do personagem")] = None,
        arma_assinatura: Annotated[Literal["sim", "nao"] | None, Form()] = None,
        regen_externa: Annotated[float, Form()] = 0.0,
    ) -> RespostaExtracao:
        perfil = _perfil(dados, build)
        if not 1 <= len(echos) <= MAX_ECHOS:
            raise ErroApi(422, f"envie de 1 a {MAX_ECHOS} prints de echo; recebi {len(echos)}")
        try:
            modelo = fabrica_modelo(configuracao)
        except ConfiguracaoAusente as erro:
            raise ErroApi(503, str(erro)) from erro
        extrator = Extrator(
            modelo=modelo,
            cache=CacheVisao(configuracao.cache_dir),
            dados=dados,
            recorte_echo=configuracao.echo_recorte,
        )
        with tempfile.TemporaryDirectory(prefix="wuwastats-") as pasta:
            pedido = PedidoExtracao(
                build=build,
                prints_echo=tuple(_salvar(upload, Path(pasta), f"{i + 1}") for i, upload in enumerate(echos)),
                print_personagem=_salvar(personagem, Path(pasta), "personagem") if personagem else None,
                condicoes=Condicoes(arma_assinatura=RESPOSTA_ARMA.get(arma_assinatura or "")),
                regen_externa=regen_externa,
            )
            extracao = extrair_build(extrator, pedido, perfil, configuracao.nvidia_concorrencia)
        analise = analisar(extracao.entrada, perfil, dados) if extracao.entrada else None
        return RespostaExtracao(extracao=extracao, analise=analise)

    @app.post("/api/aliases", status_code=204, responses={422: {"model": Erro, "description": "Alias inválido"}})
    def mapear_nome(pedido: PedidoAlias) -> None:
        try:
            repositorio.registrar_alias(pedido.categoria, pedido.chave, pedido.alias)
        except AliasInvalido as erro:
            raise ErroApi(422, str(erro)) from erro

    @app.post("/api/dados/recarregar", status_code=204, responses={422: {"model": Erro, "description": "JSON inválido"}})
    def recarregar() -> None:
        try:
            repositorio.recarregar()
        except GameDataError as erro:
            raise ErroApi(422, "dados de jogo inválidos; mantidos os anteriores", erro.erros) from erro

    if WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


def _perfil(dados: GameData, build: str) -> Perfil:
    perfil = dados.perfis.get(build)
    if perfil is None:
        raise ErroApi(404, f"build '{build}' não existe em characters.json", sorted(dados.perfis))
    return perfil


def _salvar(upload: UploadFile, pasta: Path, prefixo: str) -> Path:
    """Nome no disco = prefixo + extensão original: preserva a ordem e evita caminhos vindos do cliente."""
    conteudo = upload.file.read(MAX_BYTES_POR_PRINT + 1)
    if len(conteudo) > MAX_BYTES_POR_PRINT:
        raise ErroApi(422, f"{upload.filename}: arquivo maior que {MAX_BYTES_POR_PRINT // (1024 * 1024)} MB")
    destino = pasta / f"{prefixo}{Path(upload.filename or '').suffix.lower()}"
    destino.write_bytes(conteudo)
    return destino
