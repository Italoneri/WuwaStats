import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from wuwastats.api.app import criar_app
from wuwastats.config import Settings
from wuwastats.conftest import FIXTURES, TelaFalsa
from wuwastats.gamedata.test_imagens import imagem
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
def cliente(settings: Settings, tela: TelaFalsa) -> TestClient:
    return TestClient(criar_app(settings, fabrica_modelo=lambda _: ModeloFalso(), ferramentas_captura=tela.ferramentas()))


@pytest.fixture
def entrada() -> dict[str, Any]:
    return json.loads((FIXTURES / "entradas" / "suoming_dps.json").read_text(encoding="utf-8"))


def test_lista_builds_com_condicoes_das_variantes_e_explicacao(cliente: TestClient) -> None:
    builds = {b["chave"]: b for b in cliente.get("/api/builds").json()}

    assert builds["Suoming_DPS"]["condicoes"] == ["arma_assinatura"]
    assert builds["Suoming_DPS"]["variantes"][0]["perfil"]["sets"] == {"Heart of Sworn Vigil": 5}
    assert builds["Suoming_DPS"]["variantes"][0]["perfil"]["estrelas"] == builds["Suoming_DPS"]["base"]["estrelas"]
    assert builds["Suoming_DPS"]["armas"] == {"melhor": "Test Weapon", "alternativas": ["Alt Weapon"]}
    assert builds["Suoming_SubDPS"]["condicoes"] == []
    assert builds["Suoming_SubDPS"]["armas"] is None
    assert builds["Suoming_DPS"]["descricao"] == "DPS **Electro** de Ataque Básico."
    assert builds["Suoming_SubDPS"]["descricao"] is None


def test_lista_todos_os_personagens_e_indica_quem_tem_perfil(cliente: TestClient) -> None:
    personagens = {p["chave"]: p for p in cliente.get("/api/personagens").json()}

    assert personagens["Suoming"]["builds"] == ["Suoming_DPS", "Suoming_SubDPS"]
    assert personagens["Suoming"]["tem_perfil"] is True
    assert personagens["Suoming"]["elemento"] == {"chave": "electro", "nome": "Voltaico"}
    assert personagens["Shorekeeper"] == {
        "chave": "Shorekeeper",
        "nome": "Guardiã da Costa",
        "elemento": {"chave": "glacio", "nome": "Criogênico"},
        "tipo_arma": {"chave": "rectifier", "nome": "Retificador"},
        "raridade": 4,
        "builds": [],
        "tem_perfil": False,
    }


def test_catalogo_traz_rotulos_e_valores_discretos(cliente: TestClient) -> None:
    stats = {s["chave"]: s for s in cliente.get("/api/catalogo").json()["stats"]}

    assert stats["crit_dmg"]["nomes"][0] == "Dano CRIT"
    assert stats["crit_dmg"]["substatus"][-1] == 21.0
    assert stats["crit_dmg"]["principal"] == {"4": 44.0}
    assert stats["electro_dmg"]["substatus"] is None
    assert stats["atk_flat"]["percentual"] is False
    armas = {a["chave"]: a for a in cliente.get("/api/catalogo").json()["armas"]}
    assert armas["Test Weapon"] == {"chave": "Test Weapon", "nomes": ["Arma Teste"], "tipo": "sword", "raridade": 5}


def test_lista_echoes_com_sets_e_o_que_a_habilidade_faz(cliente: TestClient) -> None:
    echoes = {e["chave"]: e for e in cliente.get("/api/echoes").json()}

    assert echoes["Suhsin"] == {
        "chave": "Suhsin",
        "nome": "Suhsin",
        "custo": None,
        "sets": [{"chave": "Moonlit Clouds", "nome": "Moonlit Clouds"}],
        "habilidade": "Convoca Suhsin, causando 50% de dano elétrico.",
    }
    assert echoes["Soulfrayer"]["habilidade"] is None


def test_analisa_entrada_manual(cliente: TestClient, entrada: dict[str, Any]) -> None:
    resposta = cliente.post("/api/analisar", json=entrada)

    assert resposta.status_code == 200
    analise = resposta.json()
    assert [e["score_pct"] for e in analise["echos"]] == [80.4, 54.5, 35.5, 39.3, 5.6]
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


def test_extrair_sem_ia_configurada_responde_503(settings: Settings, tela: TelaFalsa) -> None:
    cliente = TestClient(criar_app(settings, fabrica_modelo=_sem_ia, ferramentas_captura=tela.ferramentas()))

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


