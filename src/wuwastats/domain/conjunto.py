"""Análise dos 5 echos juntos: regen, custos, set, echo principal."""

from collections.abc import Mapping, Sequence
from statistics import fmean

from wuwastats.domain.models import Custo, EntradaBuild
from wuwastats.domain.names import ENERGY_REGEN
from wuwastats.domain.report import (
    BonusSet,
    ConjuntoAnalise,
    CustosAnalise,
    EchoAnalise,
    EchoPrincipalAnalise,
    Problema,
    RegenAnalise,
    SetAnalise,
    SubstatValido,
    problema,
)
from wuwastats.domain.score import crit_value
from wuwastats.domain.tables import BuildSpec, GameData, SetInfo

REGEN_BASE = 100.0
CUSTO_MAXIMO = 12
TOLERANCIA_REGEN_INFORMADA = 0.15


def analisar_conjunto(
    entrada: EntradaBuild, echos: Sequence[EchoAnalise], spec: BuildSpec, dados: GameData
) -> ConjuntoAnalise:
    pecas = pecas_por_set(echos, dados.echos_repetidos_contam)
    bonus = bonus_ativos(pecas, dados.sets)
    regen = _regen(entrada, echos, bonus, spec)
    custos = _custos(echos, spec)
    set_ = _set(pecas, bonus, spec, dados)
    echo_principal = _echo_principal(echos, spec)
    return ConjuntoAnalise(
        cv=round(sum(e.cv for e in echos), 2),
        cv_com_principal=round(sum(e.cv for e in echos) + crit_value((e.principal.stat, e.principal.valor) for e in echos), 2),
        score_medio_pct=round(fmean(e.score_pct for e in echos), 1),
        regen=regen,
        custos=custos,
        set=set_,
        echo_principal=echo_principal,
        problemas=[
            *_problemas_regen(regen),
            *_problemas_custos(custos),
            *_problemas_set(set_),
            *_problemas_echo_principal(echo_principal),
        ],
    )


def pecas_por_set(echos: Sequence[EchoAnalise], repetidos_contam: bool) -> dict[str, int]:
    identidades: dict[str, set[str]] = {}
    for echo in echos:
        if echo.set is None:
            continue
        nome = echo.nome or echo.nome_lido
        identidade = nome if nome and not repetidos_contam else f"#{echo.indice}"
        identidades.setdefault(echo.set, set()).add(identidade)
    return {set_: len(ids) for set_, ids in identidades.items()}


def bonus_ativos(pecas: Mapping[str, int], sets: Mapping[str, SetInfo]) -> list[BonusSet]:
    return [
        BonusSet(set=nome, pecas=limite, stats=dict(stats))
        for nome, equipadas in pecas.items()
        for limite, stats in sorted(sets[nome].bonus.items())
        if equipadas >= limite
    ]


def _regen(entrada: EntradaBuild, echos: Sequence[EchoAnalise], bonus: Sequence[BonusSet], spec: BuildSpec) -> RegenAnalise:
    dos_echos = round(sum(_regen_do_echo(e) for e in echos), 2)
    dos_sets = round(sum(b.stats.get(ENERGY_REGEN, 0.0) for b in bonus), 2)
    total = round(REGEN_BASE + dos_echos + dos_sets + entrada.regen_externa, 2)
    informado = entrada.regen_total_informado
    return RegenAnalise(
        base=REGEN_BASE,
        echos=dos_echos,
        sets=dos_sets,
        externa=entrada.regen_externa,
        total=total,
        minimo=spec.regen_energia_min,
        atinge=total >= spec.regen_energia_min,
        informado=informado,
        diferenca_informado=None if informado is None else round(informado - total, 2),
    )


def _regen_do_echo(echo: EchoAnalise) -> float:
    principal = echo.principal.valor if echo.principal.stat == ENERGY_REGEN else 0.0
    substatus = sum(s.valor for s in echo.substatus if isinstance(s, SubstatValido) and s.stat == ENERGY_REGEN)
    return principal + substatus


def _custos(echos: Sequence[EchoAnalise], spec: BuildSpec) -> CustosAnalise:
    atual: list[Custo] = [e.custo for e in echos]
    return CustosAnalise(
        esperado=list(spec.custos),
        atual=atual,
        ok=sorted(atual) == sorted(spec.custos),
    )


def _set(pecas: Mapping[str, int], bonus: list[BonusSet], spec: BuildSpec, dados: GameData) -> SetAnalise:
    esperado = spec.set
    necessarias = dados.sets[esperado].pecas if esperado else None
    equipadas = pecas.get(esperado, 0) if esperado else 0
    return SetAnalise(
        esperado=esperado,
        pecas_necessarias=necessarias,
        pecas_equipadas=equipadas,
        ok=None if necessarias is None else equipadas >= necessarias,
        bonus_ativos=bonus,
    )


def _echo_principal(echos: Sequence[EchoAnalise], spec: BuildSpec) -> EchoPrincipalAnalise:
    """O echo principal é o do primeiro slot."""
    primeiro = echos[0]
    atual = primeiro.nome or primeiro.nome_lido
    esperado = spec.echo_principal
    return EchoPrincipalAnalise(
        esperado=esperado,
        atual=atual,
        ok=None if esperado is None else primeiro.nome == esperado,
    )


def _problemas_regen(regen: RegenAnalise) -> list[Problema]:
    problemas: list[Problema] = []
    if not regen.atinge:
        mensagem = f"Regen. de Energia {regen.total}% abaixo do mínimo de {regen.minimo}%."
        problemas.append(problema("regen_insuficiente", mensagem, "regen"))
    if regen.diferenca_informado is not None and abs(regen.diferenca_informado) > TOLERANCIA_REGEN_INFORMADA:
        mensagem = (
            f"Regen calculada {regen.total}% difere da tela do personagem ({regen.informado}%). "
            "Confira regen_externa (arma, cadeia) e os echos."
        )
        problemas.append(problema("regen_divergente", mensagem, "regen"))
    return problemas


def _problemas_custos(custos: CustosAnalise) -> list[Problema]:
    problemas: list[Problema] = []
    if sum(custos.atual) > CUSTO_MAXIMO:
        mensagem = f"Custo total {sum(custos.atual)} passa do limite de {CUSTO_MAXIMO}."
        problemas.append(problema("custo_total_excedido", mensagem, "custos"))
    if not custos.ok:
        mensagem = f"Custos {custos.atual}; a build pede {custos.esperado}."
        problemas.append(problema("custos_fora_da_build", mensagem, "custos"))
    return problemas


def _problemas_set(set_: SetAnalise) -> list[Problema]:
    if set_.esperado is None:
        return []
    if set_.pecas_necessarias is None:
        mensagem = f"Tamanho do set {set_.esperado} desconhecido em sets.json; não dá para conferir."
        return [problema("set_pecas_desconhecidas", mensagem, "set")]
    if set_.ok:
        return []
    mensagem = f"{set_.pecas_equipadas}/{set_.pecas_necessarias} peças de {set_.esperado}."
    return [problema("set_incompleto", mensagem, "set")]


def _problemas_echo_principal(echo_principal: EchoPrincipalAnalise) -> list[Problema]:
    if echo_principal.ok is not False:
        return []
    mensagem = f"Echo principal {echo_principal.atual}; a build pede {echo_principal.esperado}."
    return [problema("echo_principal_fora_da_build", mensagem, "echo_principal")]
