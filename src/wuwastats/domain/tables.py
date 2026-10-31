"""Dados de jogo já validados e com nomes resolvidos para chaves internas."""

from collections.abc import Mapping
from dataclasses import dataclass

from wuwastats.domain.models import ESTRELAS_MAXIMAS, Condicoes, Custo, Escala
from wuwastats.domain.names import NameIndex


@dataclass(frozen=True)
class SubstatTable:
    valores: tuple[float, ...]
    tolerancia: float

    @property
    def min(self) -> float:
        return self.valores[0]

    @property
    def max(self) -> float:
        return self.valores[-1]


@dataclass(frozen=True)
class MainStatTable:
    primarios: Mapping[str, float]
    secundario: Mapping[str, float]


@dataclass(frozen=True)
class SetInfo:
    pecas: int | None
    bonus: Mapping[int, Mapping[str, float]]


@dataclass(frozen=True)
class Traducao:
    en: str
    pt: str | None

    @property
    def rotulo(self) -> str:
        return self.pt or self.en


@dataclass(frozen=True)
class EchoInfo:
    custo: Custo | None
    sets: tuple[str, ...] = ()
    habilidade: Traducao | None = None  # o que o echo faz, com os valores do nível mais alto


@dataclass(frozen=True)
class BuildSpec:
    escala: Escala
    regen_energia_min: float
    custos: tuple[Custo, ...]
    set: str | None
    echo_principal: str | None
    principais: Mapping[Custo, frozenset[str]]
    estrelas: Mapping[str, int]  # 1 a ESTRELAS_MAXIMAS; status fora daqui a build ignora

    @property
    def pesos(self) -> dict[str, float]:
        """Peso no score: 3 estrelas valem o triplo de 1."""
        return {stat: estrelas / ESTRELAS_MAXIMAS for stat, estrelas in self.estrelas.items()}


@dataclass(frozen=True)
class Variante:
    condicao: Condicoes
    spec: BuildSpec


@dataclass(frozen=True)
class ArmasPerfil:
    melhor: str | None
    alternativas: tuple[str, ...]


@dataclass(frozen=True)
class Perfil:
    personagem: str  # chave em resonators.json
    armas_assinatura: frozenset[str]  # já normalizados com fold(), em qualquer idioma
    base: BuildSpec
    variantes: tuple[Variante, ...]
    armas: ArmasPerfil | None = None
    descricao: str | None = None


@dataclass(frozen=True)
class Ressonador:
    elemento: str
    tipo_arma: str
    raridade: int


@dataclass(frozen=True)
class Arma:
    tipo: str
    raridade: int


@dataclass(frozen=True)
class FaixaNota:
    nota: str
    min: float


@dataclass(frozen=True)
class GameData:
    substats: Mapping[str, SubstatTable]
    main_stats: Mapping[Custo, MainStatTable]
    sets: Mapping[str, SetInfo]
    echoes: Mapping[str, EchoInfo]
    echos_repetidos_contam: bool
    stat_names: NameIndex
    echo_names: NameIndex
    set_names: NameIndex
    perfis: Mapping[str, Perfil]
    notas: tuple[FaixaNota, ...]  # ordem decrescente de min; a última tem min 0
    elementos: Mapping[str, Traducao]
    tipos_arma: Mapping[str, Traducao]
    ressonadores: Mapping[str, Ressonador]
    armas: Mapping[str, Arma]
    ressonador_names: NameIndex
    arma_names: NameIndex
