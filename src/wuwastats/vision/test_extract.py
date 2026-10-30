import io
import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx2
import pytest
from openai import APIConnectionError
from PIL import Image

from wuwastats.domain.models import Condicoes
from wuwastats.domain.tables import GameData
from wuwastats.vision.cache import CacheVisao
from wuwastats.vision.extract import (
    EchoExtraido,
    ExtracaoBuild,
    ExtracaoFalhou,
    Extrator,
    PedidoExtracao,
    PersonagemExtraido,
    extrair_build,
    separar_prints,
)
from wuwastats.vision.image import Imagem, carregar_imagem

ECHO_JSON = {
    "nome": "Suhsin",
    "custo": 4,
    "set": "Moonlit Clouds",
    "principal": {"stat": "Dano CRIT", "valor": 44, "percentual": True},
    "substatus": [{"stat": "Taxa CRIT", "valor": 8.1, "percentual": True}],
}
PERSONAGEM_JSON = {"personagem": "Suoming", "arma": "Test Weapon", "regen_energia_total": 131.2}


@dataclass
class ModeloFalso:
    """Responde pelo conteúdo da imagem; registra cada chamada para conferir o cache."""

    respostas: dict[bytes, str | Exception]
    nome: str = "modelo-falso"
    chamadas: list[bytes] = field(default_factory=list)

    def completar(self, prompt: str, imagem: Imagem) -> str:
        self.chamadas.append(imagem.conteudo)
        resposta = self.respostas[imagem.conteudo]
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


def _erro_de_conexao() -> APIConnectionError:
    return APIConnectionError(request=httpx2.Request("POST", "https://integrate.api.nvidia.com/v1/chat/completions"))


def _print(pasta: Path, nome: str, conteudo: bytes) -> Path:
    arquivo = pasta / nome
    arquivo.write_bytes(conteudo)
    return arquivo


@pytest.fixture
def cache(tmp_path: Path) -> CacheVisao:
    return CacheVisao(tmp_path / "cache")


class TestEcho:
    def test_le_echo_e_reaproveita_cache(self, tmp_path: Path, dados: GameData, cache: CacheVisao) -> None:
        modelo = ModeloFalso({b"echo-1": json.dumps(ECHO_JSON)})
        extrator = Extrator(modelo=modelo, cache=cache, dados=dados)
        arquivo = _print(tmp_path, "1.png", b"echo-1")

        primeiro, segundo = extrator.echo(arquivo), extrator.echo(arquivo)

        assert isinstance(primeiro, EchoExtraido) and isinstance(segundo, EchoExtraido)
        assert (primeiro.do_cache, segundo.do_cache) == (False, True)
        assert primeiro.echo == segundo.echo
        assert len(modelo.chamadas) == 1

    @pytest.mark.parametrize(
        ("substatus", "restantes"),
        [
            ([{"stat": "ATQ", "valor": 150, "percentual": False}, {"stat": "Taxa CRIT", "valor": 8.1}], ["Taxa CRIT"]),
            ([{"stat": "ATQ", "valor": 40, "percentual": False}, {"stat": "Taxa CRIT", "valor": 8.1}], ["ATQ", "Taxa CRIT"]),
            ([{"stat": "ATQ%", "valor": 150}, {"stat": "Taxa CRIT", "valor": 8.1}], ["ATQ%", "Taxa CRIT"]),
        ],
    )
    def test_tira_o_status_fixo_secundario_lido_como_substatus(
        self, tmp_path: Path, dados: GameData, cache: CacheVisao, substatus: list[dict[str, object]], restantes: list[str]
    ) -> None:
        modelo = ModeloFalso({b"echo-1": json.dumps(ECHO_JSON | {"substatus": substatus})})

        resultado = Extrator(modelo=modelo, cache=cache, dados=dados).echo(_print(tmp_path, "1.png", b"echo-1"))

        assert isinstance(resultado, EchoExtraido)
        assert [s.stat for s in resultado.echo.substatus] == restantes

    def test_cache_separa_modelos_diferentes(self, tmp_path: Path, dados: GameData, cache: CacheVisao) -> None:
        arquivo = _print(tmp_path, "1.png", b"echo-1")
        respostas: dict[bytes, str | Exception] = {b"echo-1": json.dumps(ECHO_JSON)}
        Extrator(modelo=ModeloFalso(respostas, nome="a"), cache=cache, dados=dados).echo(arquivo)

        resultado = Extrator(modelo=ModeloFalso(respostas, nome="b"), cache=cache, dados=dados).echo(arquivo)

        assert resultado.do_cache is False

    def test_resposta_malformada_falha_sem_quebrar_e_fica_em_cache(
        self, tmp_path: Path, dados: GameData, cache: CacheVisao
    ) -> None:
        modelo = ModeloFalso({b"borrado": "Não consegui ler."})
        extrator = Extrator(modelo=modelo, cache=cache, dados=dados)
        arquivo = _print(tmp_path, "1.png", b"borrado")

        resultado = extrator.echo(arquivo)
        extrator.echo(arquivo)

        assert isinstance(resultado, ExtracaoFalhou)
        assert resultado.resposta_bruta == "Não consegui ler."
        assert len(modelo.chamadas) == 1

    def test_erro_da_api_falha_sem_gravar_cache(self, tmp_path: Path, dados: GameData, cache: CacheVisao) -> None:
        modelo = ModeloFalso({b"echo-1": _erro_de_conexao()})
        extrator = Extrator(modelo=modelo, cache=cache, dados=dados)
        arquivo = _print(tmp_path, "1.png", b"echo-1")

        resultado = extrator.echo(arquivo)
        extrator.echo(arquivo)

        assert isinstance(resultado, ExtracaoFalhou)
        assert resultado.motivo.startswith("API de visão")
        assert len(modelo.chamadas) == 2

    def test_formato_de_imagem_nao_suportado_falha(self, tmp_path: Path, dados: GameData, cache: CacheVisao) -> None:
        extrator = Extrator(modelo=ModeloFalso({}), cache=cache, dados=dados)

        resultado = extrator.echo(_print(tmp_path, "print.gif", b"gif"))

        assert isinstance(resultado, ExtracaoFalhou)
        assert "formato não suportado" in resultado.motivo

    def test_cache_corrompido_e_ignorado(self, tmp_path: Path, dados: GameData, cache: CacheVisao) -> None:
        modelo = ModeloFalso({b"echo-1": json.dumps(ECHO_JSON)})
        extrator = Extrator(modelo=modelo, cache=cache, dados=dados)
        arquivo = _print(tmp_path, "1.png", b"echo-1")
        extrator.echo(arquivo)
        for gravado in cache.pasta.rglob("*.json"):
            gravado.write_text("{corrompido", encoding="utf-8")

        resultado = extrator.echo(arquivo)

        assert isinstance(resultado, EchoExtraido)
        assert len(modelo.chamadas) == 2


