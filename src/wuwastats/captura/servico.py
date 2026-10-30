"""Captura no servidor: atalho global -> print -> leitura imediata pela IA -> eventos para a página.

O que depende do Windows (tela, teclas, bipe) chega por FerramentasCaptura, para os testes trocarem por falsos.
Os ouvintes de eventos são chamados com a trava segura, na ordem dos acontecimentos: devem só enfileirar, nunca bloquear.
"""

import logging
import shutil
import tempfile
import threading
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from wuwastats.captura.sessao import (
    EchoLido,
    EspacoEcho,
    EspacoPersonagem,
    EspacosCheios,
    Falhou,
    Lendo,
    PersonagemLido,
    Sessao,
    atualizar_echo,
    atualizar_personagem,
    encerrar,
    esvaziar_echo,
    esvaziar_personagem,
    montar_entrada,
    receber_echo,
    receber_personagem,
    refazer,
    reordenar,
)
from wuwastats.captura.teclas import Acao
from wuwastats.domain.models import EntradaBuild, StatLido
from wuwastats.domain.tables import Perfil
from wuwastats.vision.extract import EchoExtraido, Extrator, PersonagemExtraido

Sinal = Literal["ok", "erro"]
Local = int | Literal["personagem"]
TipoEvento = Literal[
    "estado", "print_recebido", "leitura_iniciada", "lido", "falhou", "ir_para_analise", "erro_captura", "encerrada"
]

logger = logging.getLogger(__name__)


class CapturaFalhou(Exception):
    pass


class CapturaIndisponivel(CapturaFalhou):
    pass


class SessaoInexistente(Exception):
    pass


class SemEchoLido(Exception):
    pass


class Escuta(Protocol):
    def parar(self) -> None: ...


@dataclass(frozen=True)
class FerramentasCaptura:
    capturar_tela: Callable[[], bytes]
    escutar_atalhos: Callable[[Mapping[Acao, Callable[[], None]]], Escuta]
    sinalizar: Callable[[Sinal], None]


class Evento(BaseModel):
    model_config = ConfigDict(frozen=True)

    tipo: TipoEvento
    espaco: Local | None = None
    nome: str | None = None
    principal: StatLido | None = None
    motivo: str | None = None
    sessao: Sessao


Ouvinte = Callable[[Evento], None]
Executar = Callable[[Callable[[], None]], object]


@dataclass(frozen=True)
class _Detalhe:
    tipo: TipoEvento
    nome: str | None = None
    principal: StatLido | None = None
    motivo: str | None = None


