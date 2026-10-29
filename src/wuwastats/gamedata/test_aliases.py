import json
import re
from pathlib import Path

import pytest

from wuwastats.domain.names import resolve_stat
from wuwastats.domain.report import CategoriaNome
from wuwastats.gamedata.aliases import AliasInvalido, registrar_alias
from wuwastats.gamedata.loader import load_game_data


def test_alias_registrado_passa_a_resolver_apos_recarregar(data_dir_copia: Path) -> None:
    dados = load_game_data(data_dir_copia)

    registrar_alias(data_dir_copia, dados, "sets", "Moonlit Clouds", "Nuvens ao Luar")
    registrar_alias(data_dir_copia, dados, "stats", "crit_dmg", "Dano Crítico")

    recarregado = load_game_data(data_dir_copia)
    assert recarregado.set_names.resolve("nuvens ao luar") == "Moonlit Clouds"
    assert resolve_stat(recarregado.stat_names, "Dano Critico") == "crit_dmg"


def test_registrar_o_mesmo_alias_duas_vezes_nao_duplica(data_dir_copia: Path) -> None:
    dados = load_game_data(data_dir_copia)

    registrar_alias(data_dir_copia, dados, "echoes", "Suhsin", "Suhsin PT")
    registrar_alias(data_dir_copia, dados, "echoes", "Suhsin", "Suhsin PT")

    aliases = json.loads((data_dir_copia / "stat_aliases.json").read_text(encoding="utf-8"))
    assert aliases["echoes"]["Suhsin"] == ["Suhsin PT"]


@pytest.mark.parametrize(
    ("categoria", "chave", "alias", "trecho"),
    [
        ("sets", "Set Fantasma", "Qualquer", "não existe em sets"),
        ("stats", "crit_dmg", "Taxa CRIT", "já aponta para ['crit_rate']"),
        ("echoes", "Suhsin", "   ", "alias vazio"),
    ],
)
def test_rejeita_alias_invalido_sem_tocar_no_arquivo(
    data_dir_copia: Path, categoria: CategoriaNome, chave: str, alias: str, trecho: str
) -> None:
    dados = load_game_data(data_dir_copia)
    antes = (data_dir_copia / "stat_aliases.json").read_bytes()

    with pytest.raises(AliasInvalido, match=re.escape(trecho)):
        registrar_alias(data_dir_copia, dados, categoria, chave, alias)

    assert (data_dir_copia / "stat_aliases.json").read_bytes() == antes