class TestBuild:
    def _extrair(
        self, tmp_path: Path, dados: GameData, cache: CacheVisao, condicoes: Condicoes | None = None
    ) -> ExtracaoBuild:
        modelo = ModeloFalso(
            {
                b"echo-1": json.dumps(ECHO_JSON),
                b"echo-2": "sem json",
                b"tela": json.dumps(PERSONAGEM_JSON),
            }
        )
        pedido = PedidoExtracao(
            build="Suoming_DPS",
            prints_echo=(_print(tmp_path, "1.png", b"echo-1"), _print(tmp_path, "2.png", b"echo-2")),
            print_personagem=_print(tmp_path, "personagem.png", b"tela"),
            condicoes=condicoes or Condicoes(),
            regen_externa=12.8,
        )
        extrator = Extrator(modelo=modelo, cache=cache, dados=dados)
        return extrair_build(extrator, pedido, dados.perfis["Suoming_DPS"], concorrencia=2)

    def test_monta_entrada_com_echos_lidos_e_lista_falhas(
        self, tmp_path: Path, dados: GameData, cache: CacheVisao
    ) -> None:
        extracao = self._extrair(tmp_path, dados, cache)

        assert extracao.entrada is not None
        assert [e.nome for e in extracao.entrada.echos] == ["Suhsin"]
        assert [r.tipo for r in extracao.echos] == ["ok", "falhou"]
        assert extracao.entrada.regen_externa == 12.8

    def test_detecta_arma_assinatura_e_regen_pela_tela_do_personagem(
        self, tmp_path: Path, dados: GameData, cache: CacheVisao
    ) -> None:
        extracao = self._extrair(tmp_path, dados, cache)

        assert isinstance(extracao.personagem, PersonagemExtraido)
        assert extracao.entrada is not None
        assert extracao.entrada.condicoes.arma_assinatura is True
        assert extracao.entrada.regen_total_informado == 131.2

    def test_condicao_informada_pelo_usuario_prevalece(
        self, tmp_path: Path, dados: GameData, cache: CacheVisao
    ) -> None:
        extracao = self._extrair(tmp_path, dados, cache, Condicoes(arma_assinatura=False))

        assert extracao.entrada is not None
        assert extracao.entrada.condicoes.arma_assinatura is False

    def test_rejeita_mais_de_cinco_echos(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="de 1 a 5"):
            PedidoExtracao(build="x", prints_echo=tuple(tmp_path / f"{i}.png" for i in range(6)))


def test_separa_print_do_personagem_e_ordena_echos(tmp_path: Path) -> None:
    for nome in ["2.png", "1.jpg", "Personagem.png", "notas.txt"]:
        _print(tmp_path, nome, b"x")

    echos, personagem = separar_prints(tmp_path)

    assert [e.name for e in echos] == ["1.jpg", "2.png"]
    assert personagem is not None and personagem.name == "Personagem.png"


def test_recorta_painel_do_echo(tmp_path: Path) -> None:
    arquivo = tmp_path / "echo.png"
    Image.new("RGB", (200, 100), "white").save(arquivo)

    imagem = carregar_imagem(arquivo, (0.5, 0.0, 1.0, 0.5))

    with Image.open(io.BytesIO(imagem.conteudo)) as recortada:
        assert recortada.size == (100, 50)
