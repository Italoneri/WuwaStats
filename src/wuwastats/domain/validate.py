"""Aproxima valores lidos para os valores discretos válidos de cada substatus."""

from dataclasses import dataclass

from wuwastats.domain.tables import SubstatTable

_EPSILON = 1e-9


@dataclass(frozen=True)
class Ajuste:
    valor: float
    tier: int
    diferenca: float
    dentro_tolerancia: bool


def snap(tabela: SubstatTable, lido: float) -> Ajuste:
    indice, valor = min(enumerate(tabela.valores), key=lambda par: abs(par[1] - lido))
    diferenca = round(lido - valor, 4)
    return Ajuste(
        valor=valor,
        tier=indice + 1,
        diferenca=diferenca,
        dentro_tolerancia=abs(diferenca) <= tabela.tolerancia + _EPSILON,
    )


def posicao_pct(tabela: SubstatTable, valor: float) -> float:
    if tabela.max == tabela.min:
        return 100.0
    return round((valor - tabela.min) / (tabela.max - tabela.min) * 100, 1)
