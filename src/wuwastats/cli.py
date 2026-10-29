"""Linha de comando: validar dados, analisar uma entrada JSON e mapear nomes."""

import argparse
import io
import sys
from collections.abc import Callable
from pathlib import Path
from typing import get_args

from pydantic import ValidationError

from wuwastats.config import Settings
from wuwastats.domain.analyze import analisar
from wuwastats.domain.models import EntradaBuild
from wuwastats.domain.report import CategoriaNome
from wuwastats.domain.tables import GameData
from wuwastats.gamedata.aliases import AliasInvalido, registrar_alias
from wuwastats.gamedata.loader import GameDataError, load_game_data

Comando = Callable[[argparse.Namespace, GameData, Path], int]


def main(argv: list[str] | None = None) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    data_dir: Path = args.data_dir or Settings().data_dir
    try:
        dados = load_game_data(data_dir)
    except GameDataError as erro:
        _erro("Dados de jogo inválidos:", *erro.erros)
        return 1
    return COMANDOS[args.comando](args, dados, data_dir)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wuwastats", description="Analisador de echos de Wuthering Waves")
    parser.add_argument("--data-dir", type=Path, default=None, help="pasta dos JSON de jogo (padrão: ./data)")
    comandos = parser.add_subparsers(dest="comando", required=True)
    comandos.add_parser("check-data", help="valida os arquivos em data/")
    analyze = comandos.add_parser("analyze", help="analisa um JSON de entrada e imprime o relatório")
    analyze.add_argument("entrada", type=Path)
    alias = comandos.add_parser("alias", help="mapeia um nome lido para uma chave do dicionário")
    alias.add_argument("categoria", choices=get_args(CategoriaNome))
    alias.add_argument("chave", help="chave interna (ex.: 'Moonlit Clouds', 'crit_dmg')")
    alias.add_argument("alias", help="nome como aparece no jogo")
    return parser


def _check_data(_args: argparse.Namespace, dados: GameData, data_dir: Path) -> int:
    print(f"OK: {data_dir}")
    print(f"  {len(dados.substats)} substatus, {len(dados.sets)} sets, {len(dados.echoes)} echos, {len(dados.perfis)} builds")
    return 0


def _analyze(args: argparse.Namespace, dados: GameData, _data_dir: Path) -> int:
    try:
        entrada = EntradaBuild.model_validate_json(args.entrada.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as erro:
        _erro(f"Entrada inválida em {args.entrada}:", str(erro))
        return 1
    perfil = dados.perfis.get(entrada.build)
    if perfil is None:
        _erro(f"Build '{entrada.build}' não existe em characters.json.", f"Disponíveis: {', '.join(sorted(dados.perfis))}")
        return 1
    print(analisar(entrada, perfil, dados).model_dump_json(indent=2))
    return 0


def _alias(args: argparse.Namespace, dados: GameData, data_dir: Path) -> int:
    try:
        registrar_alias(data_dir, dados, args.categoria, args.chave, args.alias)
    except AliasInvalido as erro:
        _erro(str(erro))
        return 1
    print(f"'{args.alias}' -> {args.chave} ({args.categoria})")
    return 0


def _erro(*linhas: str) -> None:
    print("\n".join(linhas), file=sys.stderr)


COMANDOS: dict[str, Comando] = {"check-data": _check_data, "analyze": _analyze, "alias": _alias}

if __name__ == "__main__":
    sys.exit(main())
