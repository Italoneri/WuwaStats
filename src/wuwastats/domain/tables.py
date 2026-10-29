"""Dados de jogo já validados e com nomes resolvidos para chaves internas."""

from collections.abc import Mapping
from dataclasses import dataclass

from wuwastats.domain.models import Condicoes, Custo, Escala
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
class EchoInfo:
    custo: Custo | None


@dataclass(frozen=True)
class BuildSpec:
    escala: Escala
    regen_energia_min: float
    custos: tuple[Custo, ...]
    set: str | None
    echo_principal: str | None
    principais: Mapping[Custo, frozenset[str]]
    pesos: Mapping[str, float]


@dataclass(frozen=True)
class Variante:
    condicao: Condicoes
    spec: BuildSpec


@dataclass(frozen=True)
class Perfil:
    personagem: str
    armas_assinatura: frozenset[str]  # já normalizados com fold(), em qualquer idioma
    base: BuildSpec
    variantes: tuple[Variante, ...]


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
