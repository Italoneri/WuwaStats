"""Entrada da análise: echos lidos (manual, JSON ou IA de visão) + contexto da build."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Custo = Literal[1, 3, 4]
Escala = Literal["ATQ", "DEF", "HP"]
MAX_ECHOS = 5
ESTRELAS_MAXIMAS = 3  # prioridade de substatus numa build: 1 a 3 estrelas


class _Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Condicoes(_Entrada):
    """Condições que escolhem a variante da build. Nova condição = novo campo opcional aqui."""

    arma_assinatura: bool | None = None


class StatLido(_Entrada):
    stat: str = Field(min_length=1)
    valor: float
    percentual: bool | None = None


class EchoEntrada(_Entrada):
    nome: str | None = None
    custo: Custo
    set: str | None = None
    principal: StatLido
    substatus: tuple[StatLido, ...] = ()


class EntradaBuild(_Entrada):
    build: str
    condicoes: Condicoes = Condicoes()
    regen_externa: float = 0
    regen_total_informado: float | None = None
    echos: tuple[EchoEntrada, ...] = Field(min_length=1, max_length=MAX_ECHOS)
