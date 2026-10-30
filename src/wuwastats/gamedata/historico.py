"""Análises salvas pelo usuário (entrada corrigida + tela do personagem), em data/historico/<id>.json.

Guarda a entrada, não o resultado: ao reabrir, a análise roda de novo com os dados e pesos atuais.
O score e a nota do momento em que foi salva ficam só como resumo para a lista.
"""

import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from wuwastats.domain.models import EntradaBuild
from wuwastats.gamedata.aliases import escrever_atomico
from wuwastats.vision.parse import LeituraPersonagem

PASTA_HISTORICO = "historico"
ID_VALIDO = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{6}$")
MAX_NOME = 80

logger = logging.getLogger(__name__)


class AnaliseSalvaInexistente(LookupError):
    pass


class ResumoAnaliseSalva(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    nome: str = Field(max_length=MAX_NOME)
    build: str
    criado_em: datetime
    score_medio_pct: float = Field(description="Score médio quando foi salva (os pesos podem ter mudado desde então).")
    nota_media: str


class AnaliseSalva(ResumoAnaliseSalva):
    entrada: EntradaBuild
    leitura: LeituraPersonagem | None = None


class HistoricoAnalises:
    def __init__(self, data_dir: Path) -> None:
        self._pasta = data_dir / PASTA_HISTORICO

    def salvar(self, analise: AnaliseSalva) -> None:
        self._pasta.mkdir(parents=True, exist_ok=True)
        escrever_atomico(self._arquivo(analise.id), analise.model_dump(mode="json"))

    def listar(self, build: str | None = None) -> list[ResumoAnaliseSalva]:
        """Mais recentes primeiro. Arquivo corrompido é ignorado (com aviso no log), não derruba a lista."""
        if not self._pasta.is_dir():
            return []
        resumos = (self._resumo(arquivo) for arquivo in self._pasta.glob("*.json"))
        validos = [r for r in resumos if r is not None and (build is None or r.build == build)]
        return sorted(validos, key=lambda r: r.criado_em, reverse=True)

    def ler(self, analise_id: str) -> AnaliseSalva:
        arquivo = self._arquivo(analise_id)
        if not arquivo.is_file():
            raise AnaliseSalvaInexistente(f"análise salva '{analise_id}' não existe")
        return AnaliseSalva.model_validate_json(arquivo.read_text(encoding="utf-8"))

    def apagar(self, analise_id: str) -> None:
        arquivo = self._arquivo(analise_id)
        if not arquivo.is_file():
            raise AnaliseSalvaInexistente(f"análise salva '{analise_id}' não existe")
        arquivo.unlink()

    def _arquivo(self, analise_id: str) -> Path:
        if not ID_VALIDO.match(analise_id):
            raise AnaliseSalvaInexistente(f"id de análise inválido: '{analise_id}'")
        return self._pasta / f"{analise_id}.json"

    def _resumo(self, arquivo: Path) -> ResumoAnaliseSalva | None:
        try:
            return ResumoAnaliseSalva.model_validate(json.loads(arquivo.read_text(encoding="utf-8")))
        except (OSError, ValueError, ValidationError) as erro:
            logger.warning("histórico: %s ignorado: %s", arquivo.name, erro)
            return None


def novo_id(agora: datetime) -> str:
    return f"{agora:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
