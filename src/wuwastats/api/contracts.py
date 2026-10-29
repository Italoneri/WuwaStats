"""Modelos de requisição/resposta exclusivos da API. A análise em si usa domain/report.py."""

from pydantic import BaseModel, ConfigDict, Field

from wuwastats.domain.models import Custo, Escala
from wuwastats.domain.names import is_percent_stat
from wuwastats.domain.report import Analise, CategoriaNome
from wuwastats.domain.tables import GameData, Perfil
from wuwastats.vision.extract import ExtracaoBuild


class _Contrato(BaseModel):
    model_config = ConfigDict(frozen=True)


class VarianteResumo(_Contrato):
    condicao: dict[str, bool | int | str]
    set: str | None
    echo_principal: str | None


class BuildResumo(_Contrato):
    chave: str
    personagem: str
    escala: Escala
    set: str | None
    echo_principal: str | None
    condicoes: list[str] = Field(description="Condições usadas pelas variantes; a interface deve perguntar as pendentes.")
    variantes: list[VarianteResumo]


class StatCatalogo(_Contrato):
    chave: str
    nomes: list[str] = Field(description="Aliases na ordem do arquivo; o primeiro serve de rótulo.")
    percentual: bool
    substatus: list[float] | None = Field(description="Valores discretos (índice = tier - 1); null se não é substatus.")
    principal: dict[Custo, float] = Field(description="Valor máximo como status principal, por custo.")


class ItemCatalogo(_Contrato):
    chave: str
    nomes: list[str]


class SetCatalogo(ItemCatalogo):
    pecas: int | None


class EchoCatalogo(ItemCatalogo):
    custo: Custo | None


class Catalogo(_Contrato):
    stats: list[StatCatalogo]
    sets: list[SetCatalogo]
    echoes: list[EchoCatalogo]


class PedidoAlias(_Contrato):
    model_config = ConfigDict(frozen=True, extra="forbid")

    categoria: CategoriaNome
    chave: str = Field(min_length=1)
    alias: str = Field(min_length=1)


class RespostaExtracao(_Contrato):
    extracao: ExtracaoBuild
    analise: Analise | None = Field(description="Análise dos echos lidos; null se nenhum echo foi lido.")


class Erro(_Contrato):
    mensagem: str
    erros: list[str] = []


def resumir_build(chave: str, perfil: Perfil) -> BuildResumo:
    variantes = [
        VarianteResumo(condicao=v.condicao.model_dump(exclude_none=True), set=v.spec.set, echo_principal=v.spec.echo_principal)
        for v in perfil.variantes
    ]
    return BuildResumo(
        chave=chave,
        personagem=perfil.personagem,
        escala=perfil.base.escala,
        set=perfil.base.set,
        echo_principal=perfil.base.echo_principal,
        condicoes=sorted({chave for v in variantes for chave in v.condicao}),
        variantes=variantes,
    )


def montar_catalogo(dados: GameData) -> Catalogo:
    return Catalogo(
        stats=[_stat(chave, dados) for chave in sorted(dados.stat_names.keys)],
        sets=[
            SetCatalogo(chave=chave, nomes=list(dados.set_names.aliases_by_key.get(chave, ())), pecas=info.pecas)
            for chave, info in sorted(dados.sets.items())
        ],
        echoes=[
            EchoCatalogo(chave=chave, nomes=list(dados.echo_names.aliases_by_key.get(chave, ())), custo=info.custo)
            for chave, info in sorted(dados.echoes.items())
        ],
    )


def _stat(chave: str, dados: GameData) -> StatCatalogo:
    tabela = dados.substats.get(chave)
    return StatCatalogo(
        chave=chave,
        nomes=list(dados.stat_names.aliases_by_key.get(chave, ())),
        percentual=is_percent_stat(chave),
        substatus=list(tabela.valores) if tabela else None,
        principal={custo: t.primarios[chave] for custo, t in dados.main_stats.items() if chave in t.primarios},
    )
