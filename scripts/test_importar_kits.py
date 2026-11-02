import dataclasses
import json

import pytest
from importar_dados_jogo import FonteIndisponivel
from importar_kits import (
    HabilidadeKitFonte,
    ImagemKit,
    MultiplicadorFonte,
    NoFonte,
    PersonagemKitFonte,
    SequenciaFonte,
    TabelasKit,
    TagFonte,
    TipoFonte,
    baixar_imagens,
    caminhos_do_forte,
    montar_kit,
)

from wuwastats.gamedata.kits import Bonus, ImagensDoKit

ICONE = "/Game/Aki/UI/UIResources/Common/Atlas/SkillIcon/SP_{}.SP_{}"
FORTE = ["/Game/Aki/UI/UIResources/UiRole/Image/T_RoleSkillTreeYangyang.T_RoleSkillTreeYangyang"]
VINTE = [f"{n}%" for n in range(1, 21)]

PERSONAGEM = PersonagemKitFonte.model_validate(
    {
        "Id": 1402,
        "Name": "nome",
        "RoleType": 1,
        "IsTrial": False,
        "Tag": [3],
        "SkillTreeGroupId": 1402,
        "ResonantChainGroupId": 1402,
    }
)


def _no(indice: int, tipo_no: int, habilidade: int = 0, titulo: str = "", param: list[str] | None = None) -> NoFonte:
    return NoFonte.model_validate(
        {
            "NodeIndex": indice,
            "NodeGroup": 1402,
            "NodeType": tipo_no,
            "SkillId": habilidade,
            "PropertyNodeTitle": titulo,
            "PropertyNodeParam": param or [],
        }
    )


def _habilidade(id_: int, tipo: int, detalhe: list[str] | None = None) -> HabilidadeKitFonte:
    return HabilidadeKitFonte.model_validate(
        {
            "Id": id_,
            "SkillType": tipo,
            "SkillName": f"h{id_}n",
            "SkillDescribe": f"h{id_}d",
            "SkillDetailNum": detalhe or [],
            "Icon": ICONE.format(id_, id_),
            "SkillLevelGroupId": id_,
        }
    )


def _multiplicador(grupo: int, nome: str, ordem: int, descricao: str = "") -> MultiplicadorFonte:
    return MultiplicadorFonte.model_validate(
        {
            "SkillLevelGroupId": grupo,
            "AttributeName": nome,
            "Description": descricao,
            "Order": ordem,
            "SkillDetailNum": [{"ArrayString": VINTE}],
        }
    )


TEXTOS = {
    "T1": "ATQ Normal",
    "T6": "Circuito Ressonante",
    "T4": "Habilidade Inerente",
    "h1n": "Plumilâmina",
    "h1d": "Ataca.",
    "h6n": "Penas Ecoicas",
    "h6d": "Com {0} Melodias.",
    "h4n": "Compaixão",
    "h4d": "Recupera {0} de VIG.",
    "m1": "Dano",
    "m2": "Tempo de recarga",
    "m2d": "{0}s",
    "p": "ATQ+",
    "c1n": "Céus Safirinos, \nPardais Altíssimos",
    "c1d": "Aumenta {0}.",
    "tg": "Eficiência de Concerto",
    "tgd": "Regenera rápido",
}

TABELAS = TabelasKit(
    personagens=[PERSONAGEM],
    nos=[
        _no(7, 1, 6),
        _no(1, 2, 1),
        _no(4, 3, 4),
        _no(9, 4, titulo="p", param=["1.80%"]),
        _no(10, 4, titulo="p", param=["4.20%"]),
    ],
    habilidades=[_habilidade(6, 6, ["3"]), _habilidade(1, 1), _habilidade(4, 4, ["30"])],
    multiplicadores=[_multiplicador(1, "m2", 2, "m2d"), _multiplicador(1, "m1", 1)],
    sequencias=[
        SequenciaFonte.model_validate(
            {
                "GroupId": 1402,
                "GroupIndex": 1,
                "NodeName": "c1n",
                "AttributesDescription": "c1d",
                "AttributesDescriptionParams": ["15%"],
                "NodeIcon": ICONE.format("c", "c"),
            }
        )
    ],
    tags=[TagFonte.model_validate({"Id": 3, "TagName": "tg", "TagDesc": "tgd", "TagNameColor": "ff4040"})],
    tipos=[TipoFonte.model_validate({"Id": n, "TypeName": f"T{n}"}) for n in (1, 4, 6)],
    textos_pt=TEXTOS,
    textos_en=TEXTOS,
)


def test_ordena_habilidades_na_ordem_oficial() -> None:
    kit, _, _ = montar_kit(TABELAS, PERSONAGEM, FORTE)

    assert [h.tipo for h in kit.habilidades] == ["ATQ Normal", "Circuito Ressonante"]
    assert [h.tipo for h in kit.inerentes] == ["Habilidade Inerente"]


