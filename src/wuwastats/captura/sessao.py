"""Estado de uma sessão de captura: 5 espaços de echo (na ordem dos slots) + 1 do personagem.

Só funções puras: cada operação devolve uma Sessao nova. Cada print recebe um número de captura; a leitura
da IA, que termina depois, acha o espaço por esse número (o usuário pode ter reordenado ou esvaziado no meio).
"""

from collections.abc import Sequence
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from wuwastats.domain.models import MAX_ECHOS, Condicoes, EchoEntrada, EntradaBuild
from wuwastats.domain.tables import Perfil
from wuwastats.domain.variants import detectar_condicoes
from wuwastats.vision.parse import LeituraPersonagem


class EspacosCheios(Exception):
    pass


class OrdemInvalida(ValueError):
    pass


class _Estado(BaseModel):
    model_config = ConfigDict(frozen=True)


class Vazio(_Estado):
    estado: Literal["vazio"] = "vazio"


class Recebido(_Estado):
    estado: Literal["recebido"] = "recebido"
    captura: int


class Lendo(_Estado):
    estado: Literal["lendo"] = "lendo"
    captura: int


class Falhou(_Estado):
    estado: Literal["falhou"] = "falhou"
    captura: int
    motivo: str


class EchoLido(_Estado):
    estado: Literal["lido"] = "lido"
    captura: int
    do_cache: bool
    echo: EchoEntrada


class PersonagemLido(_Estado):
    estado: Literal["lido"] = "lido"
    captura: int
    do_cache: bool
    leitura: LeituraPersonagem


EspacoEcho = Annotated[Vazio | Recebido | Lendo | Falhou | EchoLido, Field(discriminator="estado")]
EspacoPersonagem = Annotated[Vazio | Recebido | Lendo | Falhou | PersonagemLido, Field(discriminator="estado")]


class Sessao(_Estado):
    id: str
    build: str
    ativa: bool = True
    echos: tuple[EspacoEcho, ...] = (Vazio(),) * MAX_ECHOS
    personagem: EspacoPersonagem = Vazio()
    alvo_f8: int | None = Field(default=None, description="Espaço marcado com 'Refazer'; sem marca, o F8 usa o primeiro vazio.")
    ultima_captura: int = 0


def proximo_alvo(sessao: Sessao) -> int | None:
    if sessao.alvo_f8 is not None:
        return sessao.alvo_f8
    return next((i for i, espaco in enumerate(sessao.echos) if isinstance(espaco, Vazio)), None)


def receber_echo(sessao: Sessao) -> tuple[Sessao, int, int]:
    """Devolve (sessão, índice do espaço, número da captura)."""
    indice = proximo_alvo(sessao)
    if indice is None:
        raise EspacosCheios(f"os {MAX_ECHOS} espaços de echo estão ocupados; use 'Refazer' ou remova um print")
    captura = sessao.ultima_captura + 1
    echos = _trocar(sessao.echos, indice, Recebido(captura=captura))
    return sessao.model_copy(update={"echos": echos, "alvo_f8": None, "ultima_captura": captura}), indice, captura


def receber_personagem(sessao: Sessao) -> tuple[Sessao, int]:
    captura = sessao.ultima_captura + 1
    return sessao.model_copy(update={"personagem": Recebido(captura=captura), "ultima_captura": captura}), captura


def atualizar_echo(sessao: Sessao, captura: int, novo: EspacoEcho) -> tuple[Sessao, int | None]:
    """Troca o espaço que ainda guarda essa captura. Se o print saiu da sessão, nada muda (índice None)."""
    indice = next((i for i, espaco in enumerate(sessao.echos) if _captura(espaco) == captura), None)
    if indice is None:
        return sessao, None
    return sessao.model_copy(update={"echos": _trocar(sessao.echos, indice, novo)}), indice


def atualizar_personagem(sessao: Sessao, captura: int, novo: EspacoPersonagem) -> tuple[Sessao, bool]:
    if _captura(sessao.personagem) != captura:
        return sessao, False
    return sessao.model_copy(update={"personagem": novo}), True


def reordenar(sessao: Sessao, ordem: Sequence[int]) -> Sessao:
    """ordem[j] = índice atual do espaço que passa para a posição j. A marca de 'Refazer' acompanha o espaço."""
    if sorted(ordem) != list(range(MAX_ECHOS)):
        raise OrdemInvalida(f"ordem deve ser uma permutação de 0 a {MAX_ECHOS - 1}; recebi {list(ordem)}")
    alvo = None if sessao.alvo_f8 is None else list(ordem).index(sessao.alvo_f8)
    return sessao.model_copy(update={"echos": tuple(sessao.echos[i] for i in ordem), "alvo_f8": alvo})


def esvaziar_echo(sessao: Sessao, indice: int) -> Sessao:
    return sessao.model_copy(update={"echos": _trocar(sessao.echos, indice, Vazio())})


def esvaziar_personagem(sessao: Sessao) -> Sessao:
    return sessao.model_copy(update={"personagem": Vazio()})


def refazer(sessao: Sessao, indice: int) -> Sessao:
    """O print atual fica até o próximo F8, que vai para este espaço."""
    if not 0 <= indice < MAX_ECHOS:
        raise IndexError(f"espaço de echo {indice} não existe")
    return sessao.model_copy(update={"alvo_f8": indice})


def encerrar(sessao: Sessao) -> Sessao:
    return sessao.model_copy(update={"ativa": False})


def montar_entrada(sessao: Sessao, perfil: Perfil) -> EntradaBuild | None:
    """Só os echos lidos, na ordem dos espaços; None se nenhum foi lido. Os que falharam se preenchem na análise."""
    echos = tuple(espaco.echo for espaco in sessao.echos if isinstance(espaco, EchoLido))
    if not echos:
        return None
    leitura = sessao.personagem.leitura if isinstance(sessao.personagem, PersonagemLido) else LeituraPersonagem()
    return EntradaBuild(
        build=sessao.build,
        condicoes=detectar_condicoes(perfil, leitura.arma, Condicoes()),
        regen_total_informado=leitura.regen_energia_total,
        echos=echos,
    )


def _captura(espaco: EspacoEcho | EspacoPersonagem) -> int | None:
    return None if isinstance(espaco, Vazio) else espaco.captura


def _trocar(echos: tuple[EspacoEcho, ...], indice: int, novo: EspacoEcho) -> tuple[EspacoEcho, ...]:
    if not 0 <= indice < len(echos):
        raise IndexError(f"espaço de echo {indice} não existe")
    return (*echos[:indice], novo, *echos[indice + 1 :])
