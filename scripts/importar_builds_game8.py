"""Gera builds em data/characters.json a partir dos guias "Best Builds and Teams" do Game8.

    uv run python scripts/importar_builds_game8.py --simular                # mostra o que faria, sem gravar
    uv run python scripts/importar_builds_game8.py                          # todos que ainda não têm build
    uv run python scripts/importar_builds_game8.py --personagem Hsin --substituir

Cada bloco "<...> Build" da página vira uma build: armas, set, padrão de custo, echo principal, status principais e
estrelas dos substatus. A Regen mínima vem da meta citada no texto do bloco; sem meta, fica 100 com status TODO.
Personagens que já têm build não são tocados (a não ser com --substituir). O texto explicativo (descricao) não é
gerado: é escrito à mão, com palavras próprias. Páginas baixadas ficam em cache/game8/ (--atualizar baixa de novo).
"""

import argparse
import html
import io
import re
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from wuwastats.config import PROJECT_ROOT
from wuwastats.domain.models import ESTRELAS_MAXIMAS, Custo
from wuwastats.domain.names import NameIndex, fold, resolve_stat
from wuwastats.domain.tables import GameData
from wuwastats.gamedata.loader import GameDataError, load_game_data
from wuwastats.gamedata.perfis import CHAVE_VALIDA, gravar_perfis, ler_perfis

GAME8 = "https://game8.co"
HOME = f"{GAME8}/games/Wuthering-Waves"
TIMEOUT_S = 30
TENTATIVAS = 3
PAUSA_ENTRE_DOWNLOADS_S = 1.0  # o site é de terceiros: sem rajadas
PASTA_CACHE = PROJECT_ROOT / "cache" / "game8"
REGEN_PADRAO = 100
CUSTOS_DA_TABELA: dict[str, Custo] = {"4": 4, "3": 3, "1": 1}  # colunas da tabela de principais
# Nomes do Game8 que não estão em stat_aliases.json (comparados já normalizados com fold()).
STATS_DO_GAME8 = {
    "res skill dmg": "skill_dmg",
    "resonance skill dmg": "skill_dmg",
    "res liberation dmg": "liberation_dmg",
    "resonance liberation dmg": "liberation_dmg",
    "basic attack dmg": "basic_atk_dmg",
    "heavy attack dmg": "heavy_atk_dmg",
    "crit": "crit_rate",
}
ESCALA_PELO_PRINCIPAL_DE_CUSTO_1 = {"hp_pct": "HP", "def_pct": "DEF"}
LINK_DE_ARTIGO = r'<a[^>]+href="((?:https://game8\.co)?/games/Wuthering-Waves/archives/\d+)"[^>]*>(.*?)</a>'


class PaginaIndisponivel(Exception):
    pass


@dataclass(frozen=True)
class BlocoGame8:
    titulo: str
    melhor_arma: str | None
    alternativas: tuple[str, ...]
    sets: tuple[str, ...]
    sonata: str  # texto da célula, ex.: "3-pc : Dream of the Lost 2-pc : Havoc Eclipse"
    custos: tuple[int, ...]
    echo_principal: str | None
    principais: Mapping[str, str]  # "4" / "3" / "1" → texto da célula ("Crit DMG or Crit Rate")
    substatus: tuple[tuple[str, int], ...]  # (nome, estrelas) na ordem do site
    texto: str  # parágrafos do bloco, só para achar a meta de Regen


@dataclass
class BuildGerada:
    chave: str
    perfil: dict[str, Any]
    avisos: list[str] = field(default_factory=list)


# --- Fluxo principal ---


