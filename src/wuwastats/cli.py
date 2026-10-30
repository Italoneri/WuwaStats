"""Linha de comando: validar dados, extrair echos de prints, analisar e mapear nomes."""

import argparse
import io
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import get_args

import uvicorn
from pydantic import ValidationError

from wuwastats.api.app import criar_app
from wuwastats.config import Settings
from wuwastats.domain.analyze import analisar
from wuwastats.domain.models import Condicoes, EntradaBuild
from wuwastats.domain.report import CategoriaNome
from wuwastats.domain.tables import GameData
from wuwastats.domain.variants import resolver_build
from wuwastats.gamedata.aliases import AliasInvalido, registrar_alias
from wuwastats.gamedata.loader import GameDataError, load_game_data
from wuwastats.vision.cache import CacheVisao
from wuwastats.vision.client import ConfiguracaoAusente, criar_modelo_nvidia
from wuwastats.vision.extract import ExtracaoBuild, Extrator, PedidoExtracao, extrair_build, separar_prints

Comando = Callable[[argparse.Namespace, GameData, Settings], int]

RESPOSTA_ARMA = {"sim": True, "nao": False}


def main(argv: list[str] | None = None) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("wuwastats").setLevel(logging.INFO)  # eventos de negócio: captura iniciada, tempo de cada leitura
    args = _parser().parse_args(argv)
    settings = Settings()
    if args.data_dir:
        settings = settings.model_copy(update={"data_dir": args.data_dir})
    try:
        dados = load_game_data(settings.data_dir)
    except GameDataError as erro:
        _erro("Dados de jogo inválidos:", *erro.erros)
        return 1
    return COMANDOS[args.comando](args, dados, settings)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wuwastats", description="Analisador de echos de Wuthering Waves")
    parser.add_argument("--data-dir", type=Path, default=None, help="pasta dos JSON de jogo (padrão: ./data)")
    comandos = parser.add_subparsers(dest="comando", required=True)

    comandos.add_parser("check-data", help="valida os arquivos em data/")

    analyze = comandos.add_parser("analyze", help="analisa um JSON de entrada e imprime o relatório")
    analyze.add_argument("entrada", type=Path)

    extract = comandos.add_parser("extract", help="lê os prints de uma pasta com a IA de visão e gera o JSON de entrada")
    extract.add_argument("pasta", type=Path, help="prints dos echos (ordem alfabética; o 1º é o principal)")
    extract.add_argument("--build", required=True, help="chave em characters.json (ex.: Suoming_DPS)")
    extract.add_argument("--personagem", type=Path, help="print da tela do personagem (padrão: arquivo 'personagem*' na pasta)")
    extract.add_argument("--arma-assinatura", choices=list(RESPOSTA_ARMA), help="sobrescreve o que for detectado no print")
    extract.add_argument("--regen-externa", type=float, default=0.0, help="Regen. de Energia de arma, cadeia etc.")
    extract.add_argument("--saida", type=Path, help="grava o JSON de entrada aqui (padrão: imprime)")

    serve = comandos.add_parser("serve", help="sobe a API e a página em http://127.0.0.1:8000")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    alias = comandos.add_parser("alias", help="mapeia um nome lido para uma chave do dicionário")
    alias.add_argument("categoria", choices=get_args(CategoriaNome))
    alias.add_argument("chave", help="chave interna (ex.: 'Moonlit Clouds', 'crit_dmg')")
    alias.add_argument("alias", help="nome como aparece no jogo")
    return parser


def _check_data(_args: argparse.Namespace, dados: GameData, settings: Settings) -> int:
    print(f"OK: {settings.data_dir}")
    print(f"  {len(dados.substats)} substatus, {len(dados.sets)} sets, {len(dados.echoes)} echos, {len(dados.perfis)} builds")
    return 0


def _analyze(args: argparse.Namespace, dados: GameData, _settings: Settings) -> int:
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


def _extract(args: argparse.Namespace, dados: GameData, settings: Settings) -> int:
    perfil = dados.perfis.get(args.build)
    if perfil is None:
        _erro(f"Build '{args.build}' não existe em characters.json.", f"Disponíveis: {', '.join(sorted(dados.perfis))}")
        return 1
    try:
        modelo = criar_modelo_nvidia(settings)
        prints_echo, print_personagem = separar_prints(args.pasta)
        pedido = PedidoExtracao(
            build=args.build,
            prints_echo=prints_echo,
            print_personagem=args.personagem or print_personagem,
            condicoes=Condicoes(arma_assinatura=RESPOSTA_ARMA.get(args.arma_assinatura)),
            regen_externa=args.regen_externa,
        )
    except (ConfiguracaoAusente, OSError, ValueError) as erro:
        _erro(str(erro))
        return 1
    extrator = Extrator(modelo=modelo, cache=CacheVisao(settings.cache_dir), dados=dados, recorte_echo=settings.echo_recorte)
    extracao = extrair_build(extrator, pedido, perfil, settings.nvidia_concorrencia)
    _resumir(extracao)
    if extracao.entrada is None:
        _erro("Nenhum echo lido; nada a gravar.")
        return 1
    pendentes = resolver_build(perfil, extracao.entrada.condicoes).condicoes_pendentes
    if pendentes:
        _erro(f"Condições não detectadas: {', '.join(pendentes)}. Use --arma-assinatura sim|nao ou preencha 'condicoes'.")
    _gravar_entrada(extracao.entrada, args.saida)
    return 0


def _resumir(extracao: ExtracaoBuild) -> None:
    resultados = [*extracao.echos, *([extracao.personagem] if extracao.personagem else [])]
    for resultado in resultados:
        origem = " (cache)" if resultado.do_cache else ""
        situacao = "ok" if resultado.tipo == "ok" else f"FALHOU: {resultado.motivo}"
        _erro(f"{resultado.arquivo}: {situacao}{origem}")


def _gravar_entrada(entrada: EntradaBuild, saida: Path | None) -> None:
    texto = entrada.model_dump_json(indent=2, exclude_none=True)
    if saida is None:
        print(texto)
        return
    saida.write_text(texto + "\n", encoding="utf-8")
    _erro(f"Entrada gravada em {saida}. Revise e rode: wuwastats analyze {saida}")


def _alias(args: argparse.Namespace, dados: GameData, settings: Settings) -> int:
    try:
        registrar_alias(settings.data_dir, dados, args.categoria, args.chave, args.alias)
    except AliasInvalido as erro:
        _erro(str(erro))
        return 1
    print(f"'{args.alias}' -> {args.chave} ({args.categoria})")
    return 0


def _serve(args: argparse.Namespace, _dados: GameData, settings: Settings) -> int:
    uvicorn.run(criar_app(settings), host=args.host, port=args.port)
    return 0


def _erro(*linhas: str) -> None:
    print("\n".join(linhas), file=sys.stderr)


COMANDOS: dict[str, Comando] = {
    "check-data": _check_data,
    "analyze": _analyze,
    "extract": _extract,
    "serve": _serve,
    "alias": _alias,
}

if __name__ == "__main__":
    sys.exit(main())
