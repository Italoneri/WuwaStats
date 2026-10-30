import json
import re
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import unquote

import pytest
from captura import BuildIndefinida, CapturaFalhou, escolher_build, proximo_print_echo, url_resultado

from wuwastats.config import PROJECT_ROOT
from wuwastats.domain.tables import Perfil
from wuwastats.gamedata.loader import load_game_data

PERFIS = load_game_data(PROJECT_ROOT / "fixtures" / "gamedata").perfis


@pytest.mark.parametrize(
    ("existentes", "esperado"),
    [
        ([], "echo_1.png"),
        (["echo_1.png", "echo_3.png", "personagem.png", "outro.png"], "echo_4.png"),
    ],
)
def test_numera_prints_de_echo_em_sequencia(tmp_path: Path, existentes: list[str], esperado: str) -> None:
    for nome in existentes:
        (tmp_path / nome).touch()

    assert proximo_print_echo(tmp_path) == tmp_path / esperado


def test_recusa_sexto_print_de_echo(tmp_path: Path) -> None:
    for numero in range(1, 6):
        (tmp_path / f"echo_{numero}.png").touch()

    with pytest.raises(CapturaFalhou, match="já há 5 prints"):
        proximo_print_echo(tmp_path)


@pytest.mark.parametrize(
    ("perfis", "personagem", "build", "esperado"),
    [
        (PERFIS, "Suoming", "Suoming_SubDPS", "Suoming_SubDPS"),
        ({"Suoming_DPS": PERFIS["Suoming_DPS"]}, "suoming", None, "Suoming_DPS"),
    ],
)
def test_escolhe_build(perfis: Mapping[str, Perfil], personagem: str, build: str | None, esperado: str) -> None:
    assert escolher_build(perfis, personagem, build) == esperado


@pytest.mark.parametrize(
    ("personagem", "build", "trecho"),
    [
        ("Suoming", None, "várias builds (Suoming_DPS, Suoming_SubDPS)"),
        ("Jinhsi", None, "nenhuma build de 'Jinhsi'"),
        ("Suoming", "Suoming_Healer", "build 'Suoming_Healer' não existe"),
    ],
)
def test_build_indefinida_explica_o_motivo(personagem: str, build: str | None, trecho: str) -> None:
    with pytest.raises(BuildIndefinida, match=re.escape(trecho)):
        escolher_build(PERFIS, personagem, build)


def test_url_leva_a_entrada_inteira_no_hash() -> None:
    entrada = json.dumps({"build": "Suoming_DPS", "echos": [{"nome": "Desfia-Alma & #1"}]}, ensure_ascii=False)

    url = url_resultado(8123, entrada)

    prefixo = "http://127.0.0.1:8123/#entrada="
    assert url.startswith(prefixo)
    assert json.loads(unquote(url.removeprefix(prefixo))) == json.loads(entrada)


def test_nao_usa_apis_que_enviam_entrada_ao_jogo() -> None:
    """O utilitário só pode ler a tela; qualquer API de injeção de teclado/mouse ou foco é proibida."""
    codigo = (Path(__file__).parent / "captura.py").read_text(encoding="utf-8")
    proibidas = ["SendInput", "keybd_event", "mouse_event", "PostMessage", "SendMessage", "SetForegroundWindow", "pyautogui"]

    assert [api for api in proibidas if api in codigo] == []
