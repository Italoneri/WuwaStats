"""Kit oficial dos ressonadores (data/kits.json, gerado por scripts/importar_kits.py), resumos escritos à mão
(data/kit_resumos.json) e as imagens do kit (data/imagens/kit/<personagem>/<nome>.png)."""

import os
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from wuwastats.gamedata.imagens import PASTA_IMAGENS, nome_de_arquivo, normalizar_imagem
from wuwastats.gamedata.kit_texto import Paragrafo

ARQUIVO_KITS = "kits.json"
ARQUIVO_RESUMOS = "kit_resumos.json"
PASTA_KIT = "kit"


class _Modelo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class Multiplicador(_Modelo):
    nome: str
    valores: list[str]


class Habilidade(_Modelo):
    tipo: str
    nome: str
    imagem: str | None
    ilustracoes: list[str]
    descricao: list[Paragrafo]
    multiplicadores: list[Multiplicador]


class Sequencia(_Modelo):
    numero: int = Field(ge=1, le=6)
    nome: str
    imagem: str | None
    descricao: list[Paragrafo]


class Bonus(_Modelo):
    nome: str
    valor: str


class TagKit(_Modelo):
    nome: str
    descricao: str
    cor: str


class Kit(_Modelo):
    id_jogo: int
    tags: list[TagKit]
    habilidades: list[Habilidade]
    inerentes: list[Habilidade]
    bonus: list[Bonus]
    sequencias: list[Sequencia]


class KitsFile(_Modelo):
    meta: dict[str, str] = Field(alias="_meta")
    kits: dict[str, Kit]


class ResumosFile(_Modelo):
    meta: dict[str, str] = Field(alias="_meta")
    resumos: dict[str, str]


def ler_kit(data_dir: Path, chave: str) -> tuple[Kit, str | None] | None:
    """Kit e resumo do personagem; None se o kit não foi importado. Arquivo ausente conta como vazio."""
    kits = _ler(data_dir / ARQUIVO_KITS, KitsFile)
    kit = kits.kits.get(chave) if kits else None
    if kit is None:
        return None
    resumos = _ler(data_dir / ARQUIVO_RESUMOS, ResumosFile)
    return kit, resumos.resumos.get(chave) if resumos else None


def _ler[M: BaseModel](caminho: Path, modelo: type[M]) -> M | None:
    if not caminho.is_file():
        return None
    return modelo.model_validate_json(caminho.read_bytes())


@dataclass(frozen=True)
class ImagensDoKit:
    data_dir: Path

    def caminho(self, chave: str, nome: str) -> Path:
        return self.data_dir / PASTA_IMAGENS / PASTA_KIT / nome_de_arquivo(chave) / f"{nome_de_arquivo(nome)}.png"

    def existe(self, chave: str, nome: str) -> bool:
        return self.caminho(chave, nome).is_file()

    def salvar(self, chave: str, nome: str, conteudo: bytes) -> None:
        png = normalizar_imagem(conteudo)
        destino = self.caminho(chave, nome)
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporario = destino.with_suffix(".png.tmp")
        temporario.write_bytes(png)
        os.replace(temporario, destino)
