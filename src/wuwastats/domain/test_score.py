import pytest

from wuwastats.domain.score import crit_value, melhor_caso, nota, score_pct
from wuwastats.domain.tables import FaixaNota

FAIXAS = (FaixaNota("S", 65), FaixaNota("A", 40), FaixaNota("C", 0))


def test_melhor_caso_soma_os_cinco_maiores_pesos_de_substatus() -> None:
    pesos = {"a": 1.0, "b": 1.0, "c": 0.8, "d": 0.7, "e": 0.4, "f": 0.3, "fora": 5.0}

    assert melhor_caso(pesos, ["a", "b", "c", "d", "e", "f", "sem_peso"]) == pytest.approx(3.9)


def test_score_pct_e_zero_quando_build_nao_pesa_nenhum_substatus() -> None:
    assert score_pct(0.0, 0.0) == 0.0


def test_crit_value_dobra_taxa_e_ignora_outros_stats() -> None:
    stats = [("crit_rate", 8.1), ("crit_dmg", 17.4), ("atk_pct", 10.1), (None, 99.0)]

    assert crit_value(stats) == 33.6


@pytest.mark.parametrize(("score", "esperada"), [(100.0, "S"), (65.0, "S"), (64.9, "A"), (40.0, "A"), (0.0, "C"), (-1.0, "C")])
def test_nota_usa_a_primeira_faixa_alcancada(score: float, esperada: str) -> None:
    assert nota(score, FAIXAS) == esperada
