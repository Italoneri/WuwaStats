import dataclasses
import io
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from importar_dados_jogo import (
    ArmaFonte,
    ArmaImportada,
    ArquivoAusente,
    Catalogo,
    Categoria,
    Commit,
    EchoFonte,
    EchoImportado,
    EfeitoSetFonte,
    ElementoFonte,
    Elenco,
    FonteIndisponivel,
    GrupoSetFonte,
    HabilidadeFonte,
    PersonagemFonte,
    PropriedadeFonte,
    RaridadeFonte,
    RessonadorImportado,
    TabelasFonte,
    Traducao,
    gerar_echoes,
    gerar_sets,
    gravar_validado,
    importar_icones,
    limpar_marcacao,
    mesclar_aliases,
    montar_catalogo,
    montar_elenco,
    preencher,
    url_do_icone,
)
from PIL import Image

from wuwastats.config import PROJECT_ROOT
from wuwastats.domain.names import NameIndex
from wuwastats.domain.tables import Traducao as TraducaoCarregada
from wuwastats.gamedata.imagens import ImagensDoCatalogo
from wuwastats.gamedata.loader import GameDataError, load_game_data
from wuwastats.gamedata.schemas import AliasesFile, EchoesFile, SetsFile

GAMEDATA_FIXTURE = PROJECT_ROOT / "fixtures" / "gamedata"
COMMIT = Commit(ref="3.7", sha="abc1234567890", data="2026-09-29T20:35:07Z", mensagem="GameVer 3.7.0")
STATS = NameIndex.build({"energy_regen": ["Energy Regen"], "atk_pct": ["ATK"], "atk_flat": ["ATK"]})


def _tabelas(textos_pt: dict[str, str] | None) -> TabelasFonte:
    def echo(nome: str, raridade: int, grupos: list[int], tipo: int = 1) -> EchoFonte:
        return EchoFonte.model_validate({"MonsterName": nome, "Rarity": raridade, "FetterGroup": grupos, "PhantomType": tipo})

    return TabelasFonte(
        echos=[
            echo("M_Nuvem", 0, [8]),
            echo("M_Nuvem", 0, [8]),
            echo("M_Gulpuff", 0, [8]),
            echo("M_Gulpuff", 0, [8]),
            echo("M_Gulpuff", 2, [9], tipo=2),
        ],
        raridades=[RaridadeFonte.model_validate({"Rare": r, "Cost": c}) for r, c in [(0, 1), (1, 3), (2, 4)]],
        grupos_set=[
            _grupo(8, {2: 15, 5: 16}),
            _grupo(9, {2: 17}),
        ],
        efeitos_set=[
            _efeito(15, ["10%"], [{"Id": 11, "Value": 1000, "IsRatio": False}]),
            _efeito(16, ["22.5%", "15"], []),
            _efeito(17, ["10%"], [{"Id": 10007, "Value": 0.10000000149011612, "IsRatio": True}]),
        ],
        propriedades=[
            PropriedadeFonte.model_validate({"Id": 11, "Name": "P_11", "IsPercent": True}),
            PropriedadeFonte.model_validate({"Id": 10007, "Name": "P_10007", "IsPercent": False}),
        ],
        textos_en={
            "M_Nuvem": "Cloudy",
            "M_Gulpuff": "Gulpuff",
            "F_8": "Moonlit Clouds",
            "F_9": "Lingering Tunes",
            "D_15": "Energy Regen + {0}",
            "D_16": "ATK +{0} for {1}s.",
            "D_17": "ATK +{0}",
            "P_11": "Energy Regen",
            "P_10007": "ATK",
        },
        textos_pt=textos_pt,
    )


def _grupo(id_: int, efeito_por_pecas: dict[int, int]) -> GrupoSetFonte:
    mapa = [{"Key": pecas, "Value": efeito} for pecas, efeito in efeito_por_pecas.items()]
    return GrupoSetFonte.model_validate({"Id": id_, "FetterGroupName": f"F_{id_}", "FetterMap": mapa})


def _efeito(id_: int, parametros: list[str], propriedades: list[dict[str, Any]]) -> EfeitoSetFonte:
    return EfeitoSetFonte.model_validate(
        {"Id": id_, "EffectDescription": f"D_{id_}", "EffectDescriptionParam": parametros, "AddProp": propriedades}
    )