def test_multiplicadores_tem_dez_niveis_e_formato() -> None:
    kit, _, _ = montar_kit(TABELAS, PERSONAGEM, FORTE)

    dano, recarga = kit.habilidades[0].multiplicadores
    assert (dano.nome, dano.valores) == ("Dano", VINTE[:10])
    assert (recarga.nome, recarga.valores[0]) == ("Tempo de recarga", "1%s")


def test_inerente_sem_multiplicadores() -> None:
    kit, _, _ = montar_kit(TABELAS, PERSONAGEM, FORTE)

    assert kit.inerentes[0].multiplicadores == []
    assert kit.inerentes[0].descricao[0][0].texto == "Recupera 30 de VIG."


def test_soma_bonus_da_arvore() -> None:
    kit, _, _ = montar_kit(TABELAS, PERSONAGEM, FORTE)

    assert kit.bonus == [Bonus(nome="ATQ", valor="6%")]


def test_sequencia_com_nome_em_uma_linha_e_tags() -> None:
    kit, _, _ = montar_kit(TABELAS, PERSONAGEM, FORTE)

    assert (kit.sequencias[0].numero, kit.sequencias[0].nome) == (1, "Céus Safirinos, Pardais Altíssimos")
    assert kit.sequencias[0].descricao[0][0].texto == "Aumenta 15%."
    assert [(t.nome, t.cor) for t in kit.tags] == [("Eficiência de Concerto", "ff4040")]


def test_texto_sem_pt_usa_ingles_e_avisa() -> None:
    pt = {k: v for k, v in TEXTOS.items() if k != "h1d"}
    tabelas = dataclasses.replace(TABELAS, textos_pt=pt, textos_en={**TEXTOS, "h1d": "Attacks."})

    kit, _, avisos = montar_kit(tabelas, PERSONAGEM, FORTE)

    assert kit.habilidades[0].descricao[0][0].texto == "Attacks."
    assert any("sem PT" in aviso for aviso in avisos)


def test_ilustracao_so_no_circuito() -> None:
    kit, imagens, _ = montar_kit(TABELAS, PERSONAGEM, FORTE)

    assert kit.habilidades[1].ilustracoes == ["forte-1"]
    assert kit.habilidades[0].ilustracoes == []
    assert (
        ImagemKit("forte-1", "https://static.nanoka.cc/assets/ww/UIResources/UiRole/Image/T_RoleSkillTreeYangyang.webp")
        in imagens
    )
    assert kit.habilidades[0].imagem == "habilidade-1"


FORTE_ANTIGO = {"forte": {"icon": "/Game/Aki/UI/A/T_Antigo.T_Antigo"}, "forte_new": {}}
FORTE_NOVO = {
    "forte": {"icon": ""},
    "forte_new": {
        "instructions": {
            "1": {
                "desc": {
                    "11": {"image_list": ["/Game/Aki/UI/A/T_Um.T_Um"]},
                    "12": {"image_list": ["/Game/Aki/UI/A/T_Dois.T_Dois"]},
                }
            },
            "2": {"desc": {"21": {"image_list": ["/Game/Aki/UI/A/T_Um.T_Um", "/Game/Aki/UI/A/T_Tres.T_Tres"]}}},
        }
    },
}


@pytest.mark.parametrize(
    ("dados", "esperado"),
    [
        (FORTE_ANTIGO, ["/Game/Aki/UI/A/T_Antigo.T_Antigo"]),
        (FORTE_NOVO, ["/Game/Aki/UI/A/T_Um.T_Um", "/Game/Aki/UI/A/T_Dois.T_Dois", "/Game/Aki/UI/A/T_Tres.T_Tres"]),
    ],
    ids=["icone_unico", "instrucoes_sem_repetir"],
)
def test_caminhos_do_forte(dados: dict[str, object], esperado: list[str]) -> None:
    assert caminhos_do_forte(1402, "3.8.1", baixar=lambda _url: json.dumps(dados).encode()) == (esperado, None)


def test_forte_indisponivel_vira_aviso() -> None:
    def baixar(_url: str) -> bytes:
        raise FonteIndisponivel("HTTP 503")

    caminhos, aviso = caminhos_do_forte(1402, "3.8.1", baixar=baixar)

    assert caminhos == []
    assert aviso is not None


def test_falha_de_imagem_vira_aviso(tmp_path) -> None:
    def baixar(_url: str) -> bytes:
        raise FonteIndisponivel("HTTP 503")

    avisos = baixar_imagens(ImagensDoKit(tmp_path), "Yangyang", [ImagemKit("forte", "https://x/forte.webp")], baixar=baixar)

    assert len(avisos) == 1
    assert "forte" in avisos[0]


def test_bonus_com_valor_invalido_vira_aviso() -> None:
    nos = [*TABELAS.nos, _no(11, 4, titulo="p", param=["muito"])]

    kit, _, avisos = montar_kit(dataclasses.replace(TABELAS, nos=nos), PERSONAGEM, FORTE)

    assert kit.bonus == [Bonus(nome="ATQ", valor="6%")]
    assert any("muito" in aviso for aviso in avisos)
