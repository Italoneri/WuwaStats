import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from wuwastats.api.app import criar_app
from wuwastats.config import Settings
from wuwastats.conftest import FIXTURES
from wuwastats.vision.client import ConfiguracaoAusente, ModeloVisao
from wuwastats.vision.image import Imagem

ECHO_LIDO = {
    "nome": "Suhsin",
    "custo": 4,
    "set": "Nuvens ao Luar",
    "principal": {"stat": "Dano CRIT", "valor": "44%"},
    "substatus": [{"stat": "Taxa CRIT", "valor": "8,1%"}, {"stat": "Dano CRIT", "valor": "17,5%"}],
}


class ModeloFalso:
    nome = "modelo-falso"

    def completar(self, prompt: str, imagem: Imagem) -> str:
        respostas = {b"echo": json.dumps(ECHO_LIDO), b"tela": '{"arma": "Arma Teste", "regen_energia_total": 118.4}'}
        return respostas.get(imagem.conteudo, "não sei")


def _sem_ia(_settings: Settings) -> ModeloVisao:
    raise ConfiguracaoAusente("defina NVIDIA_API_KEY e NVIDIA_VISION_MODEL no .env (veja .env.example)")


@pytest.fixture
def settings(data_dir_copia: Path, tmp_path: Path) -> Settings:
    return Settings.model_validate({"data_dir": data_dir_copia, "cache_dir": tmp_path / "cache"})


@pytest.fixture
def cliente(settings: Settings) -> TestClient:
    return TestClient(criar_app(settings, fabrica_modelo=lambda _: ModeloFalso()))


@pytest.fixture
def entrada() -> dict[str, Any]:
    return json.loads((FIXTURES / "entradas" / "suoming_dps.json").read_text(encoding="utf-8"))


def test_lista_builds_com_condicoes_das_variantes(cliente: TestClient) -> None:
    builds = {b["chave"]: b for b in cliente.get("/api/builds").json()}

    assert builds["Suoming_DPS"]["condicoes"] == ["arma_assinatura"]
    assert builds["Suoming_DPS"]["variantes"][0]["set"] == "Heart of Sworn Vigil"
    assert builds["Suoming_SubDPS"]["condicoes"] == []


def test_catalogo_traz_rotulos_e_valores_discretos(cliente: TestClient) -> None:
    stats = {s["chave"]: s for s in cliente.get("/api/catalogo").json()["stats"]}

    assert stats["crit_dmg"]["nomes"][0] == "Dano CRIT"
    assert stats["crit_dmg"]["substatus"][-1] == 21.0
    assert stats["crit_dmg"]["principal"] == {"4": 44.0}
    assert stats["electro_dmg"]["substatus"] is None
    assert stats["atk_flat"]["percentual"] is False


def test_analisa_entrada_manual(cliente: TestClient, entrada: dict[str, Any]) -> None:
    resposta = cliente.post("/api/analisar", json=entrada)

    assert resposta.status_code == 200
    analise = resposta.json()
    assert [e["score_pct"] for e in analise["echos"]] == [80.4, 51.3, 37.0, 37.9, 6.3]
    assert analise["echos"][0]["substatus"][1]["tipo"] == "valido"


@pytest.mark.parametrize(
    ("mudanca", "status", "trecho"),
    [
        ({"build": "Ninguem"}, 404, "build 'Ninguem' não existe"),
        ({"echos": []}, 422, "echos"),
        ({"campo_extra": 1}, 422, "campo_extra"),
    ],
)
def test_erros_seguem_o_formato_do_contrato(
    cliente: TestClient, entrada: dict[str, Any], mudanca: dict[str, Any], status: int, trecho: str
) -> None:
    resposta = cliente.post("/api/analisar", json={**entrada, **mudanca})

    assert resposta.status_code == status
    corpo = resposta.json()
    assert set(corpo) == {"mensagem", "erros"}
    assert trecho in corpo["mensagem"] + " ".join(corpo["erros"])


def test_extrai_prints_e_ja_devolve_analise(cliente: TestClient) -> None:
    resposta = cliente.post(
        "/api/extrair",
        data={"build": "Suoming_DPS", "regen_externa": "0"},
        files=[
            ("echos", ("slot1.png", b"echo", "image/png")),
            ("echos", ("slot2.png", b"borrado", "image/png")),
            ("personagem", ("tela.png", b"tela", "image/png")),
        ],
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert [r["tipo"] for r in corpo["extracao"]["echos"]] == ["ok", "falhou"]
    assert corpo["extracao"]["entrada"]["condicoes"] == {"arma_assinatura": True}
    assert corpo["analise"]["conjunto"]["regen"]["informado"] == 118.4
    assert corpo["analise"]["nomes_desconhecidos"][0]["nome_lido"] == "Nuvens ao Luar"


def test_extrair_sem_ia_configurada_responde_503(settings: Settings) -> None:
    cliente = TestClient(criar_app(settings, fabrica_modelo=_sem_ia))

    resposta = cliente.post("/api/extrair", data={"build": "Suoming_DPS"}, files=[("echos", ("1.png", b"echo", "image/png"))])

    assert resposta.status_code == 503
    assert "NVIDIA_API_KEY" in resposta.json()["mensagem"]


def test_mapear_nome_grava_alias_e_vale_na_proxima_analise(
    cliente: TestClient, entrada: dict[str, Any], settings: Settings
) -> None:
    entrada["echos"][0]["set"] = "Nuvens ao Luar"
    antes = cliente.post("/api/analisar", json=entrada).json()

    mapeamento = cliente.post("/api/aliases", json={"categoria": "sets", "chave": "Moonlit Clouds", "alias": "Nuvens ao Luar"})
    depois = cliente.post("/api/analisar", json=entrada).json()

    assert antes["nomes_desconhecidos"][0]["nome_lido"] == "Nuvens ao Luar"
    assert mapeamento.status_code == 204
    assert depois["nomes_desconhecidos"] == []
    aliases = json.loads((settings.data_dir / "stat_aliases.json").read_text(encoding="utf-8"))
    assert "Nuvens ao Luar" in aliases["sets"]["Moonlit Clouds"]


def test_mapear_alias_conflitante_responde_422(cliente: TestClient) -> None:
    resposta = cliente.post("/api/aliases", json={"categoria": "stats", "chave": "crit_dmg", "alias": "Taxa CRIT"})

    assert resposta.status_code == 422
    assert "já aponta para" in resposta.json()["mensagem"]


def test_recarregar_dados_invalidos_mantem_os_anteriores(cliente: TestClient, settings: Settings) -> None:
    (settings.data_dir / "characters.json").write_text("{quebrado", encoding="utf-8")

    resposta = cliente.post("/api/dados/recarregar")

    assert resposta.status_code == 422
    assert "characters.json" in resposta.json()["erros"][0]
    assert cliente.get("/api/builds").status_code == 200


def test_serve_a_pagina_minima(cliente: TestClient) -> None:
    resposta = cliente.get("/")

    assert resposta.status_code == 200
    assert "WuwaStats" in resposta.text
