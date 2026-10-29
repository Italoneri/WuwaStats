import pytest

from wuwastats.domain.models import Condicoes
from wuwastats.domain.tables import GameData
from wuwastats.domain.variants import Resolucao, resolver_build


@pytest.mark.parametrize(
    ("arma_assinatura", "variante", "set_", "echo_principal"),
    [
        (True, 0, "Heart of Sworn Vigil", "Suhsin"),
        (False, 1, "Moonlit Clouds", None),
    ],
)
def test_escolhe_variante_pela_arma(
    dados: GameData, arma_assinatura: bool, variante: int, set_: str, echo_principal: str | None
) -> None:
    resolucao = resolver_build(dados.perfis["Suoming_DPS"], Condicoes(arma_assinatura=arma_assinatura))

    assert resolucao.variante == variante
    assert resolucao.spec.set == set_
    assert resolucao.spec.echo_principal == echo_principal
    assert resolucao.condicoes_pendentes == ()


def test_condicao_nao_informada_volta_como_pendente_e_usa_base(dados: GameData) -> None:
    perfil = dados.perfis["Suoming_DPS"]

    resolucao = resolver_build(perfil, Condicoes())

    assert resolucao.condicoes_pendentes == ("arma_assinatura",)
    assert resolucao.variante is None
    assert resolucao.spec == perfil.base


def test_variante_herda_campos_do_perfil_base(dados: GameData) -> None:
    perfil = dados.perfis["Suoming_DPS"]

    spec = resolver_build(perfil, Condicoes(arma_assinatura=True)).spec

    assert spec.pesos == perfil.base.pesos
    assert spec.custos == (4, 3, 3, 1, 1)


def test_perfil_sem_variantes_ignora_condicoes(dados: GameData) -> None:
    perfil = dados.perfis["Suoming_SubDPS"]

    resolucao = resolver_build(perfil, Condicoes(arma_assinatura=True))

    assert resolucao == Resolucao(perfil.base, None, ())
