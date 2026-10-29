import shutil
from pathlib import Path

import pytest

from wuwastats.config import PROJECT_ROOT
from wuwastats.domain.models import EchoEntrada, EntradaBuild
from wuwastats.domain.tables import GameData
from wuwastats.gamedata.loader import load_game_data

FIXTURES = PROJECT_ROOT / "fixtures"
GAMEDATA_FIXTURE = FIXTURES / "gamedata"


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
