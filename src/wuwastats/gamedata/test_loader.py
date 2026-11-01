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
    assert perfil.base.estrelas["basic_atk_dmg"] == 2
    assert perfil.base.pesos["basic_atk_dmg"] == pytest.approx(2 / 3)


def test_arma_assinatura_do_catalogo_vale_por_todos_os_nomes_dela(data_dir_copia: Path) -> None:
    _editar(data_dir_copia, "characters.json", _suoming("armas_assinatura", ["Test Weapon"]))

    assinatura = load_game_data(data_dir_copia).perfis["Suoming_DPS"].armas_assinatura

    assert {"test weapon", "arma teste"} <= assinatura


def test_resolve_armas_do_perfil_em_qualquer_idioma_para_a_chave_em_ingles(data_dir_copia: Path) -> None:
    armas = load_game_data(data_dir_copia).perfis["Suoming_DPS"].armas

    assert armas is not None
    assert (armas.melhor, armas.alternativas) == ("Test Weapon", ("Alt Weapon",))


def test_carrega_metas_da_build(data_dir_copia: Path) -> None:
    base = load_game_data(data_dir_copia).perfis["Suoming_DPS"].base

    meta_crit = base.meta_de("crit_rate")
    assert meta_crit is not None
    assert (meta_crit.min, meta_crit.max, meta_crit.fonte) == (60, 80, "prydwen")
    assert base.meta_de("crit_dmg") is None


def test_variante_herda_ou_substitui_metas(data_dir_copia: Path) -> None:
    _editar(data_dir_copia, "characters.json", lambda c: c["Suoming_DPS"]["variantes"][1].__setitem__("metas", []))

    perfil = load_game_data(data_dir_copia).perfis["Suoming_DPS"]

    assert perfil.variantes[0].spec.metas == perfil.base.metas
    assert len(perfil.base.metas) == 2
    assert perfil.variantes[1].spec.metas == ()


def _editar(data_dir: Path, arquivo: str, mudar: Callable[[Json], None]) -> None:
    caminho = data_dir / arquivo
    conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    mudar(conteudo)
    caminho.write_text(json.dumps(conteudo, ensure_ascii=False), encoding="utf-8")


def _suoming(campo: str, valor: object) -> Callable[[Json], None]:
    return lambda conteudo: conteudo["Suoming_DPS"].__setitem__(campo, valor)


def _variante(campo: str, valor: object) -> Callable[[Json], None]:
    return lambda conteudo: conteudo["Suoming_DPS"]["variantes"][0].__setitem__(campo, valor)


_META_CRIT: Json = {"stat": "crit_rate", "min": 60, "tipo": "rotacao", "fonte": "game8"}


@pytest.mark.parametrize(
    ("arquivo", "mudar", "trecho"),
    [
        ("characters.json", _suoming("estrelas", {"ATQ": 3}), "estrelas › ATQ: status 'ATQ' desconhecido ou ambíguo"),
        ("characters.json", _suoming("estrelas", {"Taxa CRIT": 4}), "estrelas › Taxa CRIT"),
        ("characters.json", _suoming("principais", {"1": ["Dano CRIT"]}), "principal de echo custo 1"),
        ("characters.json", _suoming("custos", [4, 4, 4, 1, 1]), "custo total 14"),
        ("characters.json", _suoming("custos", [4, 3, 3, 1]), "custos"),
        ("characters.json", _suoming("sets", {"Set Inexistente": 5}), "sets › Set Inexistente: 'Set Inexistente' não está"),
        ("characters.json", _suoming("sets", {"Moonlit Clouds": 3, "Heart of Sworn Vigil": 3}), "pedem 6 peças"),
        ("characters.json", _variante("sets", {"Moonlit Clouds": 5, "Heart of Sworn Vigil": 1}), "pedem 6 peças"),
        ("characters.json", _suoming("regen_energia_min", 110), "regen_energia_min: Extra inputs are not permitted"),
        ("characters.json", _suoming("metas", [_META_CRIT, _META_CRIT]), "metas: Value error, meta de crit_rate repetida"),
        ("characters.json", _suoming("metas", [_META_CRIT | {"max": 50}]), "metas › 0: Value error, max menor que min"),
        ("characters.json", _variante("metas", [_META_CRIT, _META_CRIT]), "variantes › 0 › metas: Value error"),
        ("characters.json", _variante("condicao", {"sequencia": 2}), "sequencia"),
        ("characters.json", _variante("condicao", {}), "condição vazia"),
        ("characters.json", _variante("echo_principal", "Ninguém"), "variantes › 0 › echo_principal"),
        ("substats.json", lambda c: c["substatus"]["crit_rate"].__setitem__("valores", [7.5, 6.3]), "ordem crescente"),
        ("main_stats.json", lambda c: c["custos"].pop("3"), "faltam os custos"),
        ("stat_aliases.json", lambda c: c["sets"].__setitem__("Set Fantasma", []), "Set Fantasma: não existe"),
        ("stat_aliases.json", lambda c: c["stats"]["crit_rate"].append("Dano CRIT"), "'dano crit' aponta para"),
        ("sets.json", lambda c: c["sets"]["Moonlit Clouds"]["bonus"]["2"].__setitem__("Sorte", 1), "Sorte"),
        ("notas.json", lambda c: c["faixas"].reverse(), "ordem decrescente"),
        ("characters.json", _suoming("personagem", "Ninguém"), "personagem: 'Ninguém' não está"),
        ("characters.json", _suoming("armas", {"melhor": "Arma Fantasma"}), "armas › melhor: 'Arma Fantasma'"),
        ("characters.json", _suoming("armas", {"alternativas": ["Arma Fantasma"]}), "armas › alternativas: 'Arma Fantasma'"),
        ("resonators.json", lambda c: c["ressonadores"]["Suoming"].__setitem__("elemento", "agua"), "'agua' não existe"),
        ("weapons.json", lambda c: c["armas"]["Test Weapon"].__setitem__("tipo", "lanca"), "'lanca' não existe"),
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
