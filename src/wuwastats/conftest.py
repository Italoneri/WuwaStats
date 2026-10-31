import shutil
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from wuwastats.captura.servico import CapturaFalhou, FerramentasCaptura, Sinal
from wuwastats.captura.teclas import Acao
from wuwastats.config import PROJECT_ROOT, Settings
from wuwastats.domain.models import EchoEntrada, EntradaBuild
from wuwastats.domain.tables import GameData
from wuwastats.gamedata.loader import load_game_data

FIXTURES = PROJECT_ROOT / "fixtures"
GAMEDATA_FIXTURE = FIXTURES / "gamedata"


@pytest.fixture(autouse=True)
def sem_env_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """O .env de quem roda os testes (recorte, modelo, limites) não pode mudar o resultado."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)


@pytest.fixture(autouse=True)
def temporarios_no_tmp_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Sessão de captura que o teste não desliga deixaria a pasta dos prints no Temp do sistema a cada execução."""
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))


@pytest.fixture(scope="session")
def dados() -> GameData:
    return load_game_data(GAMEDATA_FIXTURE)


@pytest.fixture
def data_dir_copia(tmp_path: Path) -> Path:
    """Cópia descartável dos dados, para testes que editam ou quebram arquivos."""
    destino = tmp_path / "data"
    shutil.copytree(GAMEDATA_FIXTURE, destino)
    return destino


@pytest.fixture
def entrada_suoming() -> EntradaBuild:
    texto = (FIXTURES / "entradas" / "suoming_dps.json").read_text(encoding="utf-8")
    return EntradaBuild.model_validate_json(texto)


def com_echo(entrada: EntradaBuild, indice: int, **campos: object) -> EntradaBuild:
    """Copia a entrada trocando campos (em formato JSON) de um echo."""
    echo = EchoEntrada.model_validate(entrada.echos[indice].model_dump() | campos)
    echos = (*entrada.echos[:indice], echo, *entrada.echos[indice + 1 :])
    return entrada.model_copy(update={"echos": echos})


@dataclass
class EscutaFalsa:
    acoes: Mapping[Acao, Callable[[], None]]
    parada: bool = False

    def parar(self) -> None:
        self.parada = True


@dataclass
class TelaFalsa:
    """Faz o papel do jogo: 'proximo_print' é o que o atalho vai capturar; apertar() simula a tecla da ação."""

    proximo_print: bytes | CapturaFalhou = b"echo"
    sinais: list[Sinal] = field(default_factory=list)
    escutas: list[EscutaFalsa] = field(default_factory=list)

    def ferramentas(self) -> FerramentasCaptura:
        return FerramentasCaptura(capturar_tela=self._capturar, escutar_atalhos=self._escutar, sinalizar=self.sinais.append)

    def apertar(self, acao: Acao, print_: bytes | None = None) -> None:
        if print_ is not None:
            self.proximo_print = print_
        self.escutas[-1].acoes[acao]()

    def _capturar(self) -> bytes:
        if isinstance(self.proximo_print, CapturaFalhou):
            raise self.proximo_print
        return self.proximo_print

    def _escutar(self, acoes: Mapping[Acao, Callable[[], None]]) -> EscutaFalsa:
        self.escutas.append(EscutaFalsa(acoes))
        return self.escutas[-1]


@pytest.fixture
def tela() -> TelaFalsa:
    return TelaFalsa()