def main(argv: list[str] | None = None) -> int:
    for saida in (sys.stdout, sys.stderr):
        if isinstance(saida, io.TextIOWrapper):
            saida.reconfigure(encoding="utf-8")
    args = _argumentos(argv)
    dados = load_game_data(args.data_dir)
    atuais = ler_perfis(args.data_dir)
    alvos = escolher_personagens(dados, atuais, args.personagem, args.substituir)
    baixar = _baixador(args.atualizar)
    try:
        links = links_da_home(baixar(HOME))
    except PaginaIndisponivel as erro:
        print(f"Erro ao abrir o Game8: {erro}", file=sys.stderr)
        return 1
    geradas, sem_pagina = gerar_todas(alvos, links, dados, baixar)
    _relatorio(geradas, sem_pagina)
    if args.simular or not geradas:
        return 0
    return _gravar(args.data_dir, mesclar(atuais, geradas, set(alvos)))


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--personagem", action="append", help="chave em resonators.json (pode repetir); padrão: todos")
    parser.add_argument("--substituir", action="store_true", help="troca as builds de quem já tem")
    parser.add_argument("--simular", action="store_true", help="só mostra o relatório, sem gravar")
    parser.add_argument("--atualizar", action="store_true", help="ignora o cache e baixa as páginas de novo")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    return parser.parse_args(argv)


def escolher_personagens(
    dados: GameData, atuais: Mapping[str, Any], pedidos: Sequence[str] | None, substituir: bool
) -> list[str]:
    """Sem --substituir, quem já tem build fica de fora: as builds feitas à mão são preservadas."""
    com_build = {perfil["personagem"] for perfil in atuais.values()}
    candidatos = list(pedidos) if pedidos else sorted(dados.ressonadores)
    desconhecidos = [nome for nome in candidatos if nome not in dados.ressonadores]
    if desconhecidos:
        raise SystemExit(f"personagens fora de resonators.json: {desconhecidos}")
    return [nome for nome in candidatos if substituir or nome not in com_build]


def gerar_todas(
    alvos: Sequence[str], links: Mapping[str, Sequence[str]], dados: GameData, baixar: Callable[[str], str]
) -> tuple[list[BuildGerada], list[str]]:
    geradas: list[BuildGerada] = []
    sem_pagina: list[str] = []
    for personagem in alvos:
        blocos = blocos_do_personagem(personagem, links, baixar)
        if not blocos:
            sem_pagina.append(personagem)
            continue
        geradas.extend(montar_build(personagem, bloco, dados) for bloco in blocos)
    return geradas, sem_pagina


def mesclar(atuais: Mapping[str, Any], geradas: Sequence[BuildGerada], alvos: set[str]) -> dict[str, Any]:
    """Tira as builds antigas dos personagens gerados (só chegam aqui os permitidos) e acrescenta as novas."""
    gerados = {build.perfil["personagem"] for build in geradas} & alvos
    mantidas = {chave: perfil for chave, perfil in atuais.items() if perfil["personagem"] not in gerados}
    return mantidas | {build.chave: build.perfil for build in geradas}


def _gravar(data_dir: Path, perfis: Mapping[str, Any]) -> int:
    try:
        gravar_perfis(data_dir, perfis)
    except GameDataError as erro:
        print("Nada foi gravado. Erros de validação:", file=sys.stderr)
        print("\n".join(f"  - {linha}" for linha in erro.erros), file=sys.stderr)
        return 1
    print(f"\nGravado em {data_dir / 'characters.json'} (o anterior foi para data/backups/).")
    return 0


# --- Download ---


def _baixador(atualizar: bool) -> Callable[[str], str]:
    def baixar(url: str) -> str:
        cache = PASTA_CACHE / f"{re.sub(r'[^A-Za-z0-9]+', '_', url.removeprefix(GAME8)).strip('_') or 'home'}.html"
        if cache.is_file() and not atualizar:
            return cache.read_text(encoding="utf-8")
        texto = _baixar(url)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(texto, encoding="utf-8")
        time.sleep(PAUSA_ENTRE_DOWNLOADS_S)
        return texto

    return baixar


def _baixar(url: str) -> str:
    requisicao = Request(url, headers={"User-Agent": "Mozilla/5.0 (wuwastats; uso pessoal)"})
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            with urlopen(requisicao, timeout=TIMEOUT_S) as resposta:
                return resposta.read().decode("utf-8", errors="replace")
        except HTTPError as erro:
            if erro.code < 500 or tentativa == TENTATIVAS:
                raise PaginaIndisponivel(f"{url}: HTTP {erro.code} {erro.reason}") from erro
        except (URLError, TimeoutError) as erro:
            if tentativa == TENTATIVAS:
                raise PaginaIndisponivel(f"{url}: {erro}") from erro
        time.sleep(2**tentativa)
    raise PaginaIndisponivel(f"{url}: sem resposta após {TENTATIVAS} tentativas")


