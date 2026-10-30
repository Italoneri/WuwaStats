from pathlib import Path


def test_nao_usa_apis_que_enviam_entrada_ao_jogo() -> None:
    """A captura só pode ler a tela; qualquer API de injeção de teclado/mouse ou foco é proibida."""
    pasta = Path(__file__).parent
    fontes = [arquivo for arquivo in pasta.glob("*.py") if not arquivo.name.startswith("test_")]
    codigo = "\n".join(arquivo.read_text(encoding="utf-8") for arquivo in fontes)
    proibidas = ["SendInput", "keybd_event", "mouse_event", "PostMessage", "SendMessage", "SetForegroundWindow", "pyautogui"]

    assert [api for api in proibidas if api in codigo] == []
