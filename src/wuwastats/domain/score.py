"""Score ponderado pelos pesos da build e Crit Value."""

from collections.abc import Iterable, Mapping, Sequence

from wuwastats.domain.names import CRIT_DMG, CRIT_RATE
from wuwastats.domain.tables import FaixaNota

MAX_SUBSTATUS = 5


def melhor_caso(pesos: Mapping[str, float], substats_existentes: Iterable[str]) -> float:
    """Pontos de um echo perfeito: os 5 substatus de maior peso, todos no valor máximo."""
    maiores = sorted((pesos.get(stat, 0.0) for stat in substats_existentes), reverse=True)
    return sum(maiores[:MAX_SUBSTATUS])


def pontos(peso: float, valor: float, maximo: float) -> float:
    return peso * valor / maximo


def score_pct(pontos_obtidos: float, melhor: float) -> float:
    if melhor <= 0:
        return 0.0
    return round(pontos_obtidos / melhor * 100, 1)


def crit_value(stats: Iterable[tuple[str | None, float]]) -> float:
    multiplicador = {CRIT_RATE: 2.0, CRIT_DMG: 1.0}
    return round(sum(multiplicador.get(stat or "", 0.0) * valor for stat, valor in stats), 2)


def nota(score: float, faixas: Sequence[FaixaNota]) -> str:
    """O loader garante faixas decrescentes terminando em 0; score negativo cai na última."""
    return next((f.nota for f in faixas if score >= f.min), faixas[-1].nota)
