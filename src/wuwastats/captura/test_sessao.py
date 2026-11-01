import pytest

from wuwastats.captura.sessao import (
    EchoLido,
    EspacosCheios,
    Falhou,
    Lendo,
    OrdemInvalida,
    PersonagemLido,
    Recebido,
    Sessao,
    Vazio,
    atualizar_echo,
    atualizar_personagem,
    esvaziar_echo,
    montar_entrada,
    proximo_alvo,
    receber_echo,
    receber_personagem,
    refazer,
    reordenar,
)
from wuwastats.domain.models import EchoEntrada, StatLido
from wuwastats.domain.tables import GameData
from wuwastats.vision.parse import LeituraPersonagem

ECHO = EchoEntrada(nome="Suhsin", custo=4, principal=StatLido(stat="Dano CRIT", valor=44))


def _com_prints(quantidade: int) -> Sessao:
    sessao = Sessao(id="s", build="Suoming_DPS")
    for _ in range(quantidade):
        sessao, _indice, _captura = receber_echo(sessao)
    return sessao


def _lido(sessao: Sessao, captura: int) -> Sessao:
    return atualizar_echo(sessao, captura, EchoLido(captura=captura, do_cache=False, echo=ECHO))[0]


def test_prints_ocupam_os_espacos_em_ordem_com_numero_de_captura_crescente() -> None:
    sessao = _com_prints(2)

    assert sessao.echos[:3] == (Recebido(captura=1), Recebido(captura=2), Vazio())
    assert proximo_alvo(sessao) == 2


def test_sexto_print_sem_refazer_e_recusado() -> None:
    with pytest.raises(EspacosCheios):
        receber_echo(_com_prints(5))


def test_refazer_manda_o_proximo_print_para_o_espaco_marcado_e_desmarca() -> None:
    sessao = refazer(_com_prints(5), 1)

    sessao, indice, captura = receber_echo(sessao)

    assert (indice, captura, sessao.echos[1], sessao.alvo_f8) == (1, 6, Recebido(captura=6), None)


@pytest.mark.parametrize(
    ("ordem", "alvo_antes", "alvo_depois", "capturas"),
    [
        ([1, 0, 2, 3, 4], None, None, [2, 1, 3, 4, 5]),
        ([4, 3, 2, 1, 0], 0, 4, [5, 4, 3, 2, 1]),
        ([0, 1, 2, 3, 4], 2, 2, [1, 2, 3, 4, 5]),
    ],
)
def test_reordenar_move_os_espacos_e_a_marca_de_refazer(
    ordem: list[int], alvo_antes: int | None, alvo_depois: int | None, capturas: list[int]
) -> None:
    sessao = _com_prints(5).model_copy(update={"alvo_f8": alvo_antes})

    reordenada = reordenar(sessao, ordem)

    assert [e.captura for e in reordenada.echos if isinstance(e, Recebido)] == capturas
    assert reordenada.alvo_f8 == alvo_depois


@pytest.mark.parametrize("ordem", [[0, 0, 1, 2, 3], [0, 1, 2, 3], [1, 2, 3, 4, 5]])
def test_reordenar_exige_permutacao_dos_cinco_espacos(ordem: list[int]) -> None:
    with pytest.raises(OrdemInvalida):
        reordenar(_com_prints(5), ordem)


def test_leitura_acha_o_print_mesmo_depois_de_reordenar() -> None:
    sessao = reordenar(_com_prints(2), [1, 0, 2, 3, 4])

    sessao, indice = atualizar_echo(sessao, 1, Lendo(captura=1))

    assert indice == 1
    assert sessao.echos[1] == Lendo(captura=1)


def test_leitura_de_print_removido_nao_muda_nada() -> None:
    sessao = esvaziar_echo(_com_prints(1), 0)

    assert atualizar_echo(sessao, 1, Falhou(captura=1, motivo="x")) == (sessao, None)


def test_personagem_novo_substitui_o_anterior_e_leitura_antiga_e_descartada() -> None:
    sessao, primeira = receber_personagem(Sessao(id="s", build="Suoming_DPS"))
    sessao, segunda = receber_personagem(sessao)

    assert atualizar_personagem(sessao, primeira, Lendo(captura=primeira)) == (sessao, False)
    assert sessao.personagem == Recebido(captura=segunda)


def test_entrada_traz_so_os_echos_lidos_e_o_que_a_tela_do_personagem_informa(dados: GameData) -> None:
    sessao = _lido(_lido(_com_prints(3), 1), 3)
    sessao, captura = receber_personagem(sessao)
    leitura = LeituraPersonagem(arma="Arma Teste", regen_energia_total=118.4)
    sessao, _ = atualizar_personagem(sessao, captura, PersonagemLido(captura=captura, do_cache=False, leitura=leitura))

    entrada = montar_entrada(sessao, dados.perfis["Suoming_DPS"])

    assert entrada is not None
    assert entrada.echos == (ECHO, ECHO)
    assert (entrada.condicoes.arma_assinatura, entrada.regen_total_informado) == (True, 118.4)


def test_entrada_traz_os_atributos_da_tela_na_ordem(dados: GameData) -> None:
    sessao, captura = receber_personagem(_lido(_com_prints(1), 1))
    atributos = [{"stat": "Taxa CRIT", "valor": 62.5, "percentual": True}, {"stat": "HP", "valor": 15000}]
    leitura = LeituraPersonagem.model_validate({"atributos": atributos})
    sessao, _ = atualizar_personagem(sessao, captura, PersonagemLido(captura=captura, do_cache=False, leitura=leitura))

    entrada = montar_entrada(sessao, dados.perfis["Suoming_DPS"])

    assert entrada is not None
    assert entrada.atributos == (StatLido(stat="Taxa CRIT", valor=62.5, percentual=True), StatLido(stat="HP", valor=15000))


def test_sem_tela_do_personagem_nao_ha_atributos(dados: GameData) -> None:
    entrada = montar_entrada(_lido(_com_prints(1), 1), dados.perfis["Suoming_DPS"])

    assert entrada is not None
    assert entrada.atributos == ()


def test_sem_echo_lido_nao_ha_entrada(dados: GameData) -> None:
    assert montar_entrada(_com_prints(2), dados.perfis["Suoming_DPS"]) is None