TEXTOS_PT = {"M_Nuvem": "Nublado", "M_Gulpuff": "Baiagul", "F_8": "Nuvens Enluaradas", "D_16": "ATQ +{0} por {1}s."}


def test_monta_sets_com_bonus_em_status_e_descricoes_preenchidas() -> None:
    catalogo = montar_catalogo(_tabelas(TEXTOS_PT), STATS)

    nuvens = catalogo.sets["Moonlit Clouds"]
    assert nuvens.nome_pt == "Nuvens Enluaradas"
    assert nuvens.pecas == 5
    assert nuvens.bonus == {2: {"energy_regen": 10.0}}
    assert nuvens.efeitos[5] == ("ATK +22.5% for 15s.", "ATQ +22.5% por 15s.")
    assert catalogo.sets["Lingering Tunes"].bonus == {2: {"atk_pct": 10.0}}


def test_agrupa_variantes_do_echo_pelo_nome_em_ingles() -> None:
    catalogo = montar_catalogo(_tabelas(TEXTOS_PT), STATS)

    assert catalogo.echoes["Cloudy"] == EchoImportado(nome_pt="Nublado", custos=frozenset({1}), sets=("Moonlit Clouds",))


def test_ignora_linha_especial_que_reaproveita_nome_de_echo_normal() -> None:
    catalogo = montar_catalogo(_tabelas(TEXTOS_PT), STATS)

    assert catalogo.echoes["Gulpuff"] == EchoImportado(nome_pt="Baiagul", custos=frozenset({1}), sets=("Moonlit Clouds",))
    assert "1 linhas de echo com PhantomType 2 ignoradas" in catalogo.avisos


def _com_habilidade(niveis: list[list[str]]) -> TabelasFonte:
    base = _tabelas(TEXTOS_PT)
    nuvem = base.echos[0].model_copy(update={"habilidade": 7})
    habilidade = HabilidadeFonte.model_validate(
        {
            "PhantomSkillId": 7,
            "DescriptionEx": "H_7",
            "SimplyDescription": "R_7",
            "LevelDescStrArray": [{"ArrayString": nivel} for nivel in niveis],
        }
    )
    textos_en = {**base.textos_en, "H_7": "Deal {0} <color=Highlight>Aero DMG</color>.\n \n\n\nCD: {1}s", "R_7": "Deal Aero DMG."}
    textos_pt = {**TEXTOS_PT, "H_7": "Causa {0} de dano aero.\n\nRecarga: {1} s"}
    return dataclasses.replace(base, echos=[nuvem], habilidades=[habilidade], textos_en=textos_en, textos_pt=textos_pt)


def test_habilidade_do_echo_usa_o_nivel_mais_alto_sem_a_marcacao_do_jogo() -> None:
    catalogo = montar_catalogo(_com_habilidade([["10%", "8"], ["20%", "8"]]), STATS)

    assert catalogo.echoes["Cloudy"].habilidade == ("Deal 20% Aero DMG.\n\nCD: 8s", "Causa 20% de dano aero.\n\nRecarga: 8 s")


def test_habilidade_sem_niveis_usa_o_resumo_e_echo_sem_habilidade_vira_aviso() -> None:
    assert montar_catalogo(_com_habilidade([]), STATS).echoes["Cloudy"].habilidade == ("Deal Aero DMG.", None)
    assert "echo Gulpuff: a fonte não tem a descrição da habilidade" in montar_catalogo(_tabelas(None), STATS).avisos


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("<size=40><color=Title>Core</color></size>\nHit", "Core\nHit"),
        ("Below <50% HP, <SapTag=1>heal</SapTag>", "Below <50% HP, heal"),
        ("a \n \n\n\nb ", "a\n\nb"),
    ],
)
def test_limpa_marcacao_e_linhas_em_branco_repetidas(texto: str, esperado: str) -> None:
    assert limpar_marcacao(texto) == esperado


def test_sem_textmap_pt_os_nomes_pt_ficam_vazios() -> None:
    catalogo = montar_catalogo(_tabelas(None), STATS)

    assert {echo.nome_pt for echo in catalogo.echoes.values()} == {None}
    assert catalogo.sets["Moonlit Clouds"].efeitos[2] == ("Energy Regen + 10%", None)