class TestCaptura:
    def _esperar(self, cliente: TestClient, sessao: str, pronto: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
        """A leitura roda no pool do app: espera o estado chegar onde o teste precisa."""
        limite = time.monotonic() + 5
        estado: dict[str, Any] = cliente.get(f"/api/captura/{sessao}").json()
        while not pronto(estado):
            if time.monotonic() > limite:
                raise AssertionError(f"estado não chegou ao esperado: {estado}")
            time.sleep(0.02)
            estado = cliente.get(f"/api/captura/{sessao}").json()
        return estado

    def _iniciar(self, cliente: TestClient) -> str:
        resposta = cliente.post("/api/captura/iniciar", json={"build": "Suoming_DPS"})
        assert resposta.status_code == 200
        return resposta.json()["id"]

    def test_fluxo_completo_monta_a_entrada_na_ordem_dos_espacos(self, cliente: TestClient, tela: TelaFalsa) -> None:
        sessao = self._iniciar(cliente)
        tela.apertar("echo", b"echo")
        tela.apertar("echo", b"lixo")
        tela.apertar("personagem", b"tela")
        self._esperar(cliente, sessao, lambda e: e["echos"][1]["estado"] == "falhou" and e["personagem"]["estado"] == "lido")

        reordenado = cliente.post(f"/api/captura/{sessao}/reordenar", json={"ordem": [1, 0, 2, 3, 4]}).json()
        refazer = cliente.post(f"/api/captura/{sessao}/echos/0/refazer").json()
        tela.apertar("echo", b"echo")
        estado = self._esperar(cliente, sessao, lambda e: e["echos"][0]["estado"] == "lido")
        entrada = cliente.get(f"/api/captura/{sessao}/entrada").json()

        assert [e["estado"] for e in reordenado["echos"][:2]] == ["falhou", "lido"]
        assert refazer["alvo_f8"] == 0
        assert [e["estado"] for e in estado["echos"]] == ["lido", "lido", "vazio", "vazio", "vazio"]
        assert len(entrada["echos"]) == 2
        assert entrada["condicoes"] == {"arma_assinatura": True}
        assert entrada["regen_total_informado"] == 118.4

    def test_serve_a_imagem_do_espaco(self, cliente: TestClient, tela: TelaFalsa) -> None:
        sessao = self._iniciar(cliente)
        tela.apertar("echo", b"echo")

        imagem = cliente.get(f"/api/captura/{sessao}/imagens/0")
        vazio = cliente.get(f"/api/captura/{sessao}/imagens/personagem")
        invalido = cliente.get(f"/api/captura/{sessao}/imagens/../../.env")

        assert (imagem.status_code, imagem.content, imagem.headers["content-type"]) == (200, b"echo", "image/png")
        assert vazio.status_code == 404
        assert invalido.status_code == 404

    def test_esvaziar_espacos(self, cliente: TestClient, tela: TelaFalsa) -> None:
        sessao = self._iniciar(cliente)
        tela.apertar("echo", b"echo")
        tela.apertar("personagem", b"tela")

        cliente.delete(f"/api/captura/{sessao}/echos/0")
        estado = cliente.delete(f"/api/captura/{sessao}/personagem").json()

        assert (estado["echos"][0]["estado"], estado["personagem"]["estado"]) == ("vazio", "vazio")

    def test_eventos_de_sessao_encerrada_trazem_estado_e_fecham(self, cliente: TestClient) -> None:
        sessao = self._iniciar(cliente)
        assert cliente.post("/api/captura/parar").status_code == 204

        resposta = cliente.get(f"/api/captura/{sessao}/eventos")

        assert resposta.headers["content-type"].startswith("text/event-stream")
        mensagens = [m for m in resposta.text.split("\n\n") if m]
        assert [m.splitlines()[0] for m in mensagens] == ["event: estado", "event: encerrada"]
        assert json.loads(mensagens[0].splitlines()[1].removeprefix("data: "))["sessao"]["id"] == sessao

    @pytest.mark.parametrize(
        ("metodo", "caminho", "corpo", "status", "trecho"),
        [
            ("post", "/api/captura/iniciar", {"build": "Ninguem"}, 404, "build 'Ninguem' não existe"),
            ("get", "/api/captura/nao-existe", None, 404, "sessão de captura 'nao-existe' não existe"),
            ("post", "/api/captura/{sessao}/reordenar", {"ordem": [0, 0, 1, 2, 3]}, 422, "permutação"),
            ("delete", "/api/captura/{sessao}/echos/5", None, 422, "indice"),
            ("get", "/api/captura/{sessao}/entrada", None, 409, "nenhum echo foi lido"),
        ],
    )
    def test_erros(
        self, cliente: TestClient, metodo: str, caminho: str, corpo: dict[str, Any] | None, status: int, trecho: str
    ) -> None:
        sessao = self._iniciar(cliente)

        resposta = cliente.request(metodo, caminho.format(sessao=sessao), json=corpo)

        assert resposta.status_code == status
        assert trecho in json.dumps(resposta.json(), ensure_ascii=False)

    def test_iniciar_sem_ia_configurada_responde_503(self, settings: Settings, tela: TelaFalsa) -> None:
        cliente = TestClient(criar_app(settings, fabrica_modelo=_sem_ia, ferramentas_captura=tela.ferramentas()))

        resposta = cliente.post("/api/captura/iniciar", json={"build": "Suoming_DPS"})

        assert resposta.status_code == 503
        assert tela.escutas == []


class TestImagens:
    def test_envia_lista_e_serve_a_imagem(self, cliente: TestClient) -> None:
        png = imagem("JPEG")

        envio = cliente.put("/api/imagens/personagens/Suoming", files={"arquivo": ("s.jpg", png, "image/jpeg")})
        lista = cliente.get("/api/imagens").json()
        servida = cliente.get("/api/imagens/personagens/Suoming")

        assert envio.status_code == 204
        assert lista == {"personagens": ["Suoming"], "echoes": [], "armas": [], "sets": []}
        assert (servida.status_code, servida.headers["content-type"]) == (200, "image/png")
        assert servida.content.startswith(b"\x89PNG")

    @pytest.mark.parametrize(
        ("metodo", "caminho", "arquivo", "status"),
        [
            ("get", "/api/imagens/personagens/Suoming", None, 404),
            ("put", "/api/imagens/personagens/Ninguem", imagem("PNG"), 404),
            ("put", "/api/imagens/sonatas/Moonlit Clouds", imagem("PNG"), 422),
            ("put", "/api/imagens/armas/Test Weapon", b"texto", 422),
        ],
    )
    def test_erros(self, cliente: TestClient, metodo: str, caminho: str, arquivo: bytes | None, status: int) -> None:
        arquivos = {"arquivo": ("a.png", arquivo, "image/png")} if arquivo is not None else None

        assert cliente.request(metodo, caminho, files=arquivos).status_code == status


class TestHistorico:
    def test_salva_lista_reabre_e_apaga(self, cliente: TestClient, entrada: dict[str, Any]) -> None:
        leitura = {"personagem": "Suoming", "arma": "Arma Teste", "atributos": []}

        salvo = cliente.post("/api/historico", json={"nome": "antes da troca", "entrada": entrada, "leitura": leitura})
        resumo = salvo.json()
        lista = cliente.get("/api/historico", params={"build": "Suoming_DPS"}).json()
        outra_build = cliente.get("/api/historico", params={"build": "Suoming_SubDPS"}).json()
        completo = cliente.get(f"/api/historico/{resumo['id']}").json()
        apagado = cliente.delete(f"/api/historico/{resumo['id']}")

        assert salvo.status_code == 201
        assert (resumo["nome"], resumo["build"]) == ("antes da troca", "Suoming_DPS")
        assert (resumo["score_medio_pct"], resumo["nota_media"]) == (43.1, "B")
        assert [r["id"] for r in lista] == [resumo["id"]]
        assert outra_build == []
        assert completo["entrada"]["echos"][0]["nome"] == entrada["echos"][0]["nome"]
        assert completo["leitura"]["arma"] == "Arma Teste"
        assert apagado.status_code == 204
        assert cliente.get(f"/api/historico/{resumo['id']}").status_code == 404

    def test_nome_vazio_vira_build_com_data(self, cliente: TestClient, entrada: dict[str, Any]) -> None:
        resumo = cliente.post("/api/historico", json={"entrada": entrada}).json()

        assert resumo["nome"].startswith("Suoming_DPS · ")

    @pytest.mark.parametrize("analise_id", ["..%2F..%2F.env", "20261030-120000-zzzzzz", "nao-existe"])
    def test_id_invalido_ou_inexistente_responde_404(self, cliente: TestClient, analise_id: str) -> None:
        assert cliente.get(f"/api/historico/{analise_id}").status_code == 404

    def test_build_inexistente_nao_e_salva(self, cliente: TestClient, entrada: dict[str, Any]) -> None:
        resposta = cliente.post("/api/historico", json={"entrada": entrada | {"build": "Ninguem"}})

        assert resposta.status_code == 404
        assert cliente.get("/api/historico").json() == []


class TestEditorDeBuilds:
    def _perfil(self, cliente: TestClient, chave: str = "Suoming_DPS") -> dict[str, Any]:
        return cliente.get("/api/perfis").json()[chave]

    def test_lista_perfis_com_chaves_internas(self, cliente: TestClient) -> None:
        perfil = self._perfil(cliente)

        assert perfil["estrelas"]["crit_rate"] == 3
        assert perfil["principais"]["3"] == ["electro_dmg", "atk_pct"]
        assert perfil["armas"]["alternativas"] == ["Alt Weapon"]
        assert perfil["armas_assinatura"] == ["Test Weapon"]
        assert perfil["variantes"][1] == {"condicao": {"arma_assinatura": False}, "sets": {"Moonlit Clouds": 5}}

    def test_salva_faz_backup_e_recarrega(self, cliente: TestClient, settings: Settings) -> None:
        perfil = self._perfil(cliente) | {"metas": [{"stat": "energy_regen", "min": 125, "tipo": "rotacao", "fonte": "game8"}]}

        resposta = cliente.put("/api/perfis/Suoming_DPS", json=perfil)

        assert resposta.status_code == 200
        builds = {b["chave"]: b for b in cliente.get("/api/builds").json()}
        assert builds["Suoming_DPS"]["base"]["metas"][0]["min"] == 125
        assert len(list((settings.data_dir / "backups").glob("characters-*.json"))) == 1
        gravado = json.loads((settings.data_dir / "characters.json").read_text(encoding="utf-8"))
        assert next(iter(gravado["Suoming_DPS"])) == "personagem"

    def test_perfil_salvo_pelo_editor_ainda_detecta_a_arma_pelo_nome_pt(self, cliente: TestClient) -> None:
        cliente.put("/api/perfis/Suoming_DPS", json=self._perfil(cliente))

        resposta = cliente.post(
            "/api/extrair",
            data={"build": "Suoming_DPS"},
            files=[("echos", ("1.png", b"echo", "image/png")), ("personagem", ("tela.png", b"tela", "image/png"))],
        )

        assert resposta.json()["extracao"]["entrada"]["condicoes"] == {"arma_assinatura": True}

    @pytest.mark.parametrize(
        ("mudanca", "trecho"),
        [
            ({"estrelas": {"Sorte": 3}}, "characters.json › Suoming_DPS › estrelas › Sorte"),
            ({"sets": {"Set Inexistente": 5}}, "characters.json › Suoming_DPS › sets › Set Inexistente"),
            ({"metas": [{"stat": "energy_regen", "min": 50, "tipo": "rotacao", "fonte": "game8"}]}, "body › metas › 0"),
            ({"regen_energia_min": 120}, "body › regen_energia_min"),
            ({"custos": [4, 4, 4, 1, 1]}, "custo total 14"),
        ],
    )
    def test_perfil_invalido_responde_422_e_nao_grava(
        self, cliente: TestClient, settings: Settings, mudanca: dict[str, Any], trecho: str
    ) -> None:
        antes = (settings.data_dir / "characters.json").read_bytes()

        resposta = cliente.put("/api/perfis/Suoming_DPS", json=self._perfil(cliente) | mudanca)

        assert resposta.status_code == 422
        assert any(trecho in erro for erro in resposta.json()["erros"])
        assert (settings.data_dir / "characters.json").read_bytes() == antes

    def test_cria_e_apaga_build(self, cliente: TestClient) -> None:
        nova = self._perfil(cliente, "Suoming_SubDPS") | {"metas": []}

        criada = cliente.put("/api/perfis/Suoming_Teste", json=nova)
        apagada = cliente.delete("/api/perfis/Suoming_Teste")

        assert criada.status_code == 200
        assert apagada.status_code == 204
        assert "Suoming_Teste" not in cliente.get("/api/perfis").json()
        assert cliente.delete("/api/perfis/Suoming_Teste").status_code == 404

    def test_chave_invalida_e_recusada(self, cliente: TestClient) -> None:
        resposta = cliente.put("/api/perfis/build com espaço", json=self._perfil(cliente))

        assert resposta.status_code == 422


def test_pagina_pede_revalidacao_para_nao_usar_js_antigo(cliente: TestClient) -> None:
    assert cliente.get("/comum.js").headers["cache-control"] == "no-cache"
    assert cliente.get("/api/health").headers.get("cache-control") is None
