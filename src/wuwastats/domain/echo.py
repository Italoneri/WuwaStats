"""Análise de um echo isolado: nomes, status principal, substatus e score."""

from collections import Counter
from dataclasses import dataclass

from wuwastats.domain.models import EchoEntrada, StatLido
from wuwastats.domain.names import resolve_stat
from wuwastats.domain.report import (
    EchoAnalise,
    PrincipalAnalise,
    Problema,
    Substat,
    SubstatInvalido,
    SubstatValido,
    problema,
)
from wuwastats.domain.score import MAX_SUBSTATUS, crit_value, nota, pontos, score_pct
from wuwastats.domain.tables import BuildSpec, GameData
from wuwastats.domain.validate import posicao_pct, snap

TOLERANCIA_PRINCIPAL = 0.05


@dataclass(frozen=True)
class ContextoEcho:
    dados: GameData
    spec: BuildSpec
    melhor_caso: float


def analisar_echo(indice: int, echo: EchoEntrada, ctx: ContextoEcho) -> EchoAnalise:
    nome, problemas_nome = _resolver_nome(echo, ctx.dados)
    set_, problemas_set = _resolver_set(echo, ctx)
    principal, problemas_principal = _analisar_principal(echo, ctx)
    analisados = [_analisar_substatus(i, lido, ctx) for i, lido in enumerate(echo.substatus)]
    substatus = [substat for substat, _ in analisados]
    validos = [s for s in substatus if isinstance(s, SubstatValido)]
    score = score_pct(sum(s.pontos for s in validos), ctx.melhor_caso)
    problemas = [
        *problemas_nome,
        *problemas_set,
        *problemas_principal,
        *(p for _, problemas_sub in analisados for p in problemas_sub),
        *_problemas_estrutura(validos, len(substatus)),
    ]
    return EchoAnalise(
        indice=indice,
        nome=nome,
        nome_lido=echo.nome,
        custo=echo.custo,
        set=set_,
        set_lido=echo.set,
        principal=principal,
        substatus=substatus,
        score_pct=score,
        nota=nota(score, ctx.dados.notas),
        cv=crit_value((s.stat, s.valor) for s in validos),
        revisao=any(p.severidade == "revisao" for p in problemas),
        problemas=problemas,
    )


def _resolver_nome(echo: EchoEntrada, dados: GameData) -> tuple[str | None, list[Problema]]:
    if echo.nome is None:
        return None, []
    nome = dados.echo_names.resolve(echo.nome)
    if nome is None:
        return None, [problema("nome_desconhecido", f"Echo '{echo.nome}' não está no dicionário.", "nome")]
    custo_catalogo = dados.echoes[nome].custo
    if custo_catalogo is not None and custo_catalogo != echo.custo:
        mensagem = f"{nome} tem custo {custo_catalogo}, mas foi lido custo {echo.custo}."
        return nome, [problema("custo_divergente", mensagem, "custo")]
    return nome, []


def _resolver_set(echo: EchoEntrada, ctx: ContextoEcho) -> tuple[str | None, list[Problema]]:
    if echo.set is None:
        return None, []
    set_ = ctx.dados.set_names.resolve(echo.set)
    if set_ is None:
        return None, [problema("set_desconhecido", f"Set '{echo.set}' não está no dicionário.", "set")]
    pedidos = ctx.spec.sets
    if pedidos and set_ not in pedidos:
        return set_, [problema("set_fora_da_build", f"Set {set_}; a build pede {' + '.join(pedidos)}.", "set")]
    return set_, []


def _analisar_principal(echo: EchoEntrada, ctx: ContextoEcho) -> tuple[PrincipalAnalise, list[Problema]]:
    lido = echo.principal
    stat = resolve_stat(ctx.dados.stat_names, lido.stat, lido.percentual)
    esperado = ctx.dados.main_stats[echo.custo].primarios.get(stat) if stat else None
    permitidos = ctx.spec.principais.get(echo.custo)
    recomendado = None if permitidos is None or stat is None else stat in permitidos
    analise = PrincipalAnalise(
        stat=stat,
        stat_lido=lido.stat,
        valor=lido.valor,
        valor_esperado=esperado,
        valido_para_custo=esperado is not None,
        recomendado=recomendado,
    )
    return analise, _problemas_principal(analise, echo, sorted(permitidos or ()))


def _problemas_principal(p: PrincipalAnalise, echo: EchoEntrada, permitidos: list[str]) -> list[Problema]:
    if p.stat is None:
        return [problema("stat_desconhecido", f"Status principal '{p.stat_lido}' não reconhecido.", "principal")]
    if p.valor_esperado is None:
        mensagem = f"{p.stat} não pode ser principal de echo custo {echo.custo}."
        return [problema("principal_invalido_para_custo", mensagem, "principal")]
    problemas: list[Problema] = []
    if abs(p.valor - p.valor_esperado) > TOLERANCIA_PRINCIPAL:
        mensagem = f"{p.stat}: esperado {p.valor_esperado} no nível máximo, lido {p.valor}."
        problemas.append(problema("principal_valor_divergente", mensagem, "principal"))
    if p.recomendado is False:
        mensagem = f"Principal {p.stat}; a build pede {', '.join(permitidos)} no custo {echo.custo}."
        problemas.append(problema("principal_fora_da_build", mensagem, "principal"))
    return problemas


def _analisar_substatus(posicao: int, lido: StatLido, ctx: ContextoEcho) -> tuple[Substat, list[Problema]]:
    campo = f"substatus[{posicao}]"
    stat = resolve_stat(ctx.dados.stat_names, lido.stat, lido.percentual)
    if stat is None:
        invalido = SubstatInvalido(stat_lido=lido.stat, valor_lido=lido.valor, motivo="desconhecido")
        return invalido, [problema("stat_desconhecido", f"Substatus '{lido.stat}' não reconhecido.", campo)]
    tabela = ctx.dados.substats.get(stat)
    if tabela is None:
        invalido = SubstatInvalido(stat_lido=lido.stat, valor_lido=lido.valor, motivo="nao_e_substatus")
        return invalido, [problema("stat_nao_e_substatus", f"{stat} não existe como substatus.", campo)]
    ajuste = snap(tabela, lido.valor)
    peso = ctx.spec.pesos.get(stat, 0.0)
    substat = SubstatValido(
        stat=stat,
        stat_lido=lido.stat,
        valor_lido=lido.valor,
        valor=ajuste.valor,
        diferenca=ajuste.diferenca,
        dentro_tolerancia=ajuste.dentro_tolerancia,
        min=tabela.min,
        max=tabela.max,
        posicao_pct=posicao_pct(tabela, ajuste.valor),
        tier=ajuste.tier,
        tiers_total=len(tabela.valores),
        peso=peso,
        pontos=round(pontos(peso, ajuste.valor, tabela.max), 4),
    )
    if ajuste.dentro_tolerancia:
        return substat, []
    mensagem = f"{stat}: lido {lido.valor}, valor válido mais próximo {ajuste.valor}."
    return substat, [problema("valor_fora_tolerancia", mensagem, campo)]


def _problemas_estrutura(validos: list[SubstatValido], quantidade: int) -> list[Problema]:
    repetidos = [stat for stat, vezes in Counter(s.stat for s in validos).items() if vezes > 1]
    problemas = [problema("substat_duplicado", f"{stat} aparece mais de uma vez.", "substatus") for stat in repetidos]
    if quantidade > MAX_SUBSTATUS:
        mensagem = f"{quantidade} substatus lidos; o máximo é {MAX_SUBSTATUS}."
        problemas.append(problema("excesso_substatus", mensagem, "substatus"))
    return problemas
