"""Dados de jogo carregados na memória do servidor, recarregados quando os JSON mudam."""

from pathlib import Path
from threading import Lock

from wuwastats.domain.report import CategoriaNome
from wuwastats.domain.tables import GameData
from wuwastats.gamedata.aliases import registrar_alias
from wuwastats.gamedata.loader import load_game_data
from wuwastats.gamedata.perfis import apagar_perfil, perfis_editaveis, salvar_perfil
from wuwastats.gamedata.schemas import PerfilRaw


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

    def perfis_editaveis(self) -> dict[str, PerfilRaw]:
        return perfis_editaveis(self._data_dir, self._dados)

    def salvar_perfil(self, chave: str, perfil: PerfilRaw) -> None:
        """Perfil inválido levanta GameDataError e nada muda (nem o arquivo, nem os dados na memória)."""
        with self._lock:
            self._dados = salvar_perfil(self._data_dir, chave, perfil)

    def apagar_perfil(self, chave: str) -> None:
        with self._lock:
            self._dados = apagar_perfil(self._data_dir, chave)

    def registrar_alias(self, categoria: CategoriaNome, chave: str, alias: str) -> None:
        with self._lock:
            registrar_alias(self._data_dir, self._dados, categoria, chave, alias)
            self._dados = load_game_data(self._data_dir)