def _elenco_fonte() -> TabelasFonte:
    def personagem(nome: str, tipo: int = 1, teste: bool = False, raridade: int = 5, corpo: str = "") -> PersonagemFonte:
        campos = {"Name": nome, "QualityId": raridade, "ElementId": 3, "WeaponType": 2, "RoleType": tipo, "IsTrial": teste}
        retrato = f"/Game/Aki/UI/P/{nome}{corpo}.x"
        return PersonagemFonte.model_validate({**campos, "RoleBody": corpo, "FormationRoleCard": retrato})

    textos_en = {"R_Suo": "Suoming", "R_Rover": "Rover: Electro", "E_3": "Electro", "W_1": "Unspoken Rue"}
    textos_en["RoleProject_WeaponType02"] = "Weapon Type: Sword"
    textos_pt = {"R_Suo": "Suoming", "E_3": "Voltaico", "W_1": "Penumbra Abissal"}
    textos_pt["RoleProject_WeaponType02"] = "Tipo de Armas: Espada"
    return dataclasses.replace(
        _tabelas(None),
        textos_en=textos_en,
        textos_pt=textos_pt,
        personagens=[
            personagem("R_Suo"),
            personagem("R_Suo", tipo=2, teste=True, raridade=4),
            personagem("R_Rover", corpo="MaleM"),
            personagem("R_Rover", corpo="FemaleM"),
        ],
        elementos=[ElementoFonte.model_validate({"Id": 3, "Name": "E_3"})],
        armas=[ArmaFonte.model_validate({"WeaponName": "W_1", "QualityId": 5, "WeaponType": 2})],
    )


def test_monta_ressonadores_jogaveis_sem_versoes_de_teste_nem_rover_repetido() -> None:
    elenco = montar_elenco(_elenco_fonte())

    assert elenco.ressonadores == {
        "Rover: Electro": RessonadorImportado(nome_pt=None, elemento="electro", tipo_arma="sword", raridade=5),
        "Suoming": RessonadorImportado(nome_pt="Suoming", elemento="electro", tipo_arma="sword", raridade=5),
    }
    assert elenco.avisos == []


def test_retrato_do_ressonador_vem_da_fonte_e_rover_usa_o_corpo_preferido() -> None:
    elenco = montar_elenco(_elenco_fonte())

    assert elenco.ressonadores["Suoming"].retrato == "/Game/Aki/UI/P/R_Suo.x"
    assert elenco.ressonadores["Rover: Electro"].retrato == "/Game/Aki/UI/P/R_RoverFemaleM.x"


def test_monta_elementos_tipos_de_arma_e_armas_com_nome_pt() -> None:
    elenco = montar_elenco(_elenco_fonte())

    assert elenco.elementos == {"electro": Traducao(en="Electro", pt="Voltaico")}
    assert elenco.tipos_arma == {"sword": Traducao(en="Sword", pt="Espada")}
    assert elenco.armas == {"Unspoken Rue": ArmaImportada(nome_pt="Penumbra Abissal", tipo="sword", raridade=5)}


@pytest.mark.parametrize(
    ("custo_anterior", "custo", "status"),
    [
        (None, None, "TODO: a fonte lista custos [1, 4] para variantes deste echo; escolha um"),
        (4, 4, "custo escolhido à mão; a fonte lista [1, 4]"),
        (3, None, "TODO: a fonte lista custos [1, 4] para variantes deste echo; escolha um"),
    ],
)
def test_custo_ambiguo_so_mantem_escolha_manual_valida(custo_anterior: int | None, custo: int | None, status: str) -> None:
    atual = EchoesFile.model_validate({"_meta": {}, "echoes": {"Gulpuff": {"custo": custo_anterior}}})
    novos = {"Gulpuff": EchoImportado(nome_pt="Baiagul", custos=frozenset({1, 4}), sets=())}

    gerado, _ = gerar_echoes(novos, atual, COMMIT)

    assert gerado["echoes"]["Gulpuff"]["custo"] == custo
    assert gerado["echoes"]["Gulpuff"]["status"] == status


def test_mantem_entradas_que_sumiram_da_fonte_marcadas_como_todo() -> None:
    atual = EchoesFile.model_validate({"_meta": {"extra": 1}, "echoes": {"Suhsin": {"custo": None}}})

    gerado, avisos = gerar_echoes({}, atual, COMMIT)

    assert gerado["_meta"]["extra"] == 1
    assert gerado["echoes"]["Suhsin"]["status"].startswith("TODO: não encontrado em Arikatsu/WutheringWaves_Data@abc1234567")
    assert avisos == ["echo 'Suhsin' não existe na fonte; mantido com status TODO"]


