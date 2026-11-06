"""Correções do texto PT oficial dos kits e a conferência dele contra o texto em inglês do nanoka.

O textmap PT às vezes vem com lixo (ex.: uma linha "777777777777777777" no ATQ Normal da Augusta). O nanoka não tem PT,
mas o inglês dele é limpo e serve de referência: o importador aponta o parágrafo suspeito e a troca fica em
data/kit_correcoes.json, aplicada no texto cru antes da conversão.
"""

import re
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from wuwastats.gamedata.kit_texto import Paragrafo

ARQUIVO_CORRECOES = "kit_correcoes.json"

# Número de 2+ dígitos que não aparece no inglês ("777777"); 1 dígito fica de fora porque o EN escreve "once"/"third".
NUMERO_LONGO = re.compile(r"\d{2,}")
NUMERO = re.compile(r"\d+")
# Letras grudadas depois do ponto final: "de Augusta.zz".
LIXO_NO_FIM = re.compile(r"[.!?][a-zà-ÿ]{1,3}$")
LETRA = re.compile(r"[^\W\d_]")


class Correcao(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    trecho: str
    troca: str
    motivo: str


class _ArquivoCorrecoes(BaseModel):
    correcoes: dict[str, list[Correcao]]


def ler_correcoes(data_dir: Path) -> dict[str, list[Correcao]]:
    caminho = data_dir / ARQUIVO_CORRECOES
    if not caminho.is_file():
        return {}
    return _ArquivoCorrecoes.model_validate_json(caminho.read_bytes()).correcoes


def corrigir(texto: str, correcoes: Sequence[Correcao]) -> tuple[str, set[int]]:
    """Texto com as trocas aplicadas e os índices das correções que acharam o trecho."""
    usadas = {i for i, correcao in enumerate(correcoes) if correcao.trecho in texto}
    for i in sorted(usadas):
        texto = texto.replace(correcoes[i].trecho, correcoes[i].troca)
    return texto, usadas


def suspeitos(pt: Sequence[Paragrafo], ingles: Sequence[Paragrafo]) -> list[str]:
    """Um aviso por parágrafo PT que parece lixo quando comparado ao inglês."""
    numeros_ingles = set(NUMERO.findall(" ".join(_texto(p) for p in ingles)))
    motivos = (_motivo(_texto(p), numeros_ingles) for p in pt)
    return [motivo for motivo in motivos if motivo]


def _motivo(paragrafo: str, numeros_ingles: set[str]) -> str | None:
    if not LETRA.search(paragrafo):
        return f"parágrafo sem texto: '{paragrafo[:60]}'"
    estranhos = sorted(set(NUMERO_LONGO.findall(paragrafo)) - numeros_ingles)
    if estranhos:
        return f"número {', '.join(estranhos)} que o inglês do nanoka não tem: '{paragrafo[:60]}'"
    if LIXO_NO_FIM.search(paragrafo):
        return f"lixo no fim: '...{paragrafo[-40:]}'"
    return None


def _texto(paragrafo: Paragrafo) -> str:
    return "".join(trecho.texto for trecho in paragrafo)
