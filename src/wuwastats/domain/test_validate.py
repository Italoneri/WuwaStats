import pytest

from wuwastats.domain.tables import GameData
from wuwastats.domain.validate import posicao_pct, snap


@pytest.mark.parametrize(
    ("stat", "lido", "valor", "tier", "dentro"),
    [
        ("crit_dmg", 17.5, 17.4, 5, True),
        ("crit_dmg", 21.0, 21.0, 8, True),
        ("crit_dmg", 25.0, 21.0, 8, False),
        ("crit_dmg", 17.0, 17.4, 5, False),
        ("crit_rate", 8.1, 8.1, 4, True),
        ("crit_rate", 6.2, 6.3, 1, True),
        ("atk_pct", 7.0, 7.1, 2, True),
        ("atk_flat", 49, 50, 3, True),
        ("atk_flat", 45, 40, 2, False),
        ("hp_flat", 435, 430, 4, True),
    ],
)
def test_snap_aproxima_para_valor_valido(
    dados: GameData, stat: str, lido: float, valor: float, tier: int, dentro: bool
) -> None:
    ajuste = snap(dados.substats[stat], lido)

    assert (ajuste.valor, ajuste.tier, ajuste.dentro_tolerancia) == (valor, tier, dentro)


def test_snap_informa_diferenca_arredondada(dados: GameData) -> None:
    assert snap(dados.substats["crit_dmg"], 17.5).diferenca == 0.1


@pytest.mark.parametrize(
    ("stat", "valor", "esperado"),
    [
        ("crit_dmg", 12.6, 0.0),
        ("crit_dmg", 21.0, 100.0),
        ("crit_rate", 8.4, 50.0),
        ("atk_flat", 40, 33.3),
    ],
)
def test_posicao_pct_entre_min_e_max(dados: GameData, stat: str, valor: float, esperado: float) -> None:
    assert posicao_pct(dados.substats[stat], valor) == esperado
