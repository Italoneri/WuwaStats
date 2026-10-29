"""Cache das respostas da IA por hash da imagem: os créditos gratuitos são limitados."""

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from wuwastats.vision.prompt import PROMPT_VERSAO

TipoPrint = Literal["echo", "personagem"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChaveCache:
    tipo: TipoPrint
    sha256: str
    modelo: str

    @property
    def caminho_relativo(self) -> Path:
        modelo = re.sub(r"[^A-Za-z0-9._-]+", "_", self.modelo)
        return Path(self.tipo) / f"{self.sha256}-{modelo}-v{PROMPT_VERSAO}.json"


@dataclass(frozen=True)
class CacheVisao:
    """Guarda a resposta bruta: melhorias no parser valem para respostas já em cache."""

    pasta: Path

    def ler(self, chave: ChaveCache) -> str | None:
        caminho = self.pasta / chave.caminho_relativo
        try:
            return json.loads(caminho.read_text(encoding="utf-8"))["resposta"]
        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, KeyError, TypeError) as erro:
            logger.warning("cache corrompido, ignorando", extra={"arquivo": str(caminho), "erro": str(erro)})
            return None

    def gravar(self, chave: ChaveCache, resposta: str) -> None:
        caminho = self.pasta / chave.caminho_relativo
        caminho.parent.mkdir(parents=True, exist_ok=True)
        registro = {
            "tipo": chave.tipo,
            "modelo": chave.modelo,
            "prompt_versao": PROMPT_VERSAO,
            "criado_em": datetime.now(UTC).isoformat(),
            "resposta": resposta,
        }
        temporario = caminho.with_suffix(".json.tmp")
        temporario.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporario, caminho)
