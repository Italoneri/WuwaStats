"""Converte o texto de habilidade do jogo (rich text da Unreal) em parágrafos de trechos com estilo.

A página desenha os trechos como nós de texto: a marcação do jogo nunca chega ao navegador.
"""

import re
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

Estilo = Literal["normal", "subtitulo", "destaque", "aero", "fusion", "electro", "glacio", "havoc", "spectro"]


class Trecho(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    texto: str
    estilo: Estilo


Paragrafo = list[Trecho]

ESTILO_POR_COR: dict[str, Estilo] = {
    "Title": "subtitulo",
    "Highlight": "destaque",
    "Wind": "aero",
    "Fire": "fusion",
    "Thunder": "electro",
    "Ice": "glacio",
    "Dark": "havoc",
    "Light": "spectro",
}

TAG = re.compile(r"(<[^<>]+>)")
# "{Cus:Ipt,Touch=Toque PC=Pressione Gamepad=Pressione}": o jogo troca pelo verbo da plataforma; o app é de PC.
ENTRADA_POR_PLATAFORMA = re.compile(r"\{Cus:Ipt,[^{}]*?PC=([^{}]*?)(?:\s+Gamepad=[^{}]*)?\}")
# "<size=10> </size>" é o respiro que o jogo põe entre blocos.
ESPACADOR = re.compile(r"<size=\d+>\s*</size>")
# "<SapTag=2>3</SapTag> {Cus:Sap,S=acúmulo P=acúmulos SapTag=2}": singular ou plural conforme o número marcado.
# O marcador às vezes é letra (SapTag=B), e a palavra pode vir dentro de cor e de termo do glossário (<te href=..>).
PLURAL = re.compile(
    r"<SapTag=(\w+)>([^<]*)</SapTag>(\s*)((?:<color=\w+>)?(?:<te [^<>]*>)?)"
    r"\{Cus:Sap,S=([^{}]*?) P=([^{}]*?) SapTag=\1\}"
)
# Número marcado sem palavra para flexionar: a marcação não muda nada e sai.
MARCADOR_SOLTO = re.compile(r"</?SapTag(?:=\w+)?>")
# Subtítulo sem quebra de linha depois (o PT às vezes perde o "\n" que o inglês tem): o texto não pode grudar nele.
SUBTITULO_SEM_QUEBRA = re.compile(r"(<size=\d+><color=Title>[^<]*</color></size>)(?!\n)")


def _singular_ou_plural(encontrado: re.Match[str]) -> str:
    _, numero, espaco, glossario, singular, plural = encontrado.groups()
    return f"{numero}{espaco}{glossario or ''}{singular if numero.strip() == '1' else plural}"


def preencher(modelo: str, parametros: Sequence[str]) -> str:
    """Troca {0}, {1}... pelos parâmetros do efeito; índices sem parâmetro ficam como estão."""

    def trocar(encontrado: re.Match[str]) -> str:
        indice = int(encontrado.group(1))
        return parametros[indice] if indice < len(parametros) else encontrado.group(0)

    return re.sub(r"\{(\d+)\}", trocar, modelo).strip()


def converter_texto(texto: str, parametros: Sequence[str]) -> tuple[list[Paragrafo], list[str]]:
    """Devolve os parágrafos e os avisos (marcação que o conversor não conhece vira texto no estilo atual)."""
    avisos: list[str] = []
    preenchido = MARCADOR_SOLTO.sub("", PLURAL.sub(_singular_ou_plural, preencher(texto, parametros)))
    preparado = ESPACADOR.sub("\n", SUBTITULO_SEM_QUEBRA.sub("\\1\n", ENTRADA_POR_PLATAFORMA.sub(r"\1", preenchido)))
    paragrafos: list[Paragrafo] = [[]]
    pilha: list[Estilo] = ["normal"]
    for parte in TAG.split(preparado):
        if TAG.fullmatch(parte):
            _aplicar_tag(parte, pilha, avisos)
            continue
        for indice, linha in enumerate(parte.split("\n")):
            if indice:
                paragrafos.append([])
            _acrescentar(paragrafos[-1], linha, pilha[-1])
    return [aparado for paragrafo in paragrafos if (aparado := _aparar(paragrafo))], avisos


def _aplicar_tag(tag: str, pilha: list[Estilo], avisos: list[str]) -> None:
    if tag.startswith("</"):
        if len(pilha) > 1:
            pilha.pop()
        return
    pilha.append(_estilo_da_tag(tag, pilha[-1], avisos))


def _estilo_da_tag(tag: str, atual: Estilo, avisos: list[str]) -> Estilo:
    if tag.startswith("<size="):
        return atual
    if tag.startswith("<te "):
        return "destaque"
    cor = re.fullmatch(r"<color=(\w+)>", tag)
    if cor and cor.group(1) in ESTILO_POR_COR:
        return ESTILO_POR_COR[cor.group(1)]
    avisos.append(f"marcação desconhecida: {tag}")
    return atual


def _acrescentar(paragrafo: Paragrafo, texto: str, estilo: Estilo) -> None:
    if not texto:
        return
    if paragrafo and paragrafo[-1].estilo == estilo:
        paragrafo[-1] = Trecho(texto=paragrafo[-1].texto + texto, estilo=estilo)
        return
    paragrafo.append(Trecho(texto=texto, estilo=estilo))


def _aparar(paragrafo: Paragrafo) -> Paragrafo:
    """Espaço só no começo/fim do parágrafo some; entre trechos ele separa palavras e fica."""
    trechos = list(paragrafo)
    while trechos and not trechos[0].texto.strip():
        trechos.pop(0)
    while trechos and not trechos[-1].texto.strip():
        trechos.pop()
    if not trechos:
        return []
    trechos[0] = Trecho(texto=trechos[0].texto.lstrip(), estilo=trechos[0].estilo)
    trechos[-1] = Trecho(texto=trechos[-1].texto.rstrip(), estilo=trechos[-1].estilo)
    return trechos
