"""Modelos de requisição/resposta exclusivos da API. A análise em si usa domain/report.py."""

from pydantic import BaseModel, ConfigDict, Field

from wuwastats.domain.analyze import perfil_aplicado
from wuwastats.domain.models import Custo
from wuwastats.domain.names import NameIndex, is_percent_stat
from wuwastats.domain.report import Analise, CategoriaNome, PerfilAplicado
from wuwastats.domain.tables import GameData, Perfil, Traducao
from wuwastats.vision.extract import ExtracaoBuild


class _Contrato(BaseModel):
    model_config = ConfigDict(frozen=True)


class VarianteResumo(_Contrato):
    condicao: dict[str, bool | int | str]
    perfil: PerfilAplicado = Field(description="Perfil base com o que a variante sobrescreve já aplicado.")


class ArmasResumo(_Contrato):
    melhor: str | None
    alternativas: list[str]


class BuildResumo(_Contrato):
    chave: str
    personagem: str = Field(description="Chave do ressonador em GET /api/personagens.")
    condicoes: list[str] = Field(description="Condições usadas pelas variantes; a interface deve perguntar as pendentes.")
    armas: ArmasResumo | None = Field(description="Chaves de GET /api/catalogo (armas); null se a build não recomenda.")
    base: PerfilAplicado
    variantes: list[VarianteResumo]
    descricao: str | None = Field(
        description="Explicação da build: parágrafos separados por linha em branco, **negrito** permitido; null se não há."
    )


class Rotulo(_Contrato):
    chave: str
    nome: str = Field(description="Nome PT-BR do jogo; o inglês se não houver.")


class PersonagemResumo(_Contrato):
    chave: str
    nome: str
    elemento: Rotulo
    tipo_arma: Rotulo
    raridade: int
    builds: list[str] = Field(description="Chaves de GET /api/builds deste personagem.")
    tem_perfil: bool


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


class EchoDetalhe(_Contrato):
    chave: str
    nome: str
    custo: Custo | None
    sets: list[Rotulo]
    habilidade: str | None = Field(
        description="O que o echo faz, com os valores do nível mais alto; PT-BR quando houver. Null se a fonte não tem."
    )


class ArmaCatalogo(ItemCatalogo):
    tipo: str
    raridade: int


class Catalogo(_Contrato):
    stats: list[StatCatalogo]
    sets: list[SetCatalogo]
    echoes: list[EchoCatalogo]
    armas: list[ArmaCatalogo]


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
        VarianteResumo(condicao=v.condicao.model_dump(exclude_none=True), perfil=perfil_aplicado(v.spec))
        for v in perfil.variantes
    ]
    armas = perfil.armas
    return BuildResumo(
        chave=chave,
        personagem=perfil.personagem,
        condicoes=sorted({chave for v in variantes for chave in v.condicao}),
        armas=ArmasResumo(melhor=armas.melhor, alternativas=list(armas.alternativas)) if armas else None,
        base=perfil_aplicado(perfil.base),
        variantes=variantes,
        descricao=perfil.descricao,
    )


def listar_personagens(dados: GameData) -> list[PersonagemResumo]:
    builds: dict[str, list[str]] = {}
    for chave, perfil in sorted(dados.perfis.items()):
        builds.setdefault(perfil.personagem, []).append(chave)
    return [
        PersonagemResumo(
            chave=nome,
            nome=_rotulo(dados.ressonador_names, nome),
            elemento=_traduzido(r.elemento, dados.elementos[r.elemento]),
            tipo_arma=_traduzido(r.tipo_arma, dados.tipos_arma[r.tipo_arma]),
            raridade=r.raridade,
            builds=builds.get(nome, []),
            tem_perfil=nome in builds,
        )
        for nome, r in sorted(dados.ressonadores.items())
    ]


def listar_echoes(dados: GameData) -> list[EchoDetalhe]:
    return [
        EchoDetalhe(
            chave=chave,
            nome=_rotulo(dados.echo_names, chave),
            custo=echo.custo,
            sets=[Rotulo(chave=s, nome=_rotulo(dados.set_names, s)) for s in echo.sets],
            habilidade=echo.habilidade.rotulo if echo.habilidade else None,
        )
        for chave, echo in sorted(dados.echoes.items())
    ]


def _rotulo(indice: NameIndex, chave: str) -> str:
    return next(iter(indice.aliases_by_key.get(chave, ())), chave)


def _traduzido(chave: str, traducao: Traducao) -> Rotulo:
    return Rotulo(chave=chave, nome=traducao.rotulo)


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
        armas=[
            ArmaCatalogo(
                chave=chave, nomes=list(dados.arma_names.aliases_by_key.get(chave, ())), tipo=arma.tipo, raridade=arma.raridade
            )
            for chave, arma in sorted(dados.armas.items())
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