def test_aliases_acrescenta_nomes_pt_sem_apagar_manuais_nem_criar_ambiguidade() -> None:
    aliases = AliasesFile.model_validate(
        {
            "_meta": {},
            "stats": {"crit_rate": ["Taxa CRIT"]},
            "echoes": {"Cloudy": ["Nuvenzinha"], "Gulpuff": ["Baiagul"]},
            "sets": {},
        }
    )
    nomes_pt: dict[Categoria, dict[str, str | None]] = {
        "echoes": {"Cloudy": "Nublado", "Gulpuff": "Baiagul", "Jue": "Gulpuff", "Sem PT": None},
        "sets": {"Moonlit Clouds": "Nuvens Enluaradas"},
    }

    resultado, avisos = mesclar_aliases(aliases, nomes_pt)

    assert resultado["stats"] == {"crit_rate": ["Taxa CRIT"]}
    assert resultado["echoes"] == {"Cloudy": ["Nuvenzinha", "Nublado"], "Gulpuff": ["Baiagul"]}
    assert resultado["sets"] == {"Moonlit Clouds": ["Nuvens Enluaradas"]}
    assert avisos == ["alias echoes 'Gulpuff' → Jue pulado: já aponta para ['Gulpuff']"]


@pytest.mark.parametrize(
    ("modelo", "parametros", "esperado"),
    [
        ("Glacio DMG + {0}", ["10%"], "Glacio DMG + 10%"),
        ("{1} por {0}s", ["5", "Cura"], "Cura por 5s"),
        ("sobra {2}", ["a"], "sobra {2}"),
    ],
)
def test_preenche_parametros_da_descricao(modelo: str, parametros: list[str], esperado: str) -> None:
    assert preencher(modelo, parametros) == esperado


