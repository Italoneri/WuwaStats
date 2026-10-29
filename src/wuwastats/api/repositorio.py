"""Dados de jogo carregados na memória do servidor, recarregados quando os JSON mudam."""

from pathlib import Path
from threading import Lock

from wuwastats.domain.report import CategoriaNome
from wuwastats.domain.tables import GameData
from wuwastats.gamedata.aliases import registrar_alias
from wuwastats.gamedata.loader import load_game_data


class RepositorioDados:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._lock = Lock()
        self._dados = load_game_data(data_dir)

    @property
    def dados(self) -> GameData:
        return self._dados

    def recarregar(self) -> None:
        """Se os arquivos estiverem inválidos, levanta GameDataError e mantém os dados anteriores."""
        with self._lock:
            self._dados = load_game_data(self._data_dir)

    def registrar_alias(self, categoria: CategoriaNome, chave: str, alias: str) -> None:
        with self._lock:
            registrar_alias(self._data_dir, self._dados, categoria, chave, alias)
            self._dados = load_game_data(self._data_dir)
