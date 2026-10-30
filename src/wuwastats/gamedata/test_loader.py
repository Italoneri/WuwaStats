import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from wuwastats.config import PROJECT_ROOT
from wuwastats.gamedata.loader import GameDataError, load_game_data

Json = dict[str, Any]


def test_dados_reais_do_projeto_sao_validos() -> None:
    dados = load_game_data(PROJECT_ROOT / "data")

    assert "Suoming_DPS" in dados.perfis


def test_resolve_nomes_pt_br_do_perfil_para_chaves_internas(data_dir_copia: Path) -> None:
    perfil = load_game_data(data_dir_copia).perfis["Suoming_DPS"]

    assert perfil.base.principais[3] == frozenset({"electro_dmg", "atk_pct"})
    assert perfil.base.pesos["basic_atk_dmg"] == 0.7


def _editar(data_dir: Path, arquivo: str, mudar: Callable[[Json], None]) -> None:
    caminho = data_dir / arquivo
    conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    mudar(conteudo)
    caminho.write_text(json.dumps(conteudo, ensure_ascii=False), encoding="utf-8")


def _suoming(campo: str, valor: object) -> Callable[[Json], None]:
    return lambda conteudo: conteudo["Suoming_DPS"].__setitem__(campo, valor)


def _variante(campo: str, valor: object) -> Callable[[Json], None]:
    return lambda conteudo: conteudo["Suoming_DPS"]["variantes"][0].__setitem__(campo, valor)


@pytest.mark.parametrize(
    ("arquivo", "mudar", "trecho"),
    [
        ("characters.json", _suoming("pesos", {"ATQ": 1.0}), "pesos › ATQ: status 'ATQ' desconhecido ou ambíguo"),
        ("characters.json", _suoming("principais", {"1": ["Dano CRIT"]}), "principal de echo custo 1"),
        ("characters.json", _suoming("custos", [4, 4, 4, 1, 1]), "custo total 14"),
        ("characters.json", _suoming("custos", [4, 3, 3, 1]), "custos"),
        ("characters.json", _suoming("set", "Set Inexistente"), "set: 'Set Inexistente' não está no catálogo"),
        ("characters.json", _suoming("regen_energia_min", 90), "regen_energia_min"),
        ("characters.json", _variante("condicao", {"sequencia": 2}), "sequencia"),
        ("characters.json", _variante("condicao", {}), "condição vazia"),
        ("characters.json", _variante("echo_principal", "Ninguém"), "variantes › 0 › echo_principal"),
        ("substats.json", lambda c: c["substatus"]["crit_rate"].__setitem__("valores", [7.5, 6.3]), "ordem crescente"),
        ("main_stats.json", lambda c: c["custos"].pop("3"), "faltam os custos"),
        ("stat_aliases.json", lambda c: c["sets"].__setitem__("Set Fantasma", []), "Set Fantasma: não existe"),
        ("stat_aliases.json", lambda c: c["stats"]["crit_rate"].append("Dano CRIT"), "'dano crit' aponta para"),
        ("sets.json", lambda c: c["sets"]["Moonlit Clouds"]["bonus"]["2"].__setitem__("Sorte", 1), "Sorte"),
        ("notas.json", lambda c: c["faixas"].reverse(), "ordem decrescente"),
        ("notas.json", lambda c: c["faixas"].pop(), "última faixa precisa ter min 0"),
    ],
)
def test_acusa_erro_apontando_arquivo_e_campo(
    data_dir_copia: Path, arquivo: str, mudar: Callable[[Json], None], trecho: str
) -> None:
    _editar(data_dir_copia, arquivo, mudar)

    with pytest.raises(GameDataError) as erro:
        load_game_data(data_dir_copia)

    assert any(trecho in mensagem for mensagem in erro.value.erros), erro.value.erros


def test_acusa_json_malformado_com_linha(data_dir_copia: Path) -> None:
    (data_dir_copia / "characters.json").write_text('{\n  "x": ,\n}', encoding="utf-8")

    with pytest.raises(GameDataError, match=r"characters.json: JSON inválido \(linha 2"):
        load_game_data(data_dir_copia)
