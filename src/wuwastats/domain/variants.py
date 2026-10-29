"""Escolhe a variante da build conforme as condições informadas (arma, sequência...)."""

from dataclasses import dataclass

from wuwastats.domain.models import Condicoes
from wuwastats.domain.names import fold
from wuwastats.domain.tables import BuildSpec, Perfil


@dataclass(frozen=True)
class Resolucao:
    spec: BuildSpec
    variante: int | None
    condicoes_pendentes: tuple[str, ...]


def resolver_build(perfil: Perfil, condicoes: Condicoes) -> Resolucao:
    """A primeira variante cujas condições batem vence. Condição ausente na entrada interrompe
    a escolha e volta como pendente para a interface perguntar; enquanto isso vale o perfil base."""
    informadas = condicoes.model_dump(exclude_none=True)
    for indice, variante in enumerate(perfil.variantes):
        exigidas = variante.condicao.model_dump(exclude_none=True)
        pendentes = tuple(chave for chave in exigidas if chave not in informadas)
        if pendentes:
            return Resolucao(perfil.base, None, pendentes)
        if all(informadas[chave] == valor for chave, valor in exigidas.items()):
            return Resolucao(variante.spec, indice, ())
    return Resolucao(perfil.base, None, ())


def detectar_condicoes(perfil: Perfil, arma_equipada: str | None, informadas: Condicoes) -> Condicoes:
    """Condições informadas pelo usuário prevalecem; o resto vem do print do personagem.
    Sem arma lida ou sem armas_assinatura no perfil, a condição fica pendente (None)."""
    if informadas.arma_assinatura is not None or arma_equipada is None or not perfil.armas_assinatura:
        return informadas
    return informadas.model_copy(update={"arma_assinatura": fold(arma_equipada) in perfil.armas_assinatura})
