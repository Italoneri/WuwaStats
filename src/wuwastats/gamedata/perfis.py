"""Edição de characters.json pela interface: valida com o loader, faz backup e grava de forma atômica.

O editor trabalha com chaves internas (crit_rate, Moonlit Clouds, Unspoken Rue): sem ambiguidade de idioma nem de
ATQ/ATQ%. Nomes que não resolvem ficam como estão, para o erro de validação apontar o campo.
"""

import json
import re
import shutil
import tempfile
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from wuwastats.domain.names import NameIndex, resolve_stat
from wuwastats.domain.tables import GameData
from wuwastats.gamedata.aliases import escrever_atomico
from wuwastats.gamedata.loader import load_game_data
from wuwastats.gamedata.schemas import ArmasPerfilRaw, PerfilRaw, VarianteRaw

ARQUIVO_PERFIS = "characters.json"
PASTA_BACKUPS = "backups"
CHAVE_VALIDA = re.compile(r"^[A-Za-z0-9][\w\-]{0,59}$")


class PerfilInexistente(LookupError):
    pass


class ChaveDeBuildInvalida(ValueError):
    pass


def perfis_editaveis(data_dir: Path, dados: GameData) -> dict[str, PerfilRaw]:
    brutos = _ler(data_dir)
    return {chave: _com_chaves(PerfilRaw.model_validate(raw), dados) for chave, raw in brutos.items()}


def salvar_perfil(data_dir: Path, chave: str, perfil: PerfilRaw) -> GameData:
    if not CHAVE_VALIDA.match(chave):
        raise ChaveDeBuildInvalida("a chave da build deve ter letras, números, '_' ou '-' (até 60), ex.: Suoming_DPS")
    perfis = _ler(data_dir)
    return _gravar(data_dir, perfis | {chave: _serializar(perfil)})


def apagar_perfil(data_dir: Path, chave: str) -> GameData:
    perfis = _ler(data_dir)
    if chave not in perfis:
        raise PerfilInexistente(f"build '{chave}' não existe em {ARQUIVO_PERFIS}")
    return _gravar(data_dir, {k: v for k, v in perfis.items() if k != chave})


def _ler(data_dir: Path) -> dict[str, Any]:
    return json.loads((data_dir / ARQUIVO_PERFIS).read_text(encoding="utf-8"))


def _gravar(data_dir: Path, perfis: Mapping[str, Any]) -> GameData:
    """Valida numa cópia dos JSON (GameDataError se inválido); só então faz backup e substitui o arquivo."""
    dados = _validar(data_dir, perfis)
    caminho = data_dir / ARQUIVO_PERFIS
    backups = data_dir / PASTA_BACKUPS
    backups.mkdir(exist_ok=True)
    shutil.copy2(caminho, backups / f"characters-{datetime.now():%Y%m%d-%H%M%S-%f}.json")
    escrever_atomico(caminho, perfis)
    return dados


def _validar(data_dir: Path, perfis: Mapping[str, Any]) -> GameData:
    with tempfile.TemporaryDirectory(prefix="wuwastats-perfis-") as temporario:
        copia = Path(temporario)
        for arquivo in data_dir.glob("*.json"):
            shutil.copy2(arquivo, copia / arquivo.name)
        escrever_atomico(copia / ARQUIVO_PERFIS, perfis)
        return load_game_data(copia)


def _serializar(perfil: PerfilRaw) -> dict[str, Any]:
    """'personagem' primeiro e sem campos vazios/padrão, como os perfis escritos à mão."""
    dump = perfil.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
    return {"personagem": dump.pop("personagem"), **dump}


def _com_chaves(perfil: PerfilRaw, dados: GameData) -> PerfilRaw:
    def stat(nome: str) -> str:
        return resolve_stat(dados.stat_names, nome) or nome

    def nome(indice: NameIndex, valor: str | None) -> str | None:
        return None if valor is None else indice.resolve(valor) or valor

    def principais(valores: Mapping[Any, list[str]] | None) -> dict[Any, list[str]] | None:
        return None if valores is None else {custo: [stat(n) for n in nomes] for custo, nomes in valores.items()}

    def estrelas(valores: Mapping[str, int] | None) -> dict[str, int] | None:
        return None if valores is None else {stat(n): quantas for n, quantas in valores.items()}

    def variante(v: VarianteRaw) -> VarianteRaw:
        return v.model_copy(
            update={
                "set": nome(dados.set_names, v.set),
                "echo_principal": nome(dados.echo_names, v.echo_principal),
                "principais": principais(v.principais),
                "estrelas": estrelas(v.estrelas),
            }
        )

    armas = perfil.armas
    return perfil.model_copy(
        update={
            "personagem": nome(dados.ressonador_names, perfil.personagem),
            "set": nome(dados.set_names, perfil.set),
            "echo_principal": nome(dados.echo_names, perfil.echo_principal),
            "principais": principais(perfil.principais),
            "estrelas": estrelas(perfil.estrelas),
            "armas_assinatura": list(dict.fromkeys(nome(dados.arma_names, a) or a for a in perfil.armas_assinatura)),
            "armas": None if armas is None else ArmasPerfilRaw(
                melhor=nome(dados.arma_names, armas.melhor),
                alternativas=[nome(dados.arma_names, a) or a for a in armas.alternativas],
                status=armas.status,
            ),
            "variantes": [variante(v) for v in perfil.variantes],
        }
    )

