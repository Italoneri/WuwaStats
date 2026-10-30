"""Prints -> echos lidos. Toda falha (imagem, API, resposta) vira ExtracaoFalhou, nunca exceção."""

import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from openai import OpenAIError
from pydantic import BaseModel, ConfigDict, Field

from wuwastats.config import Recorte
from wuwastats.domain.models import MAX_ECHOS, Condicoes, EchoEntrada, EntradaBuild
from wuwastats.domain.tables import GameData, Perfil
from wuwastats.domain.variants import detectar_condicoes
from wuwastats.vision.cache import CacheVisao, ChaveCache, TipoPrint
from wuwastats.vision.client import ModeloVisao
from wuwastats.vision.image import ImagemInvalida, carregar_imagem, e_imagem
from wuwastats.vision.parse import ErroLeitura, LeituraPersonagem, parse_echo, parse_personagem
from wuwastats.vision.prompt import PROMPT_PERSONAGEM, prompt_echo

PREFIXO_PRINT_PERSONAGEM = "personagem"

logger = logging.getLogger(__name__)


class _Resultado(BaseModel):
    model_config = ConfigDict(frozen=True)

    arquivo: str
    do_cache: bool


class EchoExtraido(_Resultado):
    tipo: Literal["ok"] = "ok"
    echo: EchoEntrada


class PersonagemExtraido(_Resultado):
    tipo: Literal["ok"] = "ok"
    leitura: LeituraPersonagem


class ExtracaoFalhou(_Resultado):
    tipo: Literal["falhou"] = "falhou"
    motivo: str
    resposta_bruta: str | None = None


ResultadoEcho = Annotated[EchoExtraido | ExtracaoFalhou, Field(discriminator="tipo")]
ResultadoPersonagem = Annotated[PersonagemExtraido | ExtracaoFalhou, Field(discriminator="tipo")]


class ExtracaoBuild(BaseModel):
    """'entrada' traz só os echos lidos com sucesso; os que falharam ficam em 'echos' para correção manual."""

    model_config = ConfigDict(frozen=True)

    entrada: EntradaBuild | None
    echos: list[ResultadoEcho]
    personagem: ResultadoPersonagem | None


@dataclass(frozen=True)
class _Resposta:
    texto: str
    do_cache: bool


@dataclass(frozen=True)
class Extrator:
    modelo: ModeloVisao
    cache: CacheVisao
    dados: GameData
    recorte_echo: Recorte | None = None

    def echo(self, arquivo: Path) -> EchoExtraido | ExtracaoFalhou:
        resposta = self._consultar(arquivo, "echo", prompt_echo(self.dados), self.recorte_echo)
        if isinstance(resposta, ExtracaoFalhou):
            return resposta
        leitura = parse_echo(resposta.texto)
        if isinstance(leitura, ErroLeitura):
            return _falha_de_leitura(arquivo, leitura, resposta)
        return EchoExtraido(arquivo=arquivo.name, do_cache=resposta.do_cache, echo=leitura)

    def personagem(self, arquivo: Path) -> PersonagemExtraido | ExtracaoFalhou:
        resposta = self._consultar(arquivo, "personagem", PROMPT_PERSONAGEM, None)
        if isinstance(resposta, ExtracaoFalhou):
            return resposta
        leitura = parse_personagem(resposta.texto)
        if isinstance(leitura, ErroLeitura):
            return _falha_de_leitura(arquivo, leitura, resposta)
        return PersonagemExtraido(arquivo=arquivo.name, do_cache=resposta.do_cache, leitura=leitura)

    def _consultar(self, arquivo: Path, tipo: TipoPrint, prompt: str, recorte: Recorte | None) -> _Resposta | ExtracaoFalhou:
        try:
            imagem = carregar_imagem(arquivo, recorte)
        except (OSError, ImagemInvalida) as erro:
            return ExtracaoFalhou(arquivo=arquivo.name, do_cache=False, motivo=f"imagem: {erro}")
        chave = ChaveCache(tipo=tipo, sha256=imagem.sha256, modelo=self.modelo.nome)
        em_cache = self.cache.ler(chave)
        if em_cache is not None:
            return _Resposta(em_cache, do_cache=True)
        try:
            texto = self.modelo.completar(prompt, imagem)
        except OpenAIError as erro:
            logger.warning(
                "extract %s: API de visão falhou: %s", tipo, erro, extra={"arquivo": arquivo.name, "modelo": self.modelo.nome}
            )
            return ExtracaoFalhou(arquivo=arquivo.name, do_cache=False, motivo=f"API de visão: {erro}")
        # Resposta malformada também vai pro cache: com temperature=0 repetir só gastaria crédito.
        self.cache.gravar(chave, texto)
        return _Resposta(texto, do_cache=False)


def _falha_de_leitura(arquivo: Path, erro: ErroLeitura, resposta: _Resposta) -> ExtracaoFalhou:
    return ExtracaoFalhou(arquivo=arquivo.name, do_cache=resposta.do_cache, motivo=erro.motivo, resposta_bruta=resposta.texto)


@dataclass(frozen=True)
class PedidoExtracao:
    build: str
    prints_echo: tuple[Path, ...]
    print_personagem: Path | None = None
    condicoes: Condicoes = Condicoes()
    regen_externa: float = 0

    def __post_init__(self) -> None:
        if not 1 <= len(self.prints_echo) <= MAX_ECHOS:
            raise ValueError(f"envie de 1 a {MAX_ECHOS} prints de echo; recebi {len(self.prints_echo)}")


def extrair_build(extrator: Extrator, pedido: PedidoExtracao, perfil: Perfil, concorrencia: int) -> ExtracaoBuild:
    with ThreadPoolExecutor(max_workers=concorrencia) as pool:
        futuro_personagem = pool.submit(extrator.personagem, pedido.print_personagem) if pedido.print_personagem else None
        echos = list(pool.map(extrator.echo, pedido.prints_echo))
        personagem = futuro_personagem.result() if futuro_personagem else None
    return ExtracaoBuild(entrada=_montar_entrada(pedido, perfil, echos, personagem), echos=echos, personagem=personagem)


def _montar_entrada(
    pedido: PedidoExtracao,
    perfil: Perfil,
    echos: Sequence[EchoExtraido | ExtracaoFalhou],
    personagem: PersonagemExtraido | ExtracaoFalhou | None,
) -> EntradaBuild | None:
    lidos = tuple(r.echo for r in echos if isinstance(r, EchoExtraido))
    if not lidos:
        return None
    leitura = personagem.leitura if isinstance(personagem, PersonagemExtraido) else LeituraPersonagem()
    return EntradaBuild(
        build=pedido.build,
        condicoes=detectar_condicoes(perfil, leitura.arma, pedido.condicoes),
        regen_externa=pedido.regen_externa,
        regen_total_informado=leitura.regen_energia_total,
        echos=lidos,
    )


def separar_prints(pasta: Path) -> tuple[tuple[Path, ...], Path | None]:
    """Echos em ordem alfabética (o 1º é o echo principal); 'personagem*.png' é a tela do personagem."""
    imagens = sorted(arquivo for arquivo in pasta.iterdir() if arquivo.is_file() and e_imagem(arquivo))
    personagem = [i for i in imagens if i.stem.lower().startswith(PREFIXO_PRINT_PERSONAGEM)]
    echos = tuple(i for i in imagens if i not in personagem)
    return echos, personagem[0] if personagem else None