def links_da_home(pagina: str) -> dict[str, list[str]]:
    """Texto do link → URLs (o mesmo nome aparece para o guia de builds e para o de materiais)."""
    links: dict[str, list[str]] = {}
    for href, conteudo in re.findall(LINK_DE_ARTIGO, pagina, re.S):
        url = href if href.startswith("http") else f"{GAME8}{href}"
        lista = links.setdefault(_texto(conteudo), [])
        if url not in lista:
            lista.append(url)
    return links


def nomes_no_game8(personagem: str) -> list[str]:
    """'Rover: Havoc' aparece como 'Rover (Havoc)'."""
    return [personagem, re.sub(r"^(.+): (.+)$", r"\1 (\2)", personagem)]


def blocos_do_personagem(personagem: str, links: Mapping[str, Sequence[str]], baixar: Callable[[str], str]) -> list[BlocoGame8]:
    """O mesmo nome leva ao guia de builds, ao de materiais...: vale a primeira página com blocos de build."""
    urls = dict.fromkeys(url for nome in nomes_no_game8(personagem) for url in links.get(nome, ()))
    for url in urls:
        try:
            blocos = ler_blocos(baixar(url))
        except PaginaIndisponivel as erro:
            print(f"  aviso: {personagem}: {erro}", file=sys.stderr)
            continue
        if blocos:
            return blocos
    return []


# --- Leitura da página (puro) ---


def _texto(fragmento: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragmento))).strip()


def _links(celula: str) -> tuple[str, ...]:
    return tuple(texto for texto in (_texto(a) for a in re.findall(r"<a\b[^>]*>(.*?)</a>", celula, re.S)) if texto)


def ler_blocos(pagina: str) -> list[BlocoGame8]:
    """Cada <h3> seguido de uma tabela com 'Best Weapon' é uma build; o bloco vai até o próximo <h3> ou <h2>."""
    cabecalhos = list(re.finditer(r"<h3[^>]*>(.*?)</h3>", pagina, re.S))
    blocos: list[BlocoGame8] = []
    for indice, cabecalho in enumerate(cabecalhos):
        fim = cabecalhos[indice + 1].start() if indice + 1 < len(cabecalhos) else len(pagina)
        trecho = re.split(r"<h2\b", pagina[cabecalho.end() : fim], maxsplit=1)[0]
        bloco = _ler_bloco(_texto(cabecalho.group(1)), trecho)
        if bloco:
            blocos.append(bloco)
    return blocos


def _ler_bloco(titulo: str, trecho: str) -> BlocoGame8 | None:
    tabelas = re.findall(r"<table\b.*?</table>", trecho, re.S)
    if not tabelas or "Best Weapon" not in tabelas[0]:
        return None
    linhas = {_texto(rotulo): celula for rotulo, celula in re.findall(r"<tr>\s*<th[^>]*>(.*?)</th>(.*?)</tr>", tabelas[0], re.S)}
    if "Cost Pattern" not in linhas:  # "X is the Best In Slot" usa a mesma tabela, mas é sobre a arma
        return None
    estatisticas = next((t for t in tabelas[1:] if "Main Stats" in t), "")
    return BlocoGame8(
        titulo=titulo,
        melhor_arma=next(iter(_links(linhas.get("Best Weapon", ""))), None),
        alternativas=_links(linhas.get("Alt. Weapons", "")),
        sets=_links(linhas.get("Sonata Effect", "")),
        sonata=_texto(linhas.get("Sonata Effect", "")),
        custos=tuple(int(c) for c in re.findall(r"\b[134]\b", _texto(linhas.get("Cost Pattern", "")))),
        echo_principal=next(iter(_links(linhas.get("Main Echo", ""))), None),
        principais=_principais(estatisticas),
        substatus=_substatus(estatisticas),
        texto=_texto(trecho.split(estatisticas, 1)[-1]) if estatisticas else "",
    )


