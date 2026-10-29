import pytest

from wuwastats.domain.names import NameIndex, fold, resolve_stat
from wuwastats.domain.tables import GameData


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("Regen. de Energia", "regen de energia"),
        ("Regen de Energia", "regen de energia"),
        ("  Hab.  de   Ressonância ", "hab de ressonancia"),
        ("DANO CRIT", "dano crit"),
        ("ATQ%", "atq%"),
    ],
)
def test_fold_ignora_caixa_acentos_pontos_e_espacos(bruto: str, esperado: str) -> None:
    assert fold(bruto) == esperado


@pytest.mark.parametrize(
    ("nome", "percentual", "esperado"),
    [
        ("Dano CRIT", None, "crit_dmg"),
        ("Crit DMG", None, "crit_dmg"),
        ("crit_dmg", None, "crit_dmg"),
        ("dano critico", None, None),
        ("ATQ%", None, "atk_pct"),
        ("ATQ", True, "atk_pct"),
        ("ATQ", False, "atk_flat"),
        ("ATQ", None, None),
        ("HP", False, "hp_flat"),
        ("Taxa CRIT%", None, "crit_rate"),
        ("Regen de Energia", None, "energy_regen"),
        ("Hab. de Ressonancia", None, "skill_dmg"),
    ],
)
def test_resolve_stat(dados: GameData, nome: str, percentual: bool | None, esperado: str | None) -> None:
    assert resolve_stat(dados.stat_names, nome, percentual) == esperado


def test_name_index_lista_nomes_ambiguos() -> None:
    indice = NameIndex.build({"a": ["X"], "b": ["x", "Y"]})

    assert indice.ambiguous_names() == {"x": frozenset({"a", "b"})}
    assert indice.resolve("y") == "b"
    assert indice.resolve("X") is None
