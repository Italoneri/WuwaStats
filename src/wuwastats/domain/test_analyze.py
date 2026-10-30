from typing import get_args

import pytest

from wuwastats.conftest import com_echo
from wuwastats.domain.analyze import analisar
from wuwastats.domain.models import Condicoes, EntradaBuild
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

        assert [e.score_pct for e in analise.echos] == [80.4, 51.3, 37.0, 37.9, 6.3]

    def test_atribui_nota_por_echo_e_ao_conjunto(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        analise = _analisar(entrada_suoming, dados)

        assert [e.nota for e in analise.echos] == ["SS", "B", "C", "C", "C"]
        assert (analise.conjunto.score_medio_pct, analise.conjunto.nota_media) == (42.6, "B")
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

        assert (regen.echos, regen.sets, regen.total, regen.atinge) == (35.2, 10.0, 145.2, True)

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

        assert _analisar(sub_dps, dados).echos[0].score_pct == 78.9


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
        assert analise.conjunto.set.pecas_equipadas == 3

    def test_nome_desconhecido_nao_exige_revisao(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        analise = _analisar(com_echo(entrada_suoming, 0, nome="Eco Misterioso"), dados)

        assert analise.echos[0].revisao is False
        assert analise.echos[0].problemas[0].severidade == "mapeamento"


class TestConjunto:
    def test_avisa_regen_abaixo_do_minimo(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        entrada = entrada_suoming.model_copy(update={"echos": entrada_suoming.echos[:1]})

        regen = _analisar(entrada, dados).conjunto

        assert regen.regen.total == 108.4
        assert "regen_insuficiente" in {p.codigo for p in regen.problemas}

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

        assert _analisar(entrada, dados).conjunto.set.pecas_equipadas == 4

    def test_condicao_pendente_aparece_no_relatorio(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        entrada = entrada_suoming.model_copy(update={"condicoes": Condicoes()})

        analise = _analisar(entrada, dados)

        assert analise.condicoes_pendentes == ["arma_assinatura"]
        assert analise.conjunto.set.esperado is None

    def test_cobra_echo_principal_da_variante(self, dados: GameData, entrada_suoming: EntradaBuild) -> None:
        entrada = com_echo(entrada_suoming, 0, nome="Soulfrayer")
        entrada = entrada.model_copy(update={"condicoes": Condicoes(arma_assinatura=True)})

        conjunto = _analisar(entrada, dados).conjunto

        assert conjunto.echo_principal.ok is False
        assert {"echo_principal_fora_da_build", "set_pecas_desconhecidas"} <= {p.codigo for p in conjunto.problemas}