def _principais(tabela: str) -> dict[str, str]:
    """A linha depois de '4 COST | 3 COST | 1 COST' traz os principais na mesma ordem."""
    depois = tabela.split("1 COST", 1)[-1] if "1 COST" in tabela else ""
    celulas = [_texto(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", depois, re.S)][: len(CUSTOS_DA_TABELA)]
    return dict(zip(CUSTOS_DA_TABELA, celulas, strict=False))


def _substatus(tabela: str) -> tuple[tuple[str, int], ...]:
    lista = _texto(tabela.split("Substats", 1)[-1]) if "Substats" in tabela else ""
    return tuple((nome.strip(), len(estrelas)) for nome, estrelas in re.findall(r"\d+\.\s*([^★\d][^★]*?)\s*(★+)", lista))


def meta_de_regen(texto: str) -> int | None:
    """'aim to reach 115-120% Energy Regen' → 115; ignora números abaixo de 100 (bônus, não meta)."""
    for numero in re.findall(r"(\d{3})(?:\s*[-–~]\s*\d{3})?\s*%\s*(?:of\s+)?(?:Energy Regen|ER)\b", texto):
        if int(numero) >= REGEN_PADRAO:
            return int(numero)
    return None


# --- Montagem da build (pura) ---


def montar_build(personagem: str, bloco: BlocoGame8, dados: GameData) -> BuildGerada:
    avisos: list[str] = []
    principais = {custo: _principais_resolvidos(texto, custo, dados, avisos) for custo, texto in bloco.principais.items()}
    regen = meta_de_regen(bloco.texto)
    perfil: dict[str, Any] = {
        "personagem": personagem,
        "armas": _armas(bloco, dados, avisos),
        "escala": _escala(principais.get("1", [])),
        "regen_energia_min": regen or REGEN_PADRAO,
        "custos": list(bloco.custos),
        "echo_principal": _nome(dados.echo_names, dados.echoes, bloco.echo_principal, "echo", avisos),
        "set": _set(bloco, dados, avisos),
        "principais": {custo: stats for custo, stats in principais.items() if stats},
        "estrelas": _estrelas(bloco.substatus, dados, avisos),
    }
    if regen is None:
        avisos.append("o Game8 não cita meta de Regen. de Energia; ficou 100")
    if len(bloco.custos) != 5:
        avisos.append(f"padrão de custo ilegível: {bloco.custos}")
    perfil["status"] = f"TODO: {'; '.join(avisos)}" if avisos else "ok"
    return BuildGerada(chave=chave_da_build(personagem, bloco.titulo), perfil=_sem_vazios(perfil), avisos=avisos)


def chave_da_build(personagem: str, titulo: str) -> str:
    """'Hsin' + 'Unison/Electro Flare DPS Build' → 'Hsin_Unison_Electro_Flare_DPS'."""
    sem_build = re.sub(r"\bBuild\b", " ", titulo, flags=re.I)
    # 'Rover: Havoc' no título aparece como 'Rover Havoc'
    nome_flexivel = r"\W*".join(re.escape(parte) for parte in re.split(r"\W+", personagem) if parte)
    sem_nome = re.sub(nome_flexivel, "", sem_build, flags=re.I)
    partes = [p for p in re.split(r"[^A-Za-z0-9]+", f"{personagem} {sem_nome}") if p]
    chave = "_".join(partes)[:60]
    return chave if CHAVE_VALIDA.match(chave) else f"Build_{chave}"[:60]


def _armas(bloco: BlocoGame8, dados: GameData, avisos: list[str]) -> dict[str, Any]:
    melhor = _nome(dados.arma_names, dados.armas, bloco.melhor_arma, "arma", avisos)
    alternativas = (_nome(dados.arma_names, dados.armas, nome, "arma", avisos) for nome in bloco.alternativas)
    return {"melhor": melhor, "alternativas": [a for a in alternativas if a]}


def _set(bloco: BlocoGame8, dados: GameData, avisos: list[str]) -> str | None:
    """A build guarda um set só: em combinações (3 peças + 2 de outro) fica o primeiro e o aviso registra o resto."""
    if len(bloco.sets) > 1:
        avisos.append(f"o Game8 combina sets ({bloco.sonata}); a build guarda só {bloco.sets[0]}")
    return _nome(dados.set_names, dados.sets, next(iter(bloco.sets), None), "set", avisos)


def _nome(indice: NameIndex, catalogo: Mapping[str, object], nome: str | None, tipo: str, avisos: list[str]) -> str | None:
    """As chaves do catálogo já são os nomes em inglês do jogo; o índice cobre grafias alternativas.

    O Game8 pontua diferente ('Reminiscence: Nightmare Adam Smasher' x 'Reminiscence - Nightmare: Adam Smasher'):
    por último compara só letras e números.
    """
    if not nome:
        return None
    chave = nome if nome in catalogo else indice.resolve(nome)
    if chave is None:
        chave = next((c for c in catalogo if _sem_pontuacao(c) == _sem_pontuacao(nome)), None)
    if chave is None:
        avisos.append(f"{tipo} '{nome}' não está no catálogo")
    return chave


def _sem_pontuacao(nome: str) -> str:
    return re.sub(r"[^a-z0-9]", "", fold(nome))


def _principais_resolvidos(texto: str, custo: str, dados: GameData, avisos: list[str]) -> list[str]:
    """'Electro DMG and ATK' → ['electro_dmg', 'atk_pct']: no principal, ATQ/HP/DEF sem '%' também são percentuais."""
    tabela = dados.main_stats.get(CUSTOS_DA_TABELA[custo]) if custo in CUSTOS_DA_TABELA else None
    permitidos = set(tabela.primarios) if tabela else set()
    resolvidos: list[str] = []
    for nome in (n for n in re.split(r"\s+(?:or|and)\s+|\s*[,/&]\s*", texto) if n not in ("", "-")):
        stat = _stat(nome, dados, percentual=True)
        if stat is None or stat not in permitidos:
            avisos.append(f"principal de custo {custo} '{nome}' não reconhecido")
            continue
        resolvidos.append(stat)
    return list(dict.fromkeys(resolvidos))


def _estrelas(substatus: Sequence[tuple[str, int]], dados: GameData, avisos: list[str]) -> dict[str, int]:
    estrelas: dict[str, int] = {}
    for nome, quantas in substatus:
        stat = _stat(nome, dados, percentual=not fold(nome).startswith("flat"))
        if stat is None or stat not in dados.substats:
            avisos.append(f"substatus '{nome}' não reconhecido")
            continue
        estrelas.setdefault(stat, min(quantas, ESTRELAS_MAXIMAS))
    return estrelas


def _stat(nome: str, dados: GameData, percentual: bool) -> str | None:
    """'Flat ATK', 'Res. Liberation DMG Bonus %', 'ATK%'...: tenta o nome como veio e sem 'Bonus'/'%' no fim."""
    limpo = re.sub(r"^flat\s+", "", nome.strip(), flags=re.I)
    sem_bonus = re.sub(r"(\s+bonus)?\s*%?$", "", limpo, flags=re.I)
    for tentativa in (limpo, sem_bonus):
        stat = STATS_DO_GAME8.get(fold(tentativa)) or resolve_stat(dados.stat_names, tentativa, percentual)
        if stat:
            return stat
    return None


def _escala(principais_custo_1: Sequence[str]) -> str:
    return next((ESCALA_PELO_PRINCIPAL_DE_CUSTO_1[s] for s in principais_custo_1 if s in ESCALA_PELO_PRINCIPAL_DE_CUSTO_1), "ATQ")


def _sem_vazios(perfil: dict[str, Any]) -> dict[str, Any]:
    return {campo: valor for campo, valor in perfil.items() if valor is not None}


# --- Relatório ---


def _relatorio(geradas: Sequence[BuildGerada], sem_pagina: Sequence[str]) -> None:
    for build in geradas:
        marca = "!" if build.avisos else "✓"
        print(f"{marca} {build.chave}")
        for aviso in build.avisos:
            print(f"    - {aviso}")
    personagens = {build.perfil["personagem"] for build in geradas}
    com_aviso = sum(1 for build in geradas if build.avisos)
    print(f"\n{len(geradas)} builds de {len(personagens)} personagens; {com_aviso} com algo a conferir (status TODO).")
    if sem_pagina:
        print(f"Sem página de builds no Game8 (ou sem blocos legíveis): {', '.join(sem_pagina)}")


if __name__ == "__main__":
    sys.exit(main())
