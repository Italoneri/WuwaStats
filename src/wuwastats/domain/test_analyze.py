import dataclasses
from collections.abc import Callable
from typing import get_args

import pytest

from wuwastats.conftest import com_echo
from wuwastats.domain.analyze import analisar
from wuwastats.domain.metas import MetaDeStatus
from wuwastats.domain.models import Condicoes, EntradaBuild, StatLido
from wuwastats.domain.report import SEVERIDADE, Analise, CodigoProblema, SubstatInvalido, SubstatValido
from wuwastats.domain.tables import GameData


def _analisar(entrada: EntradaBuild, dados: GameData) -> Analise:
    return analisar(entrada, dados.perfis[entrada.build], dados)


def _codigos(analise: Analise, indice: int) -> list[str]:
    return [p.codigo for p in analise.echos[indice].problemas]


def test_todo_codigo_de_problema_tem_severidade() -> None:
    assert set(SEVERIDADE) == set(get_args(CodigoProblema))


class TestEntradaLimpa:
    def test_calcula_score_ponderado_por_echo(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        analise = _analisar(entrada_suoming, dados)

        assert [e.score_pct for e in analise.echos] == [80.4, 54.5, 35.5, 39.3, 5.6]

    def test_atribui_nota_por_echo_e_ao_conjunto(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        analise = _analisar(entrada_suoming, dados)

        assert [e.nota for e in analise.echos] == ["SS", "B", "C", "C", "C"]
        assert (analise.conjunto.score_medio_pct, analise.conjunto.nota_media) == (43.1, "B")
        assert {c.indice: c.nota for c in analise.candidatos_troca}[0] == "SS"

    def test_ajusta_valor_lido_e_informa_tier(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        dano_crit = _analisar(entrada_suoming, dados).echos[0].substatus[1]

        assert isinstance(dano_crit, SubstatValido)
        assert (dano_crit.valor_lido, dano_crit.valor, dano_crit.tier, dano_crit.tiers_total) == (17.5, 17.4, 5, 8)
        assert (dano_crit.min, dano_crit.max, dano_crit.posicao_pct) == (12.6, 21.0, 57.1)

    def test_calcula_crit_value(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        analise = _analisar(entrada_suoming, dados)

        assert analise.echos[0].cv == 33.6
        assert analise.conjunto.cv == 114.6
        assert analise.conjunto.cv_com_principal == 158.6

    def test_soma_regen_de_echos_e_bonus_de_set(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        regen = _analisar(entrada_suoming, dados).conjunto.regen

        assert (regen.echos, regen.sets, regen.total) == (35.2, 10.0, 145.2)

    def test_confere_set_custos_e_variante(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        analise = _analisar(entrada_suoming, dados)

        assert analise.variante == 1
        assert analise.conjunto.set.ok is True
        assert analise.conjunto.custos.ok is True
        assert analise.revisao is False

    def test_aponta_echo_fora_da_build_como_pior_candidato(
        self, dados: GameData, entrada_suoming: EntradaBuild
    ) -> None:
        analise = _analisar(entrada_suoming, dados)

        assert [c.indice for c in analise.candidatos_troca] == [4, 2, 3, 1, 0]
        assert _codigos(analise, 4) == ["principal_fora_da_build"]

    def test_mesmo_echo_pontua_diferente_em_outra_build(
        self, dados: GameData, entrada_suoming: EntradaBuild
    ) -> None:
        sub_dps = entrada_suoming.model_copy(update={"build": "Suoming_SubDPS"})

        assert _analisar(sub_dps, dados).echos[0].score_pct == 79.2


class TestRevisao:
    def test_marca_valor_fora_da_tolerancia(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        substatus = [{"stat": "Dano CRIT", "valor": 25.0}]
        analise = _analisar(com_echo(entrada_suoming, 1, substatus=substatus), dados)

        assert analise.echos[1].revisao is True
        assert _codigos(analise, 1) == ["valor_fora_tolerancia"]
        assert analise.revisao is True

    def test_marca_status_que_nao_existe_como_substatus(
        self, dados: GameData, entrada_suoming: EntradaBuild
    ) -> None:
        substatus = [{"stat": "Dano Elétrico", "valor": 9.4}]
        echo = _analisar(com_echo(entrada_suoming, 1, substatus=substatus), dados).echos[1]

        assert isinstance(echo.substatus[0], SubstatInvalido)
        assert echo.substatus[0].motivo == "nao_e_substatus"
        assert echo.revisao is True

    def test_marca_substatus_duplicado_e_excesso(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        substatus = [{"stat": "Taxa CRIT", "valor": 6.3}] * 6
        analise = _analisar(com_echo(entrada_suoming, 1, substatus=substatus), dados)

        assert set(_codigos(analise, 1)) == {"substat_duplicado", "excesso_substatus"}

    @pytest.mark.parametrize(
        ("principal", "codigo"),
        [
            ({"stat": "Dano CRIT", "valor": 44.0}, "principal_invalido_para_custo"),
            ({"stat": "Dano Xpto", "valor": 18.0}, "stat_desconhecido"),
            ({"stat": "ATQ%", "valor": 12.0}, "principal_valor_divergente"),
        ],
    )
    def test_valida_status_principal_contra_custo(
        self, dados: GameData, entrada_suoming: EntradaBuild, principal: dict[str, object], codigo: str
    ) -> None:
        analise = _analisar(com_echo(entrada_suoming, 3, principal=principal), dados)

        assert codigo in _codigos(analise, 3)

    def test_marca_custo_somando_mais_de_doze(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        analise = _analisar(com_echo(entrada_suoming, 3, custo=4, principal={"stat": "ATQ%", "valor": 33.0}), dados)

        assert {p.codigo for p in analise.conjunto.problemas} == {"custo_total_excedido", "custos_fora_da_build"}
        assert analise.revisao is True


class TestNomesDesconhecidos:
    def test_lista_nomes_fora_do_dicionario_sem_quebrar(
        self, dados: GameData, entrada_suoming: EntradaBuild
    ) -> None:
        entrada = com_echo(entrada_suoming, 0, nome="Eco Misterioso", set="Nuvens ao Luar")
        entrada = com_echo(entrada, 1, set="Nuvens ao Luar", substatus=[{"stat": "Sorte", "valor": 1}])

        analise = _analisar(entrada, dados)

        desconhecidos = {(n.categoria, n.nome_lido, tuple(n.echos)) for n in analise.nomes_desconhecidos}
        assert desconhecidos == {
            ("echoes", "Eco Misterioso", (0,)),
            ("sets", "Nuvens ao Luar", (0, 1)),
            ("stats", "Sorte", (1,)),
        }
        assert analise.echos[0].set is None
        assert analise.conjunto.set.pedidos[0].pecas_equipadas == 3

    def test_nome_desconhecido_nao_exige_revisao(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        analise = _analisar(com_echo(entrada_suoming, 0, nome="Eco Misterioso"), dados)

        assert analise.echos[0].revisao is False
        assert analise.echos[0].problemas[0].severidade == "mapeamento"


class TestConjunto:
    def test_soma_regen_externa_e_compara_com_valor_da_tela(
        self, dados: GameData, entrada_suoming: EntradaBuild
    ) -> None:
        entrada = entrada_suoming.model_copy(update={"regen_externa": 12.8, "regen_total_informado": 160.0})

        conjunto = _analisar(entrada, dados).conjunto

        assert conjunto.regen.total == 158.0
        assert conjunto.regen.diferenca_informado == 2.0
        assert "regen_divergente" in {p.codigo for p in conjunto.problemas}

    def test_regen_igual_a_tela_nao_gera_aviso(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        entrada = entrada_suoming.model_copy(update={"regen_total_informado": 145.2})

        assert _analisar(entrada, dados).conjunto.problemas == []

    def test_echos_com_mesmo_nome_contam_uma_peca(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        entrada = com_echo(entrada_suoming, 1, nome="Suhsin", custo=4, principal={"stat": "Taxa CRIT", "valor": 22})

        assert _analisar(entrada, dados).conjunto.set.pedidos[0].pecas_equipadas == 4

    def test_condicao_pendente_aparece_no_relatorio(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        entrada = entrada_suoming.model_copy(update={"condicoes": Condicoes()})

        analise = _analisar(entrada, dados)

        assert analise.condicoes_pendentes == ["arma_assinatura"]
        assert analise.conjunto.set.pedidos == []
        assert analise.conjunto.set.ok is None

    def test_cobra_echo_principal_da_variante(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        entrada = com_echo(entrada_suoming, 0, nome="Soulfrayer")
        entrada = entrada.model_copy(update={"condicoes": Condicoes(arma_assinatura=True)})

        conjunto = _analisar(entrada, dados).conjunto

        assert conjunto.echo_principal.ok is False
        assert "echo_principal_fora_da_build" in {p.codigo for p in conjunto.problemas}


class TestCombinacaoDeSets:
    """Build que pede 3 peças de um set + 2 de outro: cada parte é conferida à parte."""

    def _analisar_combinacao(self, dados: GameData, entrada: EntradaBuild) -> Analise:
        perfil = dados.perfis["Suoming_SubDPS"]
        base = dataclasses.replace(perfil.base, sets={"Moonlit Clouds": 3, "Heart of Sworn Vigil": 2})
        return analisar(entrada.model_copy(update={"build": "Suoming_SubDPS"}), dataclasses.replace(perfil, base=base), dados)

    def test_combinacao_completa_passa(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        entrada = com_echo(com_echo(entrada_suoming, 3, set="Heart of Sworn Vigil"), 4, set="Heart of Sworn Vigil")

        conjunto = self._analisar_combinacao(dados, entrada).conjunto

        assert [(p.set, p.pecas_equipadas, p.ok) for p in conjunto.set.pedidos] == [
            ("Moonlit Clouds", 3, True),
            ("Heart of Sworn Vigil", 2, True),
        ]
        assert conjunto.set.ok is True

    def test_parte_que_falta_vira_problema(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        entrada = com_echo(entrada_suoming, 4, set="Heart of Sworn Vigil")

        analise = self._analisar_combinacao(dados, entrada)

        assert analise.conjunto.set.ok is False
        assert [p.mensagem for p in analise.conjunto.problemas if p.codigo == "set_incompleto"] == [
            "1/2 peças de Heart of Sworn Vigil."
        ]
        assert "set_fora_da_build" not in _codigos(analise, 4)


def _com_atributos(entrada: EntradaBuild, **valores: float) -> EntradaBuild:
    atributos = tuple(StatLido(stat=stat, valor=valor) for stat, valor in valores.items())
    return entrada.model_copy(update={"atributos": atributos})


def _sem_echos_de_regen(entrada: EntradaBuild) -> EntradaBuild:
    """Só o 1º echo: Regen calculada 108.4, abaixo dos 110 da Suoming_DPS."""
    return entrada.model_copy(update={"echos": entrada.echos[:1]})


def _sub_dps(entrada: EntradaBuild) -> EntradaBuild:
    """Suoming_SubDPS pede 120–130% de Regen; os echos da entrada somam 145.2."""
    return entrada.model_copy(update={"build": "Suoming_SubDPS"})


class TestMetas:
    def test_compara_regen_da_tela_antes_dos_echos(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        com_tela = _sub_dps(entrada_suoming).model_copy(update={"regen_total_informado": 125.0})

        pela_tela = _analisar(com_tela, dados).conjunto.metas[0]
        pelos_echos = _analisar(_sub_dps(entrada_suoming), dados).conjunto.metas[0]

        assert (pela_tela.origem, pela_tela.valor, pela_tela.veredito) == ("tela", 125.0, "dentro")
        assert (pelos_echos.origem, pelos_echos.valor, pelos_echos.veredito) == ("echos", 145.2, "acima")

    @pytest.mark.parametrize(
        ("preparar", "codigo", "aparece"),
        [
            (_sem_echos_de_regen, "meta_abaixo", True),
            (_sub_dps, "regen_sobrando", True),
            (lambda e: _com_atributos(e, **{"Taxa CRIT": 92}), "taxa_crit_excessiva", True),
            (lambda e: _com_atributos(e, **{"Taxa CRIT": 90}), "taxa_crit_excessiva", False),
            (lambda e: _com_atributos(e, **{"Taxa CRIT": 85}), "meta_abaixo", False),
        ],
    )
    def test_aponta_problemas_das_metas(
        self,
        dados: GameData,
        entrada_suoming: EntradaBuild,
        preparar: Callable[[EntradaBuild], EntradaBuild],
        codigo: str,
        aparece: bool,
    ) -> None:
        conjunto = _analisar(preparar(entrada_suoming), dados).conjunto

        assert (codigo in {p.codigo for p in conjunto.problemas}) is aparece

    def test_meta_abaixo_explica_o_que_falta(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        conjunto = _analisar(_sem_echos_de_regen(entrada_suoming), dados).conjunto

        assert [(p.mensagem, p.campo, p.severidade) for p in conjunto.problemas if p.codigo == "meta_abaixo"] == [
            ("Regen. de Energia 108.4% abaixo da meta de 110%.", "energy_regen", "build")
        ]

    def test_taxa_crit_acima_da_faixa_e_so_informativa(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        conjunto = _analisar(_com_atributos(entrada_suoming, **{"Taxa CRIT": 85}), dados).conjunto

        crit = conjunto.metas[1]
        assert (crit.valor, crit.veredito, crit.mensagem) == (85, "acima", "acima da faixa, quanto mais melhor")
        assert conjunto.problemas == []

    def test_resolve_hp_da_tela_sem_percentual(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        perfil = dados.perfis["Suoming_DPS"]
        meta = MetaDeStatus(stat="hp_flat", min=50000, tipo="escala", fonte="game8")
        com_hp = dataclasses.replace(perfil, base=dataclasses.replace(perfil.base, metas=(meta,)))
        entrada = _com_atributos(entrada_suoming.model_copy(update={"condicoes": Condicoes()}), HP=48000)

        hp = analisar(entrada, com_hp, dados).conjunto.metas[0]

        assert (hp.valor, hp.origem, hp.veredito) == (48000, "tela", "abaixo")

    def test_meta_sem_valor_fica_so_de_referencia(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        crit = _analisar(entrada_suoming, dados).conjunto.metas[1]

        assert (crit.meta.stat, crit.valor, crit.origem, crit.veredito) == ("crit_rate", None, None, None)

    def test_perfil_aplicado_traz_metas(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        metas = _analisar(entrada_suoming, dados).perfil.metas

        assert [(m.stat, m.min, m.max) for m in metas] == [("energy_regen", 110, None), ("crit_rate", 60, 80)]
