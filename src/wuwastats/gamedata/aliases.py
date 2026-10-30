"""Grava novos nomes em stat_aliases.json, para o dicionário se completar com o uso."""

import json
import os
from pathlib import Path

from wuwastats.domain.names import NameIndex, is_pct_flat_pair
from wuwastats.domain.report import CategoriaNome
from wuwastats.domain.tables import GameData

ARQUIVO_ALIASES = "stat_aliases.json"


class AliasInvalido(ValueError):
    pass


def registrar_alias(data_dir: Path, dados: GameData, categoria: CategoriaNome, chave: str, alias: str) -> None:
    """Idempotente: registrar o mesmo alias de novo não muda o arquivo."""
    _validar(_indice(dados, categoria), categoria, chave, alias)
    caminho = data_dir / ARQUIVO_ALIASES
    conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    existentes: list[str] = conteudo[categoria].setdefault(chave, [])
    if alias in existentes:
        return
    existentes.append(alias)
    escrever_atomico(caminho, conteudo)


def _indice(dados: GameData, categoria: CategoriaNome) -> NameIndex:
    indices = {"stats": dados.stat_names, "echoes": dados.echo_names, "sets": dados.set_names}
    return indices[categoria]


def _validar(indice: NameIndex, categoria: CategoriaNome, chave: str, alias: str) -> None:
    if not alias.strip():
        raise AliasInvalido("alias vazio")
    if chave not in indice.keys:
        raise AliasInvalido(f"'{chave}' não existe em {categoria}; cadastre no catálogo antes de mapear")
    outros = indice.candidates(alias) - {chave}
    if outros and not (categoria == "stats" and is_pct_flat_pair(outros | {chave})):
        raise AliasInvalido(f"'{alias}' já aponta para {sorted(outros)}")


def escrever_atomico(caminho: Path, conteudo: object) -> None:
    temporario = caminho.with_suffix(".json.tmp")
    temporario.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporario, caminho)
