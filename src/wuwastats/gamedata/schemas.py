"""Esquema dos arquivos em data/. Erros aqui viram mensagens apontando arquivo e campo."""

from itertools import pairwise
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from wuwastats.domain.models import ESTRELAS_MAXIMAS, Condicoes, Custo, Escala

CustoChave = Literal["1", "3", "4"]
CUSTO_POR_CHAVE: dict[CustoChave, Custo] = {"1": 1, "3": 3, "4": 4}
CUSTO_MAXIMO = 12

StatKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z_]*$")]
Estrelas = Annotated[int, Field(ge=1, le=ESTRELAS_MAXIMAS)]


class _Estrito(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Meta(BaseModel):
    model_config = ConfigDict(extra="allow")


class ToleranciaPadrao(_Estrito):
    percentual: float = Field(ge=0)
    fixo: float = Field(ge=0)


class SubstatsMeta(Meta):
    tolerancia_padrao: ToleranciaPadrao


class SubstatRaw(_Estrito):
    valores: list[float] = Field(min_length=1)
    tolerancia: float | None = Field(default=None, ge=0)
    status: str = "ok"

    @field_validator("valores")
    @classmethod
    def _crescente(cls, valores: list[float]) -> list[float]:
        if any(atual <= anterior for anterior, atual in pairwise(valores)):
            raise ValueError("valores devem estar em ordem crescente, sem repetição")
        return valores


class SubstatsFile(_Estrito):
    meta: SubstatsMeta = Field(alias="_meta")
    substatus: dict[StatKey, SubstatRaw]


class MainStatsCustoRaw(_Estrito):
    primarios: dict[StatKey, float]
    secundario: dict[StatKey, float]
    status: str = "ok"


class MainStatsFile(_Estrito):
    meta: Meta = Field(alias="_meta")
    custos: dict[CustoChave, MainStatsCustoRaw]

    @field_validator("custos")
    @classmethod
    def _todos_os_custos(cls, custos: dict[CustoChave, MainStatsCustoRaw]) -> dict[CustoChave, MainStatsCustoRaw]:
        faltando = sorted(set(CUSTO_POR_CHAVE) - set(custos))
        if faltando:
            raise ValueError(f"faltam os custos {faltando}")
        return custos


class TextoRaw(_Estrito):
    en: str
    pt: str | None = None


class SetRaw(_Estrito):
    nome_pt: str | None = None
    pecas: int | None = Field(ge=1)
    bonus: dict[int, dict[str, float]]
    efeitos: dict[int, TextoRaw] = {}
    status: str = "ok"


class SetsMeta(Meta):
    echos_repetidos_contam: bool


class SetsFile(_Estrito):
    meta: SetsMeta = Field(alias="_meta")
    sets: dict[str, SetRaw]


class EchoRaw(_Estrito):
    nome_pt: str | None = None
    custo: Custo | None = None
    sets: list[str] = []
    habilidade: TextoRaw | None = None
    status: str = "ok"


class EchoesFile(_Estrito):
    meta: Meta = Field(alias="_meta")
    echoes: dict[str, EchoRaw]


class AliasesFile(_Estrito):
    meta: Meta = Field(alias="_meta")
    stats: dict[StatKey, list[str]]
    echoes: dict[str, list[str]]
    sets: dict[str, list[str]]


class TraducaoRaw(_Estrito):
    en: str = Field(min_length=1)
    pt: str | None = None


class RessonadorRaw(_Estrito):
    nome_pt: str | None = None
    elemento: str
    tipo_arma: str
    raridade: int = Field(ge=1, le=5)


class ResonatorsFile(_Estrito):
    meta: Meta = Field(alias="_meta")
    elementos: dict[str, TraducaoRaw]
    tipos_arma: dict[str, TraducaoRaw]
    ressonadores: dict[str, RessonadorRaw]


class ArmaRaw(_Estrito):
    nome_pt: str | None = None
    tipo: str
    raridade: int = Field(ge=1, le=5)


class WeaponsFile(_Estrito):
    meta: Meta = Field(alias="_meta")
    armas: dict[str, ArmaRaw]


class FaixaNotaRaw(_Estrito):
    nota: str = Field(min_length=1)
    min: float = Field(ge=0, le=100)


class NotasFile(_Estrito):
    meta: Meta = Field(alias="_meta")
    faixas: list[FaixaNotaRaw] = Field(min_length=1)

    @field_validator("faixas")
    @classmethod
    def _cobre_de_0_a_100(cls, faixas: list[FaixaNotaRaw]) -> list[FaixaNotaRaw]:
        if any(atual.min >= anterior.min for anterior, atual in pairwise(faixas)):
            raise ValueError("faixas devem estar em ordem decrescente de min, sem repetição")
        if faixas[-1].min != 0:
            raise ValueError("a última faixa precisa ter min 0 para todo score ter nota")
        return faixas


class BuildSpecRaw(_Estrito):
    escala: Escala
    regen_energia_min: float = Field(ge=100)
    custos: list[Custo] = Field(min_length=5, max_length=5)
    set: str | None = None
    echo_principal: str | None = None
    principais: dict[CustoChave, list[str]]
    estrelas: dict[str, Estrelas]  # prioridade do substatus; a ordem das chaves desempata quem tem as mesmas estrelas

    @field_validator("custos")
    @classmethod
    def _custo_total(cls, custos: list[Custo]) -> list[Custo]:
        if sum(custos) > CUSTO_MAXIMO:
            raise ValueError(f"custo total {sum(custos)} passa do limite de {CUSTO_MAXIMO}")
        return custos


class VarianteRaw(_Estrito):
    """Cada campo preenchido sobrescreve o do perfil base quando a condição bate."""

    condicao: Condicoes
    escala: Escala | None = None
    regen_energia_min: float | None = None
    custos: list[Custo] | None = None
    set: str | None = None
    echo_principal: str | None = None
    principais: dict[CustoChave, list[str]] | None = None
    estrelas: dict[str, Estrelas] | None = None

    @field_validator("condicao")
    @classmethod
    def _condicao_preenchida(cls, condicao: Condicoes) -> Condicoes:
        if not condicao.model_dump(exclude_none=True):
            raise ValueError("condição vazia: a variante nunca seria escolhida de forma explícita")
        return condicao


class ArmasPerfilRaw(_Estrito):
    """Recomendação exibida na tela do personagem; não entra no cálculo."""

    melhor: str | None = None
    alternativas: list[str] = []
    status: str = "ok"


class PerfilRaw(BuildSpecRaw):
    personagem: str = Field(min_length=1)
    armas_assinatura: list[str] = []
    armas: ArmasPerfilRaw | None = None
    variantes: list[VarianteRaw] = []
    # Explicação da build para a página do personagem: parágrafos separados por linha em branco, **negrito** permitido.
    descricao: str | None = None
    status: str = "ok"  # "TODO: ..." = algo a conferir à mão (ex.: gerado pelo importador do Game8)


class ArquivosDeDados(BaseModel):
    """Um campo por arquivo em data/ (nome do campo + .json)."""

    substats: SubstatsFile
    main_stats: MainStatsFile
    sets: SetsFile
    echoes: EchoesFile
    stat_aliases: AliasesFile
    characters: dict[str, PerfilRaw]
    notas: NotasFile
    resonators: ResonatorsFile
    weapons: WeaponsFile
