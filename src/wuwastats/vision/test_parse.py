import pytest

from wuwastats.vision.parse import ErroLeitura, LeituraPersonagem, parse_echo, parse_personagem

ECHO_OK = (
    '{"nome": "Suhsin", "custo": 4, "set": "Moonlit Clouds",'
    ' "principal": {"stat": "Dano CRIT", "valor": 44, "percentual": true},'
    ' "substatus": [{"stat": "Taxa CRIT", "valor": 8.1, "percentual": true}]}'
)


@pytest.mark.parametrize(
    "resposta",
    [
        ECHO_OK,
        f"```json\n{ECHO_OK}\n```",
        f"<think>vou ler a imagem {{rascunho}}</think>\n{ECHO_OK}",
        f"Aqui está o JSON pedido:\n{ECHO_OK}\nEspero ter ajudado.",
    ],
)
def test_le_echo_mesmo_com_texto_em_volta(resposta: str) -> None:
    echo = parse_echo(resposta)

    assert not isinstance(echo, ErroLeitura)
    assert (echo.nome, echo.custo, echo.principal.valor, echo.substatus[0].stat) == ("Suhsin", 4, 44.0, "Taxa CRIT")


def test_aceita_numeros_no_formato_do_jogo() -> None:
    resposta = (
        '{"custo": "3", "nome": "", "principal": {"stat": "ATQ", "valor": "30,0%"},'
        ' "substatus": [{"stat": "ATQ", "valor": "50"}, {"stat": "Dano CRIT", "valor": "17,4%"}]}'
    )

    echo = parse_echo(resposta)

    assert not isinstance(echo, ErroLeitura)
    assert echo.custo == 3
    assert echo.nome is None
    assert (echo.principal.valor, echo.principal.percentual) == (30.0, True)
    assert [(s.valor, s.percentual) for s in echo.substatus] == [(50.0, None), (17.4, True)]


@pytest.mark.parametrize(
    ("resposta", "trecho"),
    [
        ("", "não contém um objeto JSON"),
        ("não consegui ler a imagem", "não contém um objeto JSON"),
        ('{"custo": 4, "principal": {"stat": "Dano CRIT", "valor": 44,}', "JSON inválido"),
        ('{"custo": 4}', "principal"),
        ('{"custo": 2, "principal": {"stat": "Dano CRIT", "valor": 44}}', "custo"),
        ('{"custo": 4, "principal": {"stat": "Dano CRIT", "valor": "quarenta"}}', "principal.valor"),
        ('{"custo": 4, "principal": {"stat": null, "valor": 44}}', "principal.stat"),
    ],
)
def test_resposta_malformada_vira_erro_de_leitura(resposta: str, trecho: str) -> None:
    erro = parse_echo(resposta)

    assert isinstance(erro, ErroLeitura)
    assert trecho in erro.motivo


def test_le_tela_do_personagem() -> None:
    leitura = parse_personagem('{"personagem": "Suoming", "arma": "Arma Teste", "regen_energia_total": "125,4%"}')

    assert leitura == LeituraPersonagem(personagem="Suoming", arma="Arma Teste", regen_energia_total=125.4)


def test_tela_do_personagem_aceita_campos_nulos() -> None:
    assert parse_personagem('{"arma": null}') == LeituraPersonagem()
