"""Metas de status de uma build (Regen, crítico, HP…) e o veredito do valor lido contra a meta.

O mesmo modelo serve de schema do characters.json, de dado de domínio e de saída da API: a meta não tem nome a resolver.
"""

from collections.abc import Callable
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wuwastats.domain.names import ENERGY_REGEN, is_percent_stat

StatDeMeta = Literal["energy_regen", "crit_rate", "crit_dmg", "hp_flat", "atk_flat", "def_flat"]
TipoDeMeta = Literal["escala", "rotacao"]  # escala: o kit converte o status até um teto; rotacao: basta bater o valor
FonteDeMeta = Literal["game8", "prydwen"]
Veredito = Literal["abaixo", "dentro", "acima"]
OrigemValor = Literal["tela", "echos"]

REGEN_BASE = 100.0


class MetaDeStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stat: StatDeMeta
    min: float = Field(gt=0)
    max: float | None = None
    tipo: TipoDeMeta
    explicacao: str | None = Field(default=None, min_length=1, description="Uma frase: o que muda de uma ponta à outra.")
    fonte: FonteDeMeta

    @model_validator(mode="after")
    def _faixa_valida(self) -> Self:
        if self.max is not None and self.max < self.min:
            raise ValueError("max menor que min")
        if self.stat == ENERGY_REGEN and self.min < REGEN_BASE:
            raise ValueError("Regen. de Energia começa em 100%")
        return self

    @property
    def teto(self) -> float:
        return self.min if self.max is None else self.max


class MetaAnalise(BaseModel):
    model_config = ConfigDict(frozen=True)

    meta: MetaDeStatus
    valor: float | None = Field(description="Valor comparado; null sem print da tela (a meta fica só de referência).")
    origem: OrigemValor | None
    veredito: Veredito | None
    mensagem: str | None


def comparar_meta(meta: MetaDeStatus, valor: float | None, origem: OrigemValor | None) -> MetaAnalise:
    if valor is None:
        return MetaAnalise(meta=meta, valor=None, origem=origem, veredito=None, mensagem=None)
    veredito, mensagem = _VEREDITO_POR_TIPO[meta.tipo](meta, valor)
    return MetaAnalise(meta=meta, valor=valor, origem=origem, veredito=veredito, mensagem=mensagem)


def formatar_valor(stat: StatDeMeta, valor: float) -> str:
    if is_percent_stat(stat):
        return f"{round(valor, 2):g}%"
    return f"{round(valor):,}".replace(",", ".")


def metas_unicas(metas: list[MetaDeStatus]) -> list[MetaDeStatus]:
    vistos: set[str] = set()
    for meta in metas:
        if meta.stat in vistos:
            raise ValueError(f"meta de {meta.stat} repetida")
        vistos.add(meta.stat)
    return metas


def _rotacao(meta: MetaDeStatus, valor: float) -> tuple[Veredito, str]:
    if valor < meta.min:
        return "abaixo", f"abaixo da meta, faltam {_diferenca(meta, meta.min - valor)}"
    if meta.max is None or valor <= meta.max:
        return "dentro", "dentro da faixa"
    if meta.stat == ENERGY_REGEN:
        return "acima", f"acima da faixa, {_diferenca(meta, valor - meta.max)} sobrando"
    return "acima", "acima da faixa, quanto mais melhor"


def _escala(meta: MetaDeStatus, valor: float) -> tuple[Veredito, str]:
    if valor >= meta.teto:
        return "acima", "no teto, o que passar sobra"
    if valor < meta.min:
        return "abaixo", "abaixo, perde poder"
    return "dentro", f"rendendo, faltam {_diferenca(meta, meta.teto - valor)} para o teto"


def _diferenca(meta: MetaDeStatus, diferenca: float) -> str:
    return formatar_valor(meta.stat, round(diferenca, 2))


_VEREDITO_POR_TIPO: dict[TipoDeMeta, Callable[[MetaDeStatus, float], tuple[Veredito, str]]] = {
    "escala": _escala,
    "rotacao": _rotacao,
}
