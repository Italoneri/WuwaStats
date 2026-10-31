"""Saída da análise. É o contrato JSON consumido pela interface (ver docs/api.md)."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from wuwastats.domain.models import Custo, Escala

Severidade = Literal["revisao", "mapeamento", "build", "aviso"]

CodigoProblema = Literal[
    "stat_desconhecido",
    "stat_nao_e_substatus",
    "valor_fora_tolerancia",
    "substat_duplicado",
    "excesso_substatus",
    "principal_invalido_para_custo",
    "custo_divergente",
    "custo_total_excedido",
    "nome_desconhecido",
    "set_desconhecido",
    "principal_fora_da_build",
    "set_fora_da_build",
    "custos_fora_da_build",
    "set_incompleto",
    "echo_principal_fora_da_build",
    "regen_insuficiente",
    "principal_valor_divergente",
    "regen_divergente",
]

# revisao: leitura provavelmente errada, precisa de correção manual
# mapeamento: nome fora do dicionário, usuário precisa mapear
# build: leitura ok, mas não segue o perfil/variante
SEVERIDADE: dict[CodigoProblema, Severidade] = {
    "stat_desconhecido": "revisao",
    "stat_nao_e_substatus": "revisao",
    "valor_fora_tolerancia": "revisao",
    "substat_duplicado": "revisao",
    "excesso_substatus": "revisao",
    "principal_invalido_para_custo": "revisao",
    "custo_divergente": "revisao",
    "custo_total_excedido": "revisao",
    "nome_desconhecido": "mapeamento",
    "set_desconhecido": "mapeamento",
    "principal_fora_da_build": "build",
    "set_fora_da_build": "build",
    "custos_fora_da_build": "build",
    "set_incompleto": "build",
    "echo_principal_fora_da_build": "build",
    "regen_insuficiente": "build",
    "principal_valor_divergente": "aviso",
    "regen_divergente": "aviso",
}


class _Saida(BaseModel):
    model_config = ConfigDict(frozen=True)


class Problema(_Saida):
    codigo: CodigoProblema
    severidade: Severidade
    mensagem: str
    campo: str | None = None


def problema(codigo: CodigoProblema, mensagem: str, campo: str | None = None) -> Problema:
    return Problema(codigo=codigo, severidade=SEVERIDADE[codigo], mensagem=mensagem, campo=campo)


class SubstatValido(_Saida):
    tipo: Literal["valido"] = "valido"
    stat: str
    stat_lido: str
    valor_lido: float
    valor: float
    diferenca: float
    dentro_tolerancia: bool
    min: float
    max: float
    posicao_pct: float
    tier: int
    tiers_total: int
    peso: float
    pontos: float


class SubstatInvalido(_Saida):
    tipo: Literal["invalido"] = "invalido"
    stat_lido: str
    valor_lido: float
    motivo: Literal["desconhecido", "nao_e_substatus"]


Substat = Annotated[SubstatValido | SubstatInvalido, Field(discriminator="tipo")]


class PrincipalAnalise(_Saida):
    stat: str | None
    stat_lido: str
    valor: float
    valor_esperado: float | None
    valido_para_custo: bool
    recomendado: bool | None


class EchoAnalise(_Saida):
    indice: int
    nome: str | None
    nome_lido: str | None
    custo: Custo
    set: str | None
    set_lido: str | None
    principal: PrincipalAnalise
    substatus: list[Substat]
    score_pct: float
    nota: str
    cv: float
    revisao: bool
    problemas: list[Problema]


class RegenAnalise(_Saida):
    base: float
    echos: float
    sets: float
    externa: float
    total: float
    minimo: float
    atinge: bool
    informado: float | None
    diferenca_informado: float | None


class CustosAnalise(_Saida):
    esperado: list[Custo]
    atual: list[Custo]
    ok: bool


class BonusSet(_Saida):
    set: str
    pecas: int
    stats: dict[str, float]


class SetPedido(_Saida):
    set: str
    pecas_necessarias: int
    pecas_equipadas: int
    ok: bool


class SetAnalise(_Saida):
    pedidos: list[SetPedido] = Field(description="Um por set da build (combinação: 3 + 2); vazio = set livre.")
    ok: bool | None = Field(description="Todos os pedidos atendidos; null se a build não pede set.")
    bonus_ativos: list[BonusSet]


class EchoPrincipalAnalise(_Saida):
    esperado: str | None
    atual: str | None
    ok: bool | None


class ConjuntoAnalise(_Saida):
    cv: float
    cv_com_principal: float
    score_medio_pct: float
    nota_media: str
    regen: RegenAnalise
    custos: CustosAnalise
    set: SetAnalise
    echo_principal: EchoPrincipalAnalise
    problemas: list[Problema]


class CandidatoTroca(_Saida):
    indice: int
    nome: str | None
    score_pct: float
    nota: str
    motivos: list[str]


CategoriaNome = Literal["stats", "echoes", "sets"]


class NomeDesconhecido(_Saida):
    categoria: CategoriaNome
    nome_lido: str
    echos: list[int]


class PerfilAplicado(_Saida):
    escala: Escala
    regen_energia_min: float
    custos: list[Custo]
    sets: dict[str, int] = Field(description="Set → peças pedidas; vazio = set livre.")
    echo_principal: str | None
    principais: dict[Custo, list[str]]
    estrelas: dict[str, int] = Field(description="1 a 3 por substatus, na ordem de prioridade da build.")


class Analise(_Saida):
    build: str
    personagem: str
    variante: int | None
    condicoes_pendentes: list[str]
    perfil: PerfilAplicado
    echos: list[EchoAnalise]
    conjunto: ConjuntoAnalise
    candidatos_troca: list[CandidatoTroca]
    nomes_desconhecidos: list[NomeDesconhecido]
    revisao: bool
