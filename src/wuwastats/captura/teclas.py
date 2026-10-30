"""Atalhos da captura escritos como texto no .env ("F8", "Ctrl+Shift+E", "Num1") -> códigos do RegisterHotKey."""

from dataclasses import dataclass
from typing import Literal

Acao = Literal["echo", "personagem", "analise"]

MODIFICADORES = {"ctrl": ("Ctrl", 0x0002), "alt": ("Alt", 0x0001), "shift": ("Shift", 0x0004), "win": ("Win", 0x0008)}
TECLAS_NOMEADAS = {
    "insert": ("Insert", 0x2D),
    "home": ("Home", 0x24),
    "end": ("End", 0x23),
    "pageup": ("PageUp", 0x21),
    "pagedown": ("PageDown", 0x22),
    "pause": ("Pause", 0x13),
    "scrolllock": ("ScrollLock", 0x91),
}


@dataclass(frozen=True)
class Atalho:
    modificadores: int
    tecla: int
    rotulo: str


def ler_atalho(texto: str) -> Atalho:
    """Modificadores (Ctrl, Alt, Shift, Win) + uma tecla: F1–F24, A–Z, 0–9, Num0–Num9 ou uma de TECLAS_NOMEADAS."""
    partes = [parte.strip() for parte in texto.split("+")]
    if not texto.strip() or any(not parte for parte in partes):
        raise ValueError(f"atalho vazio ou mal formado: '{texto}'")
    *nomes_modificadores, nome_tecla = partes
    modificadores, rotulos = 0, []
    for nome in nomes_modificadores:
        rotulo, codigo = _modificador(nome, texto)
        modificadores |= codigo
        rotulos.append(rotulo)
    rotulo, tecla = _tecla(nome_tecla, texto)
    return Atalho(modificadores=modificadores, tecla=tecla, rotulo="+".join([*rotulos, rotulo]))


def _modificador(nome: str, texto: str) -> tuple[str, int]:
    encontrado = MODIFICADORES.get(nome.casefold())
    if encontrado is None:
        raise ValueError(f"'{nome}' em '{texto}' não é modificador; use Ctrl, Alt, Shift ou Win")
    return encontrado


def _tecla(nome: str, texto: str) -> tuple[str, int]:
    chave = nome.casefold()
    if chave in TECLAS_NOMEADAS:
        return TECLAS_NOMEADAS[chave]
    if len(nome) == 1 and nome.isascii() and nome.isalnum():
        return nome.upper(), ord(nome.upper())
    if chave.startswith("num") and chave[3:].isdigit() and len(chave) == 4:
        return f"Num{chave[3]}", 0x60 + int(chave[3])
    if chave.startswith("f") and chave[1:].isdigit() and 1 <= int(chave[1:]) <= 24:
        return f"F{int(chave[1:])}", 0x6F + int(chave[1:])
    nomeadas = ", ".join(rotulo for rotulo, _codigo in TECLAS_NOMEADAS.values())
    raise ValueError(f"tecla '{nome}' em '{texto}' não reconhecida; use F1–F24, A–Z, 0–9, Num0–Num9, {nomeadas}")
