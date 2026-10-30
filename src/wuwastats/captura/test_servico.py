import json
from collections.abc import Callable
from pathlib import Path

import pytest

from wuwastats.captura.servico import CapturaFalhou, Evento, Executar, SemEchoLido, ServicoCaptura, SessaoInexistente
from wuwastats.captura.sessao import EchoLido, Falhou, PersonagemLido, Vazio
from wuwastats.conftest import TelaFalsa
from wuwastats.domain.tables import GameData
from wuwastats.vision.cache import CacheVisao
from wuwastats.vision.client import ConfiguracaoAusente
from wuwastats.vision.extract import Extrator
from wuwastats.vision.image import Imagem

ECHO = {"nome": "Suhsin", "custo": 4, "principal": {"stat": "Dano CRIT", "valor": 44}, "substatus": []}
RESPOSTAS = {
    b"echo": json.dumps(ECHO),
    b"tela": '{"personagem": "Suoming", "arma": "Arma Teste", "regen_energia_total": 118.4}',
}


class ModeloFalso:
    nome = "modelo-falso"

    def completar(self, prompt: str, imagem: Imagem) -> str:
        return RESPOSTAS.get(imagem.conteudo, "não sei")


class Adiado:
    """Executor que segura as leituras até o teste mandar rodar."""

    def __init__(self) -> None:
        self.tarefas: list[Callable[[], None]] = []

    def __call__(self, tarefa: Callable[[], None]) -> None:
        self.tarefas.append(tarefa)

    def rodar(self) -> None:
        while self.tarefas:
            self.tarefas.pop(0)()


def _servico(tela: TelaFalsa, dados: GameData, tmp_path: Path, executar: Executar) -> ServicoCaptura:
    def criar_extrator() -> Extrator:
        return Extrator(modelo=ModeloFalso(), cache=CacheVisao(tmp_path / "cache"), dados=dados)

    return ServicoCaptura(tela.ferramentas(), criar_extrator, executar)


@pytest.fixture
def servico(tela: TelaFalsa, dados: GameData, tmp_path: Path) -> ServicoCaptura:
    return _servico(tela, dados, tmp_path, executar=lambda tarefa: tarefa())


def _ouvir(servico: ServicoCaptura, sessao_id: str) -> list[Evento]:
    eventos: list[Evento] = []
    servico.inscrever(sessao_id, eventos.append)
    return eventos


def _resumo(eventos: list[Evento]) -> list[tuple[str, object]]:
    return [(e.tipo, e.espaco) for e in eventos]


def test_f8_le_o_print_na_hora_e_avisa_cada_passo(servico: ServicoCaptura, tela: TelaFalsa) -> None:
    sessao = servico.iniciar("Suoming_DPS")
    eventos = _ouvir(servico, sessao.id)

    tela.apertar("F8")

    assert _resumo(eventos) == [("estado", None), ("print_recebido", 0), ("leitura_iniciada", 0), ("lido", 0)]
    assert (eventos[-1].nome, eventos[-1].principal and eventos[-1].principal.valor) == ("Suhsin", 44.0)
    assert isinstance(servico.estado(sessao.id).echos[0], EchoLido)
    assert tela.sinais == ["ok"]


def test_leitura_que_falha_marca_o_espaco_com_o_motivo(servico: ServicoCaptura, tela: TelaFalsa) -> None:
    sessao = servico.iniciar("Suoming_DPS")
    eventos = _ouvir(servico, sessao.id)

    tela.apertar("F8", b"borrado")

    espaco = servico.estado(sessao.id).echos[0]
    assert isinstance(espaco, Falhou)
    assert eventos[-1].tipo == "falhou"
    assert eventos[-1].motivo == espaco.motivo == "a resposta não contém um objeto JSON"


def test_f9_le_a_tela_do_personagem_e_usa_a_arma_na_entrada(servico: ServicoCaptura, tela: TelaFalsa, dados: GameData) -> None:
    sessao = servico.iniciar("Suoming_DPS")
    tela.apertar("F8")
    tela.apertar("F9", b"tela")

    estado = servico.estado(sessao.id)
    entrada = servico.entrada(sessao.id, dados.perfis.__getitem__)

    assert isinstance(estado.personagem, PersonagemLido)
    assert (entrada.condicoes.arma_assinatura, entrada.regen_total_informado) == (True, 118.4)


