"""Ponto de entrada da análise: echos lidos + perfil -> relatório completo."""

from collections.abc import Sequence

from wuwastats.domain.conjunto import analisar_conjunto
from wuwastats.domain.echo import ContextoEcho, analisar_echo
from wuwastats.domain.models import EntradaBuild
from wuwastats.domain.report import (
    Analise,
    CandidatoTroca,
    CategoriaNome,
    EchoAnalise,
    NomeDesconhecido,
    PerfilAplicado,
    SubstatInvalido,
)
from wuwastats.domain.score import melhor_caso
from wuwastats.domain.tables import BuildSpec, GameData, Perfil
from wuwastats.domain.variants import resolver_build


def analisar(entrada: EntradaBuild, perfil: Perfil, dados: GameData) -> Analise:
    resolucao = resolver_build(perfil, entrada.condicoes)
    spec = resolucao.spec
    ctx = ContextoEcho(dados=dados, spec=spec, melhor_caso=melhor_caso(spec.pesos, dados.substats))
    echos = [analisar_echo(indice, echo, ctx) for indice, echo in enumerate(entrada.echos)]
    conjunto = analisar_conjunto(entrada, echos, spec, dados)
    return Analise(
        build=entrada.build,
        personagem=perfil.personagem,
        variante=resolucao.variante,
        condicoes_pendentes=list(resolucao.condicoes_pendentes),
        perfil=_perfil_aplicado(spec),
        echos=echos,
        conjunto=conjunto,
        candidatos_troca=candidatos_troca(echos),
        nomes_desconhecidos=nomes_desconhecidos(echos),
        revisao=any(e.revisao for e in echos) or any(p.severidade == "revisao" for p in conjunto.problemas),
    )


def candidatos_troca(echos: Sequence[EchoAnalise]) -> list[CandidatoTroca]:
    """Do pior para o melhor: primeiro quem foge da build, depois o menor score."""

    def problemas_de_build(echo: EchoAnalise) -> list[str]:
        return [p.mensagem for p in echo.problemas if p.severidade == "build"]

    ordenados = sorted(echos, key=lambda e: (-len(problemas_de_build(e)), e.score_pct))
    return [
        CandidatoTroca(
            indice=e.indice,
            nome=e.nome or e.nome_lido,
            score_pct=e.score_pct,
            nota=e.nota,
            motivos=[*problemas_de_build(e), f"Score {e.score_pct}%."],
        )
        for e in ordenados
    ]


def nomes_desconhecidos(echos: Sequence[EchoAnalise]) -> list[NomeDesconhecido]:
    ocorrencias: dict[tuple[CategoriaNome, str], list[int]] = {}
    for echo in echos:
        for chave in _nomes_nao_resolvidos(echo):
            ocorrencias.setdefault(chave, []).append(echo.indice)
    return [
        NomeDesconhecido(categoria=categoria, nome_lido=nome, echos=indices)
        for (categoria, nome), indices in ocorrencias.items()
    ]


def _nomes_nao_resolvidos(echo: EchoAnalise) -> list[tuple[CategoriaNome, str]]:
    nomes: list[tuple[CategoriaNome, str]] = []
    if echo.nome_lido is not None and echo.nome is None:
        nomes.append(("echoes", echo.nome_lido))
    if echo.set_lido is not None and echo.set is None:
        nomes.append(("sets", echo.set_lido))
    if echo.principal.stat is None:
        nomes.append(("stats", echo.principal.stat_lido))
    nomes.extend(
        ("stats", s.stat_lido)
        for s in echo.substatus
        if isinstance(s, SubstatInvalido) and s.motivo == "desconhecido"
    )
    return nomes


def _perfil_aplicado(spec: BuildSpec) -> PerfilAplicado:
    return PerfilAplicado(
        escala=spec.escala,
        regen_energia_min=spec.regen_energia_min,
        custos=list(spec.custos),
        set=spec.set,
        echo_principal=spec.echo_principal,
        principais={custo: sorted(stats) for custo, stats in spec.principais.items()},
        pesos=dict(spec.pesos),
    )