class ServicoCaptura:
    """Uma sessão por vez: iniciar outra encerra a anterior (os atalhos são globais)."""

    def __init__(self, ferramentas: FerramentasCaptura, criar_extrator: Callable[[], Extrator], executar: Executar) -> None:
        """executar: roda a leitura fora da thread dos atalhos (ex.: submit de um pool com limite de concorrência)."""
        self._ferramentas = ferramentas
        self._criar_extrator = criar_extrator
        self._executar = executar
        self._trava = threading.Lock()
        self._sessao: Sessao | None = None
        self._pasta: Path | None = None
        self._escuta: Escuta | None = None
        self._extrator: Extrator | None = None
        self._ouvintes: dict[object, Ouvinte] = {}

    # --- Comandos da página ---

    def iniciar(self, build: str) -> Sessao:
        extrator = self._criar_extrator()  # sem IA configurada não há leitura imediata: falha antes de ligar os atalhos
        self.parar()
        escuta = self._ferramentas.escutar_atalhos(
            {"echo": self._capturar_echo, "personagem": self._capturar_personagem, "analise": self._ir_para_analise}
        )
        with self._trava:
            self._sessao = Sessao(id=uuid.uuid4().hex[:12], build=build)
            self._pasta = Path(tempfile.mkdtemp(prefix="wuwastats-captura-"))
            self._escuta, self._extrator = escuta, extrator
            logger.info("captura iniciada", extra={"sessao": self._sessao.id, "build": build})
            return self._sessao

    def parar(self) -> None:
        with self._trava:
            escuta, pasta, sessao = self._escuta, self._pasta, self._sessao
            self._escuta, self._pasta = None, None
            if sessao is not None and sessao.ativa:
                self._sessao = encerrar(sessao)
                self._publicar(Evento(tipo="encerrada", sessao=self._sessao))
        if escuta is not None:
            escuta.parar()
        if pasta is not None:
            shutil.rmtree(pasta, onexc=_avisar_limpeza)

    def estado(self, sessao_id: str) -> Sessao:
        with self._trava:
            return self._exigir(sessao_id)

    def reordenar(self, sessao_id: str, ordem: Sequence[int]) -> Sessao:
        return self._alterar(sessao_id, lambda s: reordenar(s, ordem))

    def esvaziar_echo(self, sessao_id: str, indice: int) -> Sessao:
        return self._alterar(sessao_id, lambda s: esvaziar_echo(s, indice))

    def esvaziar_personagem(self, sessao_id: str) -> Sessao:
        return self._alterar(sessao_id, esvaziar_personagem)

    def refazer(self, sessao_id: str, indice: int) -> Sessao:
        return self._alterar(sessao_id, lambda s: refazer(s, indice))

    def entrada(self, sessao_id: str, perfil_da_build: Callable[[str], Perfil]) -> EntradaBuild:
        sessao = self.estado(sessao_id)
        entrada = montar_entrada(sessao, perfil_da_build(sessao.build))
        if entrada is None:
            raise SemEchoLido("nenhum echo foi lido ainda nesta sessão")
        return entrada

    def inscrever(self, sessao_id: str, ouvinte: Ouvinte) -> Callable[[], None]:
        """Entrega já o estado atual; sessão encerrada recebe também 'encerrada'. Devolve a função de cancelar."""
        chave = object()
        with self._trava:
            sessao = self._exigir(sessao_id)
            ouvinte(Evento(tipo="estado", sessao=sessao))
            if not sessao.ativa:
                ouvinte(Evento(tipo="encerrada", sessao=sessao))
                return lambda: None
            self._ouvintes[chave] = ouvinte

        def cancelar() -> None:
            with self._trava:
                self._ouvintes.pop(chave, None)

        return cancelar

    # --- Atalhos (rodam na thread da escuta) ---

    def _capturar_echo(self) -> None:
        self._receber_print(receber_echo, self._ler_echo)

    def _capturar_personagem(self) -> None:
        self._receber_print(_receber_personagem, self._ler_personagem)

    def _ir_para_analise(self) -> None:
        with self._trava:
            if self._sessao is None or not self._sessao.ativa:
                return
            self._publicar(Evento(tipo="ir_para_analise", sessao=self._sessao))
        self._ferramentas.sinalizar("ok")

    def _receber_print(
        self,
        receber: Callable[[Sessao], tuple[Sessao, Local, int]],
        ler: Callable[[str, int, Path], None],
    ) -> None:
        try:
            png = self._ferramentas.capturar_tela()
            with self._trava:
                sessao, pasta = self._ativa()
                sessao, local, captura = receber(sessao)
                self._sessao = sessao
                self._publicar(Evento(tipo="print_recebido", espaco=local, sessao=sessao))
            arquivo = pasta / f"{captura}.png"
            arquivo.write_bytes(png)
        except (CapturaFalhou, EspacosCheios, OSError) as erro:
            self._erro_captura(erro)
            return
        self._ferramentas.sinalizar("ok")
        sessao_id = sessao.id
        self._executar(lambda: self._em_segundo_plano(lambda: ler(sessao_id, captura, arquivo), sessao_id, captura))

    def _erro_captura(self, erro: Exception) -> None:
        logger.warning("captura: %s", erro)
        self._ferramentas.sinalizar("erro")
        with self._trava:
            if self._sessao is not None and self._sessao.ativa:
                self._publicar(Evento(tipo="erro_captura", motivo=str(erro), sessao=self._sessao))

    # --- Leitura (roda no pool) ---

    def _ler_echo(self, sessao_id: str, captura: int, arquivo: Path) -> None:
        extrator = self._extrator_da(sessao_id)
        if extrator is None:
            return
        self._mudar_echo(sessao_id, captura, Lendo(captura=captura), _Detalhe("leitura_iniciada"))
        resultado = extrator.echo(arquivo)
        if isinstance(resultado, EchoExtraido):
            lido = EchoLido(captura=captura, do_cache=resultado.do_cache, echo=resultado.echo)
            detalhe = _Detalhe("lido", nome=resultado.echo.nome, principal=resultado.echo.principal)
            self._mudar_echo(sessao_id, captura, lido, detalhe)
        else:
            falhou = Falhou(captura=captura, motivo=resultado.motivo)
            self._mudar_echo(sessao_id, captura, falhou, _Detalhe("falhou", motivo=resultado.motivo))

    def _ler_personagem(self, sessao_id: str, captura: int, arquivo: Path) -> None:
        extrator = self._extrator_da(sessao_id)
        if extrator is None:
            return
        self._mudar_personagem(sessao_id, captura, Lendo(captura=captura), _Detalhe("leitura_iniciada"))
        resultado = extrator.personagem(arquivo)
        if isinstance(resultado, PersonagemExtraido):
            lido = PersonagemLido(captura=captura, do_cache=resultado.do_cache, leitura=resultado.leitura)
            self._mudar_personagem(sessao_id, captura, lido, _Detalhe("lido", nome=resultado.leitura.personagem))
        else:
            falhou = Falhou(captura=captura, motivo=resultado.motivo)
            self._mudar_personagem(sessao_id, captura, falhou, _Detalhe("falhou", motivo=resultado.motivo))

    def _em_segundo_plano(self, tarefa: Callable[[], None], sessao_id: str, captura: int) -> None:
        """Fronteira da thread do pool: erro inesperado vira 'falhou' no espaço em vez de sumir no Future."""
        try:
            tarefa()
        except Exception as erro:
            logger.exception("leitura da captura %s falhou", captura, extra={"sessao": sessao_id})
            falhou = Falhou(captura=captura, motivo=f"erro interno: {erro}")
            detalhe = _Detalhe("falhou", motivo=falhou.motivo)
            self._mudar_echo(sessao_id, captura, falhou, detalhe)
            self._mudar_personagem(sessao_id, captura, falhou, detalhe)

    def _mudar_echo(self, sessao_id: str, captura: int, novo: EspacoEcho, detalhe: _Detalhe) -> None:
        with self._trava:
            if self._sessao is None or self._sessao.id != sessao_id:
                return
            sessao, indice = atualizar_echo(self._sessao, captura, novo)
            if indice is not None:
                self._sessao = sessao
                self._publicar(_completar(detalhe, indice, sessao))

    def _mudar_personagem(self, sessao_id: str, captura: int, novo: EspacoPersonagem, detalhe: _Detalhe) -> None:
        with self._trava:
            if self._sessao is None or self._sessao.id != sessao_id:
                return
            sessao, mudou = atualizar_personagem(self._sessao, captura, novo)
            if mudou:
                self._sessao = sessao
                self._publicar(_completar(detalhe, "personagem", sessao))

    # --- Internos (chamar com a trava) ---

    def _alterar(self, sessao_id: str, mudanca: Callable[[Sessao], Sessao]) -> Sessao:
        with self._trava:
            self._sessao = mudanca(self._exigir(sessao_id))
            self._publicar(Evento(tipo="estado", sessao=self._sessao))
            return self._sessao

    def _exigir(self, sessao_id: str) -> Sessao:
        if self._sessao is None or self._sessao.id != sessao_id:
            raise SessaoInexistente(f"sessão de captura '{sessao_id}' não existe ou foi substituída por outra")
        return self._sessao

    def _ativa(self) -> tuple[Sessao, Path]:
        if self._sessao is None or not self._sessao.ativa or self._pasta is None:
            raise CapturaFalhou("nenhuma sessão de captura ativa")
        return self._sessao, self._pasta

    def _extrator_da(self, sessao_id: str) -> Extrator | None:
        with self._trava:
            mesma = self._sessao is not None and self._sessao.id == sessao_id
            return self._extrator if mesma else None

    def _publicar(self, evento: Evento) -> None:
        for ouvinte in list(self._ouvintes.values()):
            ouvinte(evento)


def _receber_personagem(sessao: Sessao) -> tuple[Sessao, Local, int]:
    nova, captura = receber_personagem(sessao)
    return nova, "personagem", captura


def _completar(detalhe: _Detalhe, espaco: Local, sessao: Sessao) -> Evento:
    return Evento(
        tipo=detalhe.tipo, espaco=espaco, nome=detalhe.nome, principal=detalhe.principal, motivo=detalhe.motivo, sessao=sessao
    )


def _avisar_limpeza(_funcao: Callable[..., object], caminho: str, erro: BaseException) -> None:
    logger.warning("não consegui apagar %s: %s", caminho, erro)