def test_grava_so_depois_de_validar_o_conjunto(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    shutil.copytree(GAMEDATA_FIXTURE, data_dir)
    habilidade = ("Deal 20% Aero DMG.", "Causa 20% de dano aero.")
    novos = {"Suhsin": EchoImportado(nome_pt="Suhsin PT", custos=frozenset({4}), sets=("Moonlit Clouds",), habilidade=habilidade)}
    echoes, _ = gerar_echoes(novos, _ler(data_dir, "echoes.json", EchoesFile), COMMIT)

    gravar_validado(data_dir, {"echoes.json": echoes})

    suhsin = load_game_data(data_dir).echoes["Suhsin"]
    assert suhsin.custo == 4
    assert suhsin.habilidade == TraducaoCarregada(en="Deal 20% Aero DMG.", pt="Causa 20% de dano aero.")
    assert _json(data_dir / "echoes.json")["echoes"]["Suhsin"]["nome_pt"] == "Suhsin PT"


def test_nao_toca_em_data_quando_o_resultado_nao_carrega(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    shutil.copytree(GAMEDATA_FIXTURE, data_dir)
    antes = (data_dir / "sets.json").read_bytes()
    sets, _ = gerar_sets({}, _ler(data_dir, "sets.json", SetsFile), COMMIT)
    sets["sets"]["Moonlit Clouds"]["bonus"] = {"2": {"stat_inexistente": 1.0}}

    with pytest.raises(GameDataError):
        gravar_validado(data_dir, {"sets.json": sets})

    assert (data_dir / "sets.json").read_bytes() == antes


@pytest.mark.parametrize(
    ("caminho", "esperado"),
    [
        (
            "/Game/Aki/UI/UIResources/Common/Image/IconMonsterGoods/T_IconMonsterGoods_011_UI.T_IconMonsterGoods_011_UI",
            "https://static.nanoka.cc/assets/ww/UIResources/Common/Image/IconMonsterGoods/T_IconMonsterGoods_011_UI.webp",
        ),
        ("/Game/Aki/Outra/T_X.T_X", None),
        ("", None),
    ],
)
def test_converte_caminho_de_textura_em_url_do_icone(caminho: str, esperado: str | None) -> None:
    assert url_do_icone(caminho) == esperado


def test_echo_set_e_arma_levam_o_icone_da_fonte() -> None:
    com_echos, com_armas = _tabelas(None), _elenco_fonte()
    echos = [echo.model_copy(update={"icone": f"/Game/Aki/UI/E/{echo.chave_nome}.x"}) for echo in com_echos.echos]
    grupos = [grupo.model_copy(update={"icone": f"/Game/Aki/UI/S/{grupo.id}.x"}) for grupo in com_echos.grupos_set]
    armas = [arma.model_copy(update={"icone": "/Game/Aki/UI/W/W_1.x"}) for arma in com_armas.armas]

    catalogo = montar_catalogo(dataclasses.replace(com_echos, echos=echos, grupos_set=grupos), STATS)
    elenco = montar_elenco(dataclasses.replace(com_armas, armas=armas))

    assert catalogo.echoes["Cloudy"].icone == "/Game/Aki/UI/E/M_Nuvem.x"
    assert catalogo.sets["Moonlit Clouds"].icone == "/Game/Aki/UI/S/8.x"
    assert elenco.armas["Unspoken Rue"].icone == "/Game/Aki/UI/W/W_1.x"


def test_baixa_so_icones_que_faltam_e_falha_vira_aviso(tmp_path: Path) -> None:
    imagens = ImagensDoCatalogo(tmp_path)
    imagens.salvar("echoes", "Cloudy", _webp("red"))
    enviada_a_mao = imagens.caminho("echoes", "Cloudy").read_bytes()
    catalogo = Catalogo(
        echoes={
            "Cloudy": EchoImportado(nome_pt=None, custos=frozenset({1}), sets=(), icone="/Game/Aki/UI/E/Cloudy.x"),
            "Gulpuff": EchoImportado(nome_pt=None, custos=frozenset({1}), sets=(), icone="/Game/Aki/UI/E/Gulpuff.x"),
            "Sem Icone": EchoImportado(nome_pt=None, custos=frozenset({1}), sets=()),
        },
        sets={},
    )
    elenco = Elenco(
        elementos={},
        tipos_arma={},
        ressonadores={
            "Suoming": RessonadorImportado(
                nome_pt=None, elemento="electro", tipo_arma="sword", raridade=5, retrato="/Game/Aki/UI/P/T_Pile_suoming_UI.x"
            )
        },
        armas={"Unspoken Rue": ArmaImportada(nome_pt=None, tipo="sword", raridade=5, icone="/Game/Aki/UI/W/Rue.x")},
    )
    pedidas: list[str] = []

    def baixar(url: str) -> bytes:
        pedidas.append(url)
        if url.endswith("Rue.webp"):
            raise FonteIndisponivel(f"{url}: HTTP 503")
        if url.endswith("suoming_UI.webp"):
            raise ArquivoAusente(f"{url}: 404")
        return _webp("blue")

    avisos = importar_icones(imagens, catalogo, elenco, baixar)

    assert sorted(pedidas) == [
        "https://static.nanoka.cc/assets/ww/E/Gulpuff.webp",
        "https://static.nanoka.cc/assets/ww/P/T_Pile_Suoming_UI.webp",
        "https://static.nanoka.cc/assets/ww/P/T_Pile_suoming_UI.webp",
        "https://static.nanoka.cc/assets/ww/W/Rue.webp",
    ]
    assert imagens.caminho("echoes", "Cloudy").read_bytes() == enviada_a_mao
    assert imagens.existe("echoes", "Gulpuff")
    assert imagens.existe("personagens", "Suoming")
    assert not imagens.existe("armas", "Unspoken Rue")
    assert avisos == [
        "ícone echoes 'Sem Icone': caminho '' fora de /Game/Aki/UI/; envie à mão",
        "ícone armas 'Unspoken Rue': https://static.nanoka.cc/assets/ww/W/Rue.webp: HTTP 503",
    ]


def _webp(cor: str) -> bytes:
    saida = io.BytesIO()
    Image.new("RGB", (4, 4), cor).save(saida, format="WEBP")
    return saida.getvalue()


def _ler[T: EchoesFile | SetsFile](data_dir: Path, nome: str, modelo: type[T]) -> T:
    return modelo.model_validate_json((data_dir / nome).read_text(encoding="utf-8"))


def _json(caminho: Path) -> Any:
    return json.loads(caminho.read_text(encoding="utf-8"))
