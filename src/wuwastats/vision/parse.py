"""Interpreta a resposta da IA sem quebrar: JSON malformado ou incompleto vira ErroLeitura."""

import json
import re
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError, model_validator

from wuwastats.domain.models import Custo, EchoEntrada, StatLido

_PENSAMENTO = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_CERCA_MARKDOWN = re.compile(r"```(?:json)?", re.IGNORECASE)


@dataclass(frozen=True)
class ErroLeitura:
    motivo: str


def _numero(valor: object) -> object:
    """Aceita '17,4%', '17.4', 17.4."""
    if isinstance(valor, str):
        return valor.strip().rstrip("%").strip().replace(",", ".")
    return valor


def _inteiro(valor: object) -> object:
    """Aceita '4', 4.0, 4 (Literal[int] não converte texto sozinho)."""
    if isinstance(valor, str) and valor.strip().isdigit():
        return int(valor.strip())
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    return valor


def _texto_ou_nulo(valor: object) -> object:
    if isinstance(valor, str) and not valor.strip():
        return None
    return valor


Numero = Annotated[float, BeforeValidator(_numero)]
InteiroOpcional = Annotated[int | None, BeforeValidator(_inteiro)]
TextoOpcional = Annotated[str | None, BeforeValidator(_texto_ou_nulo)]


class _Leniente(BaseModel):
    model_config = ConfigDict(extra="ignore")


class StatIA(_Leniente):
    stat: str = Field(min_length=1)
    valor: Numero
    percentual: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def _percentual_pelo_sinal(cls, dados: Any) -> Any:
        if isinstance(dados, dict) and dados.get("percentual") is None and "%" in str(dados.get("valor", "")):
            return {**dados, "percentual": True}
        return dados


class EchoIA(_Leniente):
    nome: TextoOpcional = None
    custo: Annotated[Custo, BeforeValidator(_inteiro)]
    set: TextoOpcional = None
    principal: StatIA
    substatus: list[StatIA] = []


class LeituraPersonagem(_Leniente):
    personagem: TextoOpcional = None
    nivel: InteiroOpcional = None
    arma: TextoOpcional = None
    arma_nivel: InteiroOpcional = None
    arma_rank: InteiroOpcional = None
    regen_energia_total: Numero | None = None
    atributos: list[StatIA] = Field(default=[], description="Atributos totais da tela, com o nome como aparece no jogo.")


def parse_echo(resposta: str) -> EchoEntrada | ErroLeitura:
    leitura = _validar(resposta, EchoIA)
    if isinstance(leitura, ErroLeitura):
        return leitura
    return EchoEntrada.model_validate(leitura.model_dump())


def atributos_da_tela(leitura: LeituraPersonagem) -> tuple[StatLido, ...]:
    return tuple(StatLido.model_validate(atributo.model_dump()) for atributo in leitura.atributos)


def parse_personagem(resposta: str) -> LeituraPersonagem | ErroLeitura:
    return _validar(resposta, LeituraPersonagem)


def _validar[M: BaseModel](resposta: str, modelo: type[M]) -> M | ErroLeitura:
    objeto = _objeto_json(resposta)
    if isinstance(objeto, ErroLeitura):
        return objeto
    try:
        return modelo.model_validate(objeto)
    except ValidationError as erro:
        return ErroLeitura("campos faltando ou inválidos: " + "; ".join(_descrever(e) for e in erro.errors()))


def _objeto_json(resposta: str) -> dict[str, Any] | ErroLeitura:
    limpo = _CERCA_MARKDOWN.sub("", _PENSAMENTO.sub("", resposta))
    inicio, fim = limpo.find("{"), limpo.rfind("}")
    if not 0 <= inicio < fim:
        return ErroLeitura("a resposta não contém um objeto JSON")
    try:
        objeto = json.loads(limpo[inicio : fim + 1])
    except json.JSONDecodeError as erro:
        return ErroLeitura(f"JSON inválido: {erro.msg} (posição {erro.pos})")
    return objeto if isinstance(objeto, dict) else ErroLeitura("o JSON não é um objeto")


def _descrever(erro: Any) -> str:
    campo = ".".join(str(parte) for parte in erro["loc"]) or "(raiz)"
    return f"{campo}: {erro['msg']}"
