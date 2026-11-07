import json

import pytest
from revisao_kit import Correcao, corrigir, ler_correcoes, suspeitos

from wuwastats.gamedata.kit_texto import Paragrafo, Trecho


def _paragrafos(*linhas: str) -> list[Paragrafo]:
    return [[Trecho(texto=linha, estilo="normal")] for linha in linhas]


def test_corrigir_troca_trecho_e_marca_usada() -> None:
    correcoes = [Correcao(trecho="777", troca="", motivo="lixo"), Correcao(trecho="nunca", troca="x", motivo="m")]

    texto, usadas = corrigir("Causa dano.\n777\nFim.zz", correcoes)

    assert texto == "Causa dano.\n\nFim.zz"
    assert usadas == {0}


@pytest.mark.parametrize(("chave", "esperado"), [("Fase_3", "Fase 3"), ("Fase_2", "Fase 2"), (None, "Fase 2")])
def test_corrigir_com_chave_so_troca_o_texto_daquele_id(chave: str | None, esperado: str) -> None:
    correcoes = [Correcao(trecho="Fase 2", troca="Fase 3", motivo="repetido", chave="Fase_3")]

    texto, _ = corrigir("Fase 2", correcoes, chave)

    assert texto == esperado


def test_ler_correcoes_por_personagem(tmp_path) -> None:
    conteudo = {
        "_meta": {"descricao": "x"},
        "correcoes": {"Augusta": [{"trecho": "Augusta.zz", "troca": "Augusta.", "motivo": "lixo no fim"}]},
    }
    (tmp_path / "kit_correcoes.json").write_text(json.dumps(conteudo), encoding="utf-8")

    correcoes = ler_correcoes(tmp_path)

    assert correcoes == {"Augusta": [Correcao(trecho="Augusta.zz", troca="Augusta.", motivo="lixo no fim")]}


def test_ler_correcoes_sem_arquivo(tmp_path) -> None:
    assert ler_correcoes(tmp_path) == {}


INGLES = _paragrafos("Deals 20% DMG, once every 10s.", "Gains 1 stack.")


@pytest.mark.parametrize(
    ("pt", "motivo"),
    [
        (_paragrafos("Causa 20% de dano, 1 vez a cada 10s.", "777777777777"), "sem texto"),
        (_paragrafos("Causa 20% de dano, 1 vez a cada 15s."), "15"),
        (_paragrafos("Ganha 1 acúmulo de Augusta.zz"), "lixo no fim"),
    ],
    ids=["linha_so_de_numero", "numero_que_o_ingles_nao_tem", "letras_coladas_no_ponto_final"],
)
def test_suspeitos_aponta_problema(pt: list[Paragrafo], motivo: str) -> None:
    avisos = suspeitos(pt, INGLES)

    assert len(avisos) == 1
    assert motivo in avisos[0]


def test_suspeitos_aceita_traducao_normal() -> None:
    pt = _paragrafos("Causa 20% de dano,", "1 vez a cada 10s.", "Ganha 1 acúmulo.", "Fica 3º no 0,2%.")

    assert suspeitos(pt, [*INGLES, *_paragrafos("0.2%")]) == []
