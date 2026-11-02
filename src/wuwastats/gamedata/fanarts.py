"""Fanarts da tela do personagem com o crédito do artista: data/imagens/fanarts/<chave>.webp + <chave>.json.

A foto padrão (fundo transparente) da galeria continua em imagens.py; a fanart é maior e sempre leva crédito.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from wuwastats.gamedata.aliases import escrever_atomico
from wuwastats.gamedata.imagens import PASTA_IMAGENS, FormatoDeSaida, ImagemRecusada, nome_de_arquivo, normalizar_imagem

PASTA_FANARTS = "fanarts"
MAX_BYTES_FANART = 15 * 1024 * 1024
SAIDA_FANART = FormatoDeSaida(lado_maximo_px=1920, max_bytes=MAX_BYTES_FANART, formato="WEBP")


class Credito(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    artista: str = Field(min_length=1, max_length=80)
    link: str | None = Field(default=None, max_length=500)

    @field_validator("link", mode="before")
    @classmethod
    def _vazio_vira_none(cls, valor: object) -> object:
        return None if isinstance(valor, str) and not valor.strip() else valor

    @field_validator("link")
    @classmethod
    def _so_http(cls, valor: str | None) -> str | None:
        # O link vira href na página: só http(s), nunca javascript: ou data:
        if valor is None:
            return None
        partes = urlparse(valor)
        if partes.scheme not in {"http", "https"} or not partes.netloc:
            raise ValueError("o link precisa começar com http:// ou https://")
        return valor


class CreditoRecusado(ValueError):
    pass


def validar_credito(artista: str, link: str | None) -> Credito:
    try:
        return Credito(artista=artista, link=link)
    except ValidationError as erro:
        motivos = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in erro.errors())
        raise CreditoRecusado(f"crédito inválido ({motivos})") from erro


@dataclass(frozen=True)
class FanartsDoCatalogo:
    data_dir: Path

    @property
    def pasta(self) -> Path:
        return self.data_dir / PASTA_IMAGENS / PASTA_FANARTS

    def caminho(self, chave: str) -> Path:
        return self.pasta / f"{nome_de_arquivo(chave)}.webp"

    def existe(self, chave: str) -> bool:
        return self.caminho(chave).is_file()

    def credito(self, chave: str) -> Credito | None:
        arquivo = self.caminho(chave).with_suffix(".json")
        if not (self.existe(chave) and arquivo.is_file()):
            return None
        return Credito.model_validate_json(arquivo.read_text(encoding="utf-8"))

    def salvar(self, chave: str, conteudo: bytes | None, credito: Credito) -> None:
        """Sem `conteudo`, troca só o crédito de uma fanart que já existe."""
        if conteudo is None and not self.existe(chave):
            raise ImagemRecusada("envie a imagem da fanart")
        destino = self.caminho(chave)
        destino.parent.mkdir(parents=True, exist_ok=True)
        if conteudo is not None:
            webp = normalizar_imagem(conteudo, SAIDA_FANART)
            temporario = destino.with_suffix(".webp.tmp")
            temporario.write_bytes(webp)
            os.replace(temporario, destino)
        escrever_atomico(destino.with_suffix(".json"), credito.model_dump())