def test_erro_ao_capturar_a_janela_avisa_a_pagina_e_bipa(servico: ServicoCaptura, tela: TelaFalsa) -> None:
    sessao = servico.iniciar("Suoming_DPS")
    eventos = _ouvir(servico, sessao.id)

    tela.apertar("F8")
    tela.proximo_print = CapturaFalhou("o jogo não está em primeiro plano")
    tela.apertar("F8")

    assert eventos[-1].tipo == "erro_captura"
    assert eventos[-1].motivo == "o jogo não está em primeiro plano"
    assert tela.sinais == ["ok", "erro"]


def test_sexto_print_vira_erro_de_captura(servico: ServicoCaptura, tela: TelaFalsa) -> None:
    sessao = servico.iniciar("Suoming_DPS")
    for _ in range(5):
        tela.apertar("F8")
    eventos = _ouvir(servico, sessao.id)

    tela.apertar("F8")

    assert eventos[-1].tipo == "erro_captura"
    assert "espaços de echo estão ocupados" in (eventos[-1].motivo or "")


def test_refazer_e_reordenar_avisam_o_novo_estado(servico: ServicoCaptura, tela: TelaFalsa) -> None:
    sessao = servico.iniciar("Suoming_DPS")
    tela.apertar("F8")
    tela.apertar("F8", b"borrado")
    eventos = _ouvir(servico, sessao.id)

    servico.reordenar(sessao.id, [1, 0, 2, 3, 4])
    servico.refazer(sessao.id, 0)
    tela.apertar("F8", b"echo")

    estado = servico.estado(sessao.id)
    assert [type(e) for e in estado.echos[:2]] == [EchoLido, EchoLido]
    assert _resumo(eventos)[:3] == [("estado", None), ("estado", None), ("estado", None)]


def test_leitura_de_print_ja_removido_e_descartada(tela: TelaFalsa, dados: GameData, tmp_path: Path) -> None:
    adiado = Adiado()
    servico = _servico(tela, dados, tmp_path, executar=adiado)
    sessao = servico.iniciar("Suoming_DPS")
    tela.apertar("F8")
    servico.esvaziar_echo(sessao.id, 0)
    eventos = _ouvir(servico, sessao.id)

    adiado.rodar()

    assert servico.estado(sessao.id).echos[0] == Vazio()
    assert _resumo(eventos) == [("estado", None)]


def test_leitura_de_sessao_antiga_nao_vaza_para_a_nova(tela: TelaFalsa, dados: GameData, tmp_path: Path) -> None:
    adiado = Adiado()
    servico = _servico(tela, dados, tmp_path, executar=adiado)
    servico.iniciar("Suoming_DPS")
    tela.apertar("F8")
    nova = servico.iniciar("Suoming_DPS")
    tela.apertar("F8", b"borrado")

    adiado.rodar()

    assert isinstance(servico.estado(nova.id).echos[0], Falhou)


def test_f10_avisa_a_pagina(servico: ServicoCaptura, tela: TelaFalsa) -> None:
    sessao = servico.iniciar("Suoming_DPS")
    eventos = _ouvir(servico, sessao.id)

    tela.apertar("F10")

    assert eventos[-1].tipo == "f10"


def test_parar_solta_os_atalhos_e_encerra_quem_esta_ouvindo(servico: ServicoCaptura, tela: TelaFalsa) -> None:
    sessao = servico.iniciar("Suoming_DPS")
    eventos = _ouvir(servico, sessao.id)

    servico.parar()

    assert tela.escutas[-1].parada
    assert eventos[-1].tipo == "encerrada"
    assert [e.tipo for e in _ouvir(servico, sessao.id)] == ["estado", "encerrada"]


def test_iniciar_outra_sessao_encerra_a_anterior(servico: ServicoCaptura) -> None:
    antiga = servico.iniciar("Suoming_DPS")

    servico.iniciar("Suoming_SubDPS")

    with pytest.raises(SessaoInexistente):
        servico.estado(antiga.id)


def test_sem_ia_configurada_nem_liga_os_atalhos(tela: TelaFalsa) -> None:
    def sem_ia() -> Extrator:
        raise ConfiguracaoAusente("defina NVIDIA_API_KEY")

    servico = ServicoCaptura(tela.ferramentas(), sem_ia, lambda tarefa: tarefa())

    with pytest.raises(ConfiguracaoAusente):
        servico.iniciar("Suoming_DPS")
    assert tela.escutas == []


def test_entrada_sem_echo_lido_e_recusada(servico: ServicoCaptura, tela: TelaFalsa, dados: GameData) -> None:
    sessao = servico.iniciar("Suoming_DPS")
    tela.apertar("F8", b"borrado")

    with pytest.raises(SemEchoLido):
        servico.entrada(sessao.id, dados.perfis.__getitem__)
