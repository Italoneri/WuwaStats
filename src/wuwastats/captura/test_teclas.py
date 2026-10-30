import pytest

from wuwastats.captura.teclas import Atalho, ler_atalho


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("F8", Atalho(0, 0x77, "F8")),
        ("f24", Atalho(0, 0x87, "F24")),
        ("Win+Shift+E", Atalho(0x8 | 0x4, ord("E"), "Win+Shift+E")),
        ("ctrl + alt + 1", Atalho(0x2 | 0x1, ord("1"), "Ctrl+Alt+1")),
        ("Num5", Atalho(0, 0x65, "Num5")),
        ("Shift+PageDown", Atalho(0x4, 0x22, "Shift+PageDown")),
    ],
)
def test_le_atalho_escrito_no_env(texto: str, esperado: Atalho) -> None:
    assert ler_atalho(texto) == esperado


@pytest.mark.parametrize(
    ("texto", "trecho"),
    [
        ("", "vazio"),
        ("Ctrl+", "mal formado"),
        ("Super+E", "não é modificador"),
        ("F25", "não reconhecida"),
        ("Ctrl+Esc", "não reconhecida"),
    ],
)
def test_recusa_atalho_invalido(texto: str, trecho: str) -> None:
    with pytest.raises(ValueError, match=trecho):
        ler_atalho(texto)
