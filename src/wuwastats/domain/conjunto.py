"""Análise dos 5 echos juntos: regen, custos, set, echo principal."""

from collections.abc import Mapping, Sequence
from statistics import fmean

from wuwastats.domain.metas import REGEN_BASE, MetaAnalise, OrigemValor, StatDeMeta, comparar_meta, formatar_valor
from wuwastats.domain.models import Custo, EntradaBuild
from wuwastats.domain.names import CRIT_RATE, ENERGY_REGEN, NameIndex, resolve_stat
from wuwastats.domain.report import (
    BonusSet,
    ConjuntoAnalise,
    CustosAnalise,
    EchoAnalise,
    EchoPrincipalAnalise,
    Problema,
    RegenAnalise,
    SetAnalise,
    SetPedido,
    SubstatValido,
    problema,
)
from wuwastats.domain.score import crit_value, nota
from wuwastats.domain.tables import BuildSpec, GameData, SetInfo

CUSTO_MAXIMO = 12
TOLERANCIA_REGEN_INFORMADA = 0.15
LIMITE_TAXA_CRIT = 90.0  # com buffs de time (ex.: Guardiã da Costa) passa de 100%, e o excesso não rende


def analisar_conjunto(
    entrada: EntradaBuild, echos: Sequence[EchoAnalise], spec: BuildSpec, dados: GameData
) -> ConjuntoAnalise:
    pecas = pecas_por_set(echos, dados.echos_repetidos_contam)
    bonus = bonus_ativos(pecas, dados.sets)
    regen = _regen(entrada, echos, bonus)
    atributos = atributos_da_tela(entrada, dados.stat_names)
    metas = [comparar_meta(meta, *_valor_da_meta(meta.stat, regen, atributos)) for meta in spec.metas]
    custos = _custos(echos, spec)
    set_ = _set(pecas, bonus, spec)
    echo_principal = _echo_principal(echos, spec)
    score_medio = round(fmean(e.score_pct for e in echos), 1)
    return ConjuntoAnalise(
        cv=round(sum(e.cv for e in echos), 2),
        cv_com_principal=round(sum(e.cv for e in echos) + crit_value((e.principal.stat, e.principal.valor) for e in echos), 2),
        score_medio_pct=score_medio,
        nota_media=nota(score_medio, dados.notas),
        regen=regen,
        custos=custos,
        set=set_,
        echo_principal=echo_principal,
        metas=metas,
        problemas=[
            *_problemas_metas(metas, dados.stat_names),
            *_problemas_taxa_crit(atributos),
            *_problema_regen_divergente(regen),
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


def _regen(entrada: EntradaBuild, echos: Sequence[EchoAnalise], bonus: Sequence[BonusSet]) -> RegenAnalise:
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


def _set(pecas: Mapping[str, int], bonus: list[BonusSet], spec: BuildSpec) -> SetAnalise:
    """Cada set da build (um só ou combinação 3 + 2) é conferido à parte."""
    pedidos = [_pedido(nome, necessarias, pecas.get(nome, 0)) for nome, necessarias in spec.sets.items()]
    return SetAnalise(pedidos=pedidos, ok=all(p.ok for p in pedidos) if pedidos else None, bonus_ativos=bonus)


def _pedido(nome: str, necessarias: int, equipadas: int) -> SetPedido:
    return SetPedido(set=nome, pecas_necessarias=necessarias, pecas_equipadas=equipadas, ok=equipadas >= necessarias)


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


def atributos_da_tela(entrada: EntradaBuild, stat_names: NameIndex) -> dict[str, float]:
    """HP/ATQ/DEF totais vêm sem '%': percentual ausente conta como valor fixo (senão 'HP' fica ambíguo com HP%)."""
    resolvidos = ((resolve_stat(stat_names, a.stat, bool(a.percentual)), a.valor) for a in entrada.atributos)
    return {stat: valor for stat, valor in resolvidos if stat is not None}


def _valor_da_meta(
    stat: StatDeMeta, regen: RegenAnalise, atributos: Mapping[str, float]
) -> tuple[float | None, OrigemValor | None]:
    """A Regen da tela já inclui arma e cadeia; sem print, vale a conta pelos echos."""
    if stat == ENERGY_REGEN:
        return (regen.informado, "tela") if regen.informado is not None else (regen.total, "echos")
    valor = atributos.get(stat)
    return (valor, "tela") if valor is not None else (None, None)


def _problemas_metas(metas: Sequence[MetaAnalise], stat_names: NameIndex) -> list[Problema]:
    abaixo = [_meta_abaixo(a, stat_names) for a in metas if a.veredito == "abaixo"]
    sobrando = [_regen_sobrando(a) for a in metas if a.veredito == "acima" and a.meta.stat == ENERGY_REGEN]
    return [p for p in (*abaixo, *sobrando) if p is not None]


def _meta_abaixo(analise: MetaAnalise, stat_names: NameIndex) -> Problema | None:
    meta, valor = analise.meta, analise.valor
    if valor is None:
        return None
    lido, minimo = formatar_valor(meta.stat, valor), formatar_valor(meta.stat, meta.min)
    return problema("meta_abaixo", f"{_rotulo(stat_names, meta.stat)} {lido} abaixo da meta de {minimo}.", meta.stat)


def _regen_sobrando(analise: MetaAnalise) -> Problema | None:
    meta, valor = analise.meta, analise.valor
    if valor is None:
        return None
    sobra = formatar_valor(meta.stat, round(valor - meta.teto, 2))
    mensagem = (
        f"Regen. de Energia {formatar_valor(meta.stat, valor)} passa do máximo da meta "
        f"({formatar_valor(meta.stat, meta.teto)}): {sobra} sobrando, dá para trocar por dano."
    )
    return problema("regen_sobrando", mensagem, "regen")


def _problemas_taxa_crit(atributos: Mapping[str, float]) -> list[Problema]:
    taxa = atributos.get(CRIT_RATE)
    if taxa is None or taxa <= LIMITE_TAXA_CRIT:
        return []
    mensagem = (
        f"Taxa CRIT {formatar_valor(CRIT_RATE, taxa)} passa de 90%: com buffs de time (ex.: Guardiã da Costa) "
        "pode passar de 100%, e o excesso não rende."
    )
    return [problema("taxa_crit_excessiva", mensagem, CRIT_RATE)]


def _problema_regen_divergente(regen: RegenAnalise) -> list[Problema]:
    if regen.diferenca_informado is None or abs(regen.diferenca_informado) <= TOLERANCIA_REGEN_INFORMADA:
        return []
    mensagem = (
        f"Regen calculada {regen.total}% difere da tela do personagem ({regen.informado}%). "
        "Confira regen_externa (arma, cadeia) e os echos."
    )
    return [problema("regen_divergente", mensagem, "regen")]


def _rotulo(stat_names: NameIndex, stat: str) -> str:
    return next(iter(stat_names.aliases_by_key.get(stat, ())), stat)


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
    return [
        problema("set_incompleto", f"{p.pecas_equipadas}/{p.pecas_necessarias} peças de {p.set}.", "set")
        for p in set_.pedidos
        if not p.ok
    ]


def _problemas_echo_principal(echo_principal: EchoPrincipalAnalise) -> list[Problema]:
    if echo_principal.ok is not False:
        return []
    mensagem = f"Echo principal {echo_principal.atual}; a build pede {echo_principal.esperado}."
    return [problema("echo_principal_fora_da_build", mensagem, "echo_principal")]
