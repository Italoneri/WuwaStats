import pytest

from wuwastats.gamedata.kit_texto import Paragrafo, Trecho, converter_texto

T = Trecho

CASOS: list[tuple[str, str, list[str], list[Paragrafo]]] = [
    (
        "subtitulo_e_elemento",
        "<size=40><color=Title>ATQ Básico</color></size>\nCausa <color=Wind>Dano Pneumático</color>.",
        [],
        [
            [T(texto="ATQ Básico", estilo="subtitulo")],
            [T(texto="Causa ", estilo="normal"), T(texto="Dano Pneumático", estilo="aero"), T(texto=".", estilo="normal")],
        ],
    ),
    ("parametros", "Recupera {0} de VIG por {1}s.", ["30", "8"], [[T(texto="Recupera 30 de VIG por 8s.", estilo="normal")]]),
    ("parametro_sem_valor", "Ganha {2}.", ["1"], [[T(texto="Ganha {2}.", estilo="normal")]]),
    (
        "glossario_vira_destaque",
        "Aplica <color=Highlight><te href=850012>Ruína</te></color>.",
        [],
        [[T(texto="Aplica ", estilo="normal"), T(texto="Ruína", estilo="destaque"), T(texto=".", estilo="normal")]],
    ),
    ("entrada_pc", "{Cus:Ipt,Touch=Toque PC=Pressione Gamepad=Pressione} ATQ", [], [[T(texto="Pressione ATQ", estilo="normal")]]),
    ("espacador_separa", "A\n<size=10> </size>\nB", [], [[T(texto="A", estilo="normal")], [T(texto="B", estilo="normal")]]),
    (
        "plural_pela_quantidade",
        "inflige <SapTag=2>{0}</SapTag> {Cus:Sap,S=acúmulo P=acúmulos SapTag=2} de Dano",
        ["3"],
        [[T(texto="inflige 3 acúmulos de Dano", estilo="normal")]],
    ),
    (
        "singular_pela_quantidade",
        "inflige <SapTag=5>{0}</SapTag> {Cus:Sap,S=acúmulo P=acúmulos SapTag=5} de Dano",
        ["1"],
        [[T(texto="inflige 1 acúmulo de Dano", estilo="normal")]],
    ),
    (
        "marcador_com_letra",
        "restaura <SapTag=C>{0}</SapTag> {Cus:Sap,S=ponto P=pontos SapTag=C} de Traço",
        ["100"],
        [[T(texto="restaura 100 pontos de Traço", estilo="normal")]],
    ),
    (
        "plural_dentro_de_glossario",
        "consome <SapTag=6>{0}</SapTag> <te href=850017>{Cus:Sap,S=Cristal P=Cristais SapTag=6}</te>.",
        ["2"],
        [[T(texto="consome 2 ", estilo="normal"), T(texto="Cristais", estilo="destaque"), T(texto=".", estilo="normal")]],
    ),
    (
        "marcador_sem_plural_some",
        "obtém <SapTag=0>{0}</SapTag> acúmulo",
        ["1"],
        [[T(texto="obtém 1 acúmulo", estilo="normal")]],
    ),
    ("linha_vazia_some", "A\n\n\nB", [], [[T(texto="A", estilo="normal")], [T(texto="B", estilo="normal")]]),
    ("elemento_dentro_de_destaque_volta", "<color=Fire>Dano</color> e <color=Light>Luz</color>", [], [
        [T(texto="Dano", estilo="fusion"), T(texto=" e ", estilo="normal"), T(texto="Luz", estilo="spectro")]
    ]),
]


@pytest.mark.parametrize(("nome", "texto", "parametros", "esperado"), CASOS, ids=[c[0] for c in CASOS])
def test_converte_marcacao_do_jogo(nome: str, texto: str, parametros: list[str], esperado: list[Paragrafo]) -> None:
    assert converter_texto(texto, parametros) == (esperado, [])


def test_avisa_marcacao_desconhecida() -> None:
    assert converter_texto("<b>x</b>", []) == ([[T(texto="x", estilo="normal")]], ["marcação desconhecida: <b>"])
