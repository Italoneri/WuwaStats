"""Importa echos, sets (sonatas), ressonadores e armas de Arikatsu/WutheringWaves_Data para data/.

    uv run python scripts/importar_dados_jogo.py              # branch padrão (= versão atual do jogo)
    uv run python scripts/importar_dados_jogo.py --ref 3.7    # branch ou commit específico

Gera data/echoes.json, data/sets.json, data/resonators.json e data/weapons.json, acrescenta os nomes PT-BR
de echos e sets como aliases em data/stat_aliases.json (mapeamentos manuais ficam) e grava em
data/fonte_dados_jogo.json o commit usado. Tudo é validado numa cópia de data/ antes de substituir os arquivos de verdade.
Depois baixa de nanoka.cc os ícones de echos e armas que ainda não estão em data/imagens/ (ressonadores ficam à mão).
"""

import argparse
import io
import re
import shutil
import sys
import tempfile
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from wuwastats.config import PROJECT_ROOT
from wuwastats.domain.names import NameIndex, fold, resolve_stat
from wuwastats.gamedata.aliases import ARQUIVO_ALIASES, escrever_atomico
from wuwastats.gamedata.imagens import CategoriaImagem, ImagemRecusada, ImagensDoCatalogo
from wuwastats.gamedata.loader import GameDataError, load_game_data
from wuwastats.gamedata.schemas import AliasesFile, EchoesFile, EchoRaw, SetRaw, SetsFile

REPOSITORIO = "Arikatsu/WutheringWaves_Data"
API = f"https://api.github.com/repos/{REPOSITORIO}"
RAW = f"https://raw.githubusercontent.com/{REPOSITORIO}"
TIMEOUT_S = 60
TENTATIVAS = 3

# nanoka.cc serve as texturas do jogo pelo mesmo caminho dos campos Icon da fonte, em .webp.
ICONES = "https://static.nanoka.cc/assets/ww"
PREFIXO_UI_DO_JOGO = "/Game/Aki/UI/"
DOWNLOADS_SIMULTANEOS = 8

# Os outros tipos são entradas especiais que reaproveitam o nome de echos normais com outra raridade e outros sets.
TIPO_ECHO_NORMAL = 1

# Caminhos conferidos na versão 3.7. Se um 404 aparecer, a pasta mudou de nome: procure o arquivo no repositório.
CAMINHO_ECHOS = "BinData/phantom/phantomitem.json"
CAMINHO_RARIDADES = "BinData/phantom/phantomrarity.json"
CAMINHO_GRUPOS_SET = "BinData/phantom/phantomfettergroup.json"
CAMINHO_EFEITOS_SET = "BinData/phantom/phantomfetter.json"
CAMINHO_PROPRIEDADES = "BinData/property/propertyindex.json"
CAMINHO_PERSONAGENS = "BinData/role/roleinfo.json"
CAMINHO_ELEMENTOS = "BinData/element_info/elementinfo.json"
CAMINHO_ARMAS = "BinData/weapon/weaponconf.json"
CAMINHO_TEXTMAP = "Textmaps/{idioma}/multi_text/MultiText.json"

# Os outros RoleType são versões de teste/evento dos mesmos personagens.
TIPO_PERSONAGEM_JOGAVEL = 1
# Tipo de arma não tem tabela própria: o nome vem deste texto ("Weapon Type: Sword"), sem o prefixo.
TEXTO_TIPO_ARMA = "RoleProject_WeaponType{:02d}"

ARQUIVO_ECHOES = "echoes.json"
ARQUIVO_SETS = "sets.json"
ARQUIVO_RESSONADORES = "resonators.json"
ARQUIVO_ARMAS = "weapons.json"
ARQUIVO_FONTE = "fonte_dados_jogo.json"

Categoria = Literal["echoes", "sets"]


class FonteIndisponivel(Exception):
    pass


class ArquivoAusente(FonteIndisponivel):
    pass


# --- Formato dos arquivos da fonte (só os campos usados) ---


class _Fonte(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class TextoFonte(_Fonte):
    chave: str | int = Field(alias="Id")
    texto: str = Field(alias="Content")


class EchoFonte(_Fonte):
    chave_nome: str = Field(alias="MonsterName")
    raridade: int = Field(alias="Rarity")
    grupos_set: list[int] = Field(alias="FetterGroup")
    tipo: int = Field(alias="PhantomType")
    icone: str | None = Field(default=None, alias="Icon")


class RaridadeFonte(_Fonte):
    raridade: int = Field(alias="Rare")
    custo: int = Field(alias="Cost")


class PecasFonte(_Fonte):
    pecas: int = Field(alias="Key")
    efeito: int = Field(alias="Value")


class GrupoSetFonte(_Fonte):
    id: int = Field(alias="Id")
    chave_nome: str = Field(alias="FetterGroupName")
    efeitos_por_pecas: list[PecasFonte] = Field(alias="FetterMap")


class PropriedadeSomadaFonte(_Fonte):
    id: int = Field(alias="Id")
    valor: float = Field(alias="Value")
    proporcional: bool = Field(alias="IsRatio")


class EfeitoSetFonte(_Fonte):
    id: int = Field(alias="Id")
    chave_descricao: str = Field(alias="EffectDescription")
    parametros: list[str] = Field(alias="EffectDescriptionParam")
    propriedades: list[PropriedadeSomadaFonte] = Field(alias="AddProp")


class PropriedadeFonte(_Fonte):
    id: int = Field(alias="Id")
    chave_nome: str = Field(alias="Name")
    percentual: bool = Field(alias="IsPercent")


class PersonagemFonte(_Fonte):
    chave_nome: str = Field(alias="Name")
    raridade: int = Field(alias="QualityId")
    elemento: int = Field(alias="ElementId")
    tipo_arma: int = Field(alias="WeaponType")
    tipo: int = Field(alias="RoleType")
    teste: bool = Field(alias="IsTrial")


class ElementoFonte(_Fonte):
    id: int = Field(alias="Id")
    chave_nome: str = Field(alias="Name")


class ArmaFonte(_Fonte):
    chave_nome: str = Field(alias="WeaponName")
    raridade: int = Field(alias="QualityId")
    tipo: int = Field(alias="WeaponType")
    icone: str | None = Field(default=None, alias="Icon")


class RepositorioApi(_Fonte):
    default_branch: str


class AutorApi(_Fonte):
    date: str


class CommitDetalheApi(_Fonte):
    message: str
    committer: AutorApi


class CommitApi(_Fonte):
    sha: str
    commit: CommitDetalheApi


@dataclass(frozen=True)
class Commit:
    ref: str
    sha: str
    data: str
    mensagem: str


@dataclass(frozen=True)
class TabelasFonte:
    echos: list[EchoFonte]
    raridades: list[RaridadeFonte]
    grupos_set: list[GrupoSetFonte]
    efeitos_set: list[EfeitoSetFonte]
    propriedades: list[PropriedadeFonte]
    textos_en: Mapping[str, str]
    textos_pt: Mapping[str, str] | None
    personagens: list[PersonagemFonte] = field(default_factory=list)
    elementos: list[ElementoFonte] = field(default_factory=list)
    armas: list[ArmaFonte] = field(default_factory=list)


@dataclass(frozen=True)
class EchoImportado:
    nome_pt: str | None
    custos: frozenset[int]
    sets: tuple[str, ...]
    icone: str | None = None


@dataclass(frozen=True)
class SetImportado:
    nome_pt: str | None
    pecas: int
    bonus: dict[int, dict[str, float]]
    efeitos: dict[int, tuple[str, str | None]]


@dataclass(frozen=True)
class Traducao:
    en: str
    pt: str | None


@dataclass(frozen=True)
class RessonadorImportado:
    nome_pt: str | None
    elemento: str
    tipo_arma: str
    raridade: int


@dataclass(frozen=True)
class ArmaImportada:
    nome_pt: str | None
    tipo: str
    raridade: int
    icone: str | None = None


@dataclass(frozen=True)
class Elenco:
    elementos: dict[str, Traducao]
    tipos_arma: dict[str, Traducao]
    ressonadores: dict[str, RessonadorImportado]
    armas: dict[str, ArmaImportada]
    avisos: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Catalogo:
    echoes: dict[str, EchoImportado]
    sets: dict[str, SetImportado]
    avisos: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Icone:
    categoria: CategoriaImagem
    chave: str
    url: str


# --- Fluxo principal ---


def main(argv: list[str] | None = None) -> int:
    for saida in (sys.stdout, sys.stderr):
        if isinstance(saida, io.TextIOWrapper):
            saida.reconfigure(encoding="utf-8")
    args = _argumentos(argv)
    data_dir: Path = args.data_dir
    try:
        commit = resolver_commit(args.ref)
        print(f"Fonte: {REPOSITORIO}@{commit.ref} ({commit.sha[:10]}) — {commit.mensagem}")
        tabelas = baixar_tabelas(commit.sha)
    except FonteIndisponivel as erro:
        print(f"Erro ao baixar a fonte: {erro}", file=sys.stderr)
        return 1

    aliases = AliasesFile.model_validate_json((data_dir / ARQUIVO_ALIASES).read_text(encoding="utf-8"))
    catalogo = montar_catalogo(tabelas, NameIndex.build(aliases.stats))
    elenco = montar_elenco(tabelas)
    echoes_atual = EchoesFile.model_validate_json((data_dir / ARQUIVO_ECHOES).read_text(encoding="utf-8"))
    sets_atual = SetsFile.model_validate_json((data_dir / ARQUIVO_SETS).read_text(encoding="utf-8"))

    echoes_json, avisos_echoes = gerar_echoes(catalogo.echoes, echoes_atual, commit)
    sets_json, avisos_sets = gerar_sets(catalogo.sets, sets_atual, commit)
    aliases_json, avisos_aliases = mesclar_aliases(aliases, _nomes_pt(echoes_json, sets_json))
    arquivos = {
        ARQUIVO_ECHOES: echoes_json,
        ARQUIVO_SETS: sets_json,
        ARQUIVO_ALIASES: aliases_json,
        ARQUIVO_RESSONADORES: gerar_ressonadores(elenco),
        ARQUIVO_ARMAS: gerar_armas(elenco),
        ARQUIVO_FONTE: registro_da_fonte(commit, tem_pt=tabelas.textos_pt is not None),
    }
    try:
        gravar_validado(data_dir, arquivos)
    except GameDataError as erro:
        print("Importação cancelada, data/ não foi alterado. Erros de validação:", file=sys.stderr)
        print("\n".join(f"  - {linha}" for linha in erro.erros), file=sys.stderr)
        return 1

    avisos_icones = importar_icones(ImagensDoCatalogo(data_dir), catalogo, elenco)
    avisos = [*catalogo.avisos, *elenco.avisos, *avisos_echoes, *avisos_sets, *avisos_aliases, *avisos_icones]
    _relatorio(catalogo, elenco, tabelas, avisos)
    return 0


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ref", help="branch (= versão do jogo, ex.: 3.7) ou commit; padrão: branch padrão do repositório")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    return parser.parse_args(argv)


# --- Download ---


def resolver_commit(ref: str | None) -> Commit:
    """Fixa um SHA para que todos os arquivos venham do mesmo snapshot."""
    ref = ref or RepositorioApi.model_validate_json(_baixar(API)).default_branch
    commit = CommitApi.model_validate_json(_baixar(f"{API}/commits/{ref}"))
    return Commit(ref=ref, sha=commit.sha, data=commit.commit.committer.date, mensagem=commit.commit.message.strip())


def baixar_tabelas(sha: str) -> TabelasFonte:
    def tabela[T](caminho: str, formato: TypeAdapter[list[T]]) -> list[T]:
        print(f"  baixando {caminho}")
        return formato.validate_json(_baixar(f"{RAW}/{sha}/{caminho}"))

    textmap = TypeAdapter(list[TextoFonte])
    return TabelasFonte(
        echos=tabela(CAMINHO_ECHOS, TypeAdapter(list[EchoFonte])),
        raridades=tabela(CAMINHO_RARIDADES, TypeAdapter(list[RaridadeFonte])),
        grupos_set=tabela(CAMINHO_GRUPOS_SET, TypeAdapter(list[GrupoSetFonte])),
        efeitos_set=tabela(CAMINHO_EFEITOS_SET, TypeAdapter(list[EfeitoSetFonte])),
        propriedades=tabela(CAMINHO_PROPRIEDADES, TypeAdapter(list[PropriedadeFonte])),
        textos_en=_textmap(tabela(CAMINHO_TEXTMAP.format(idioma="en"), textmap)),
        textos_pt=_textmap_opcional(lambda: tabela(CAMINHO_TEXTMAP.format(idioma="pt"), textmap)),
        personagens=tabela(CAMINHO_PERSONAGENS, TypeAdapter(list[PersonagemFonte])),
        elementos=tabela(CAMINHO_ELEMENTOS, TypeAdapter(list[ElementoFonte])),
        armas=tabela(CAMINHO_ARMAS, TypeAdapter(list[ArmaFonte])),
    )


def _textmap(textos: list[TextoFonte]) -> dict[str, str]:
    return {str(texto.chave): texto.texto for texto in textos}


def _textmap_opcional(baixar: Callable[[], list[TextoFonte]]) -> dict[str, str] | None:
    try:
        return _textmap(baixar())
    except ArquivoAusente:
        print("  textmap PT não existe nesta versão: seguindo só com inglês")
        return None


def _baixar(url: str) -> bytes:
    requisicao = Request(url, headers={"User-Agent": "wuwastats-importador", "Accept": "application/json"})
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            with urlopen(requisicao, timeout=TIMEOUT_S) as resposta:
                return resposta.read()
        except HTTPError as erro:
            if erro.code == 404:
                raise ArquivoAusente(f"{url}: não encontrado (404); o caminho pode ter mudado no repositório") from erro
            if erro.code < 500 or tentativa == TENTATIVAS:
                raise FonteIndisponivel(f"{url}: HTTP {erro.code} {erro.reason}") from erro
        except (URLError, TimeoutError) as erro:
            if tentativa == TENTATIVAS:
                raise FonteIndisponivel(f"{url}: {erro}") from erro
        time.sleep(2**tentativa)
    raise FonteIndisponivel(f"{url}: sem resposta após {TENTATIVAS} tentativas")


# --- Montagem do catálogo (puro) ---


def montar_catalogo(tabelas: TabelasFonte, stats: NameIndex) -> Catalogo:
    avisos: list[str] = []
    nome_por_grupo, sets = _montar_sets(tabelas, stats, avisos)
    echoes = _montar_echoes(tabelas, nome_por_grupo, avisos)
    return Catalogo(echoes=echoes, sets=sets, avisos=avisos)


def _montar_sets(tabelas: TabelasFonte, stats: NameIndex, avisos: list[str]) -> tuple[dict[int, str], dict[str, SetImportado]]:
    efeitos = {efeito.id: efeito for efeito in tabelas.efeitos_set}
    nome_por_grupo: dict[int, str] = {}
    sets: dict[str, SetImportado] = {}
    for grupo in tabelas.grupos_set:
        nome = tabelas.textos_en.get(grupo.chave_nome, "").strip()
        if not nome or nome in sets:
            avisos.append(f"set grupo {grupo.id}: nome '{nome}' vazio ou repetido, ignorado")
            continue
        nome_por_grupo[grupo.id] = nome
        sets[nome] = _montar_set(nome, grupo, efeitos, tabelas, stats, avisos)
    return nome_por_grupo, sets


def _montar_set(
    nome: str,
    grupo: GrupoSetFonte,
    efeitos: Mapping[int, EfeitoSetFonte],
    tabelas: TabelasFonte,
    stats: NameIndex,
    avisos: list[str],
) -> SetImportado:
    propriedades = {prop.id: prop for prop in tabelas.propriedades}
    bonus: dict[int, dict[str, float]] = {}
    descricoes: dict[int, tuple[str, str | None]] = {}
    for item in grupo.efeitos_por_pecas:
        efeito = efeitos.get(item.efeito)
        if efeito is None:
            avisos.append(f"set {nome}: efeito {item.efeito} ({item.pecas} peças) não existe na tabela de efeitos")
            continue
        descricoes[item.pecas] = (
            preencher(tabelas.textos_en.get(efeito.chave_descricao, ""), efeito.parametros),
            _texto_pt(tabelas, efeito.chave_descricao, efeito.parametros),
        )
        status = _bonus_em_status(efeito, propriedades, tabelas.textos_en, stats, f"set {nome} ({item.pecas} peças)", avisos)
        if status:
            bonus[item.pecas] = status
    pecas = max((item.pecas for item in grupo.efeitos_por_pecas), default=0)
    return SetImportado(nome_pt=_texto_pt(tabelas, grupo.chave_nome), pecas=pecas, bonus=bonus, efeitos=descricoes)


def _bonus_em_status(
    efeito: EfeitoSetFonte,
    propriedades: Mapping[int, PropriedadeFonte],
    textos_en: Mapping[str, str],
    stats: NameIndex,
    onde: str,
    avisos: list[str],
) -> dict[str, float]:
    """Bônus fixos do efeito (AddProp) em chaves internas; efeitos condicionais ficam só na descrição."""
    resultado: dict[str, float] = {}
    for somada in efeito.propriedades:
        propriedade = propriedades.get(somada.id)
        nome = textos_en.get(propriedade.chave_nome, "") if propriedade else ""
        percentual = somada.proporcional or (propriedade is not None and propriedade.percentual)
        stat = resolve_stat(stats, nome, percentual=percentual) if nome else None
        if stat is None:
            avisos.append(f"{onde}: propriedade {somada.id} '{nome}' sem chave interna; adicione alias em stats e rode de novo")
            continue
        resultado[stat] = _valor_exibido(somada, percentual)
    return resultado


def _valor_exibido(somada: PropriedadeSomadaFonte, percentual: bool) -> float:
    """A fonte guarda proporções como fração (0.1) e percentuais em base 10000 (1000 = 10%)."""
    if somada.proporcional:
        return round(somada.valor * 100, 2)
    return round(somada.valor / 100, 2) if percentual else somada.valor


def preencher(modelo: str, parametros: list[str]) -> str:
    """Troca {0}, {1}... pelos parâmetros do efeito; índices sem parâmetro ficam como estão."""

    def trocar(encontrado: re.Match[str]) -> str:
        indice = int(encontrado.group(1))
        return parametros[indice] if indice < len(parametros) else encontrado.group(0)

    return re.sub(r"\{(\d+)\}", trocar, modelo).strip()


def _texto_pt(tabelas: TabelasFonte, chave: str, parametros: list[str] | None = None) -> str | None:
    texto = (tabelas.textos_pt or {}).get(chave, "").strip()
    if not texto:
        return None
    return preencher(texto, parametros) if parametros is not None else texto


def _montar_echoes(tabelas: TabelasFonte, nome_por_grupo: Mapping[int, str], avisos: list[str]) -> dict[str, EchoImportado]:
    """A fonte tem uma linha por qualidade/variante do mesmo echo; agrupa pelo nome em inglês."""
    custo_por_raridade = {raridade.raridade: raridade.custo for raridade in tabelas.raridades}
    normais = [echo for echo in tabelas.echos if echo.tipo == TIPO_ECHO_NORMAL]
    especiais = Counter(echo.tipo for echo in tabelas.echos if echo.tipo != TIPO_ECHO_NORMAL)
    avisos.extend(f"{total} linhas de echo com PhantomType {tipo} ignoradas" for tipo, total in sorted(especiais.items()))
    variantes: defaultdict[str, list[EchoFonte]] = defaultdict(list)
    for echo in normais:
        nome = tabelas.textos_en.get(echo.chave_nome, "").strip()
        if nome:
            variantes[nome].append(echo)
    sem_nome = len(normais) - sum(len(linhas) for linhas in variantes.values())
    if sem_nome:
        avisos.append(f"{sem_nome} linhas de echo sem nome em inglês foram ignoradas")
    return {
        nome: _montar_echo(nome, linhas, custo_por_raridade, nome_por_grupo, tabelas, avisos)
        for nome, linhas in sorted(variantes.items())
    }


def _montar_echo(
    nome: str,
    linhas: list[EchoFonte],
    custo_por_raridade: Mapping[int, int],
    nome_por_grupo: Mapping[int, str],
    tabelas: TabelasFonte,
    avisos: list[str],
) -> EchoImportado:
    nomes_pt = Counter(pt for pt in (_texto_pt(tabelas, linha.chave_nome) for linha in linhas) if pt)
    if len(nomes_pt) > 1:
        avisos.append(f"echo {nome}: nomes PT diferentes entre variantes {sorted(nomes_pt)}; usando o mais comum")
    grupos = dict.fromkeys(grupo for linha in linhas for grupo in linha.grupos_set)
    return EchoImportado(
        nome_pt=nomes_pt.most_common(1)[0][0] if nomes_pt else None,
        custos=frozenset(custo_por_raridade[linha.raridade] for linha in linhas if linha.raridade in custo_por_raridade),
        sets=tuple(nome_por_grupo[grupo] for grupo in grupos if grupo in nome_por_grupo),
        icone=next((linha.icone for linha in linhas if linha.icone), None),
    )


def montar_elenco(tabelas: TabelasFonte) -> Elenco:
    """Ressonadores jogáveis e armas; elemento e tipo de arma viram chaves (nome em inglês, minúsculo)."""
    avisos: list[str] = []
    jogaveis = [p for p in tabelas.personagens if p.tipo == TIPO_PERSONAGEM_JOGAVEL and not p.teste]
    elementos = _elementos(tabelas, {p.elemento for p in jogaveis}, avisos)
    numeros_tipo = sorted({p.tipo_arma for p in jogaveis} | {a.tipo for a in tabelas.armas})
    tipos_arma = {numero: _tipo_arma(tabelas, numero, avisos) for numero in numeros_tipo}
    return Elenco(
        elementos={_chave(t): t for t in elementos.values()},
        tipos_arma={_chave(t): t for t in tipos_arma.values()},
        ressonadores=_ressonadores(tabelas, jogaveis, elementos, tipos_arma, avisos),
        armas=_armas(tabelas, tipos_arma, avisos),
        avisos=avisos,
    )


def _ressonadores(
    tabelas: TabelasFonte,
    jogaveis: list[PersonagemFonte],
    elementos: Mapping[int, Traducao],
    tipos_arma: Mapping[int, Traducao],
    avisos: list[str],
) -> dict[str, RessonadorImportado]:
    ressonadores: dict[str, RessonadorImportado] = {}
    for personagem in jogaveis:
        nome = tabelas.textos_en.get(personagem.chave_nome, "").strip()
        if not nome or personagem.elemento not in elementos:
            avisos.append(f"ressonador '{personagem.chave_nome}': sem nome em inglês ou com elemento desconhecido")
            continue
        novo = RessonadorImportado(
            nome_pt=_texto_pt(tabelas, personagem.chave_nome),
            elemento=_chave(elementos[personagem.elemento]),
            tipo_arma=_chave(tipos_arma[personagem.tipo_arma]),
            raridade=personagem.raridade,
        )
        # Rover aparece uma vez por gênero, com o mesmo nome; só avisa se os dados divergirem.
        if ressonadores.setdefault(nome, novo) != novo:
            avisos.append(f"ressonador {nome}: linhas com dados diferentes; mantida a primeira")
    return dict(sorted(ressonadores.items()))


def _armas(tabelas: TabelasFonte, tipos_arma: Mapping[int, Traducao], avisos: list[str]) -> dict[str, ArmaImportada]:
    armas: dict[str, ArmaImportada] = {}
    for arma in tabelas.armas:
        nome = tabelas.textos_en.get(arma.chave_nome, "").strip()
        if not nome or nome in armas:
            avisos.append(f"arma '{arma.chave_nome}': nome '{nome}' vazio ou repetido, ignorada")
            continue
        armas[nome] = ArmaImportada(
            nome_pt=_texto_pt(tabelas, arma.chave_nome),
            tipo=_chave(tipos_arma[arma.tipo]),
            raridade=arma.raridade,
            icone=arma.icone,
        )
    return dict(sorted(armas.items()))


def _elementos(tabelas: TabelasFonte, usados: set[int], avisos: list[str]) -> dict[int, Traducao]:
    por_id = {elemento.id: elemento for elemento in tabelas.elementos}
    resultado: dict[int, Traducao] = {}
    for numero in sorted(usados):
        elemento = por_id.get(numero)
        nome = tabelas.textos_en.get(elemento.chave_nome, "").strip() if elemento else ""
        if elemento is None or not nome:
            avisos.append(f"elemento {numero}: não existe na tabela de elementos ou está sem nome")
            continue
        resultado[numero] = Traducao(en=nome, pt=_texto_pt(tabelas, elemento.chave_nome))
    return resultado


def _tipo_arma(tabelas: TabelasFonte, numero: int, avisos: list[str]) -> Traducao:
    chave = TEXTO_TIPO_ARMA.format(numero)
    nome = _sem_prefixo(tabelas.textos_en.get(chave, ""))
    if not nome:
        avisos.append(f"tipo de arma {numero}: texto '{chave}' não encontrado; usando 'Tipo {numero}'")
        return Traducao(en=f"Tipo {numero}", pt=None)
    pt = _texto_pt(tabelas, chave)
    return Traducao(en=nome, pt=_sem_prefixo(pt) if pt else None)


def _sem_prefixo(texto: str) -> str:
    return texto.split(":", 1)[-1].strip()


def _chave(traducao: Traducao) -> str:
    return re.sub(r"\W+", "_", fold(traducao.en)).strip("_")


# --- Mescla com os arquivos atuais ---


def gerar_echoes(novos: Mapping[str, EchoImportado], atual: EchoesFile, commit: Commit) -> tuple[dict[str, Any], list[str]]:
    avisos: list[str] = []
    echoes = {nome: _echo_json(nome, echo, atual.echoes.get(nome), avisos) for nome, echo in novos.items()}
    echoes |= _orfaos(atual.echoes, novos, commit, avisos, "echo")
    meta = atual.meta.model_dump() | {
        "descricao": (
            "Catálogo de echos, gerado por scripts/importar_dados_jogo.py (fonte em fonte_dados_jogo.json). "
            "Chave = nome em inglês; nome_pt também vira alias em stat_aliases.json. 'custo' null = desconhecido "
            "(não é conferido). 'sets' = sonatas possíveis. Para custo marcado como TODO, preencha à mão: "
            "a escolha sobrevive à próxima importação."
        )
    }
    return {"_meta": meta, "echoes": echoes}, avisos


def _echo_json(nome: str, echo: EchoImportado, anterior: EchoRaw | None, avisos: list[str]) -> dict[str, Any]:
    custo, status = _custo(echo.custos, anterior)
    if status != "ok":
        avisos.append(f"echo {nome}: {status}")
    return {"nome_pt": echo.nome_pt, "custo": custo, "sets": list(echo.sets), "status": status}


def _custo(custos: frozenset[int], anterior: EchoRaw | None) -> tuple[int | None, str]:
    """Quando a fonte é ambígua, mantém o custo que já estava no arquivo se ele for uma das opções."""
    opcoes = sorted(custos)
    if len(opcoes) == 1:
        return opcoes[0], "ok"
    if not opcoes:
        return None, "TODO: a fonte não informa o custo"
    if anterior is not None and anterior.custo in custos:
        return anterior.custo, f"custo escolhido à mão; a fonte lista {opcoes}"
    return None, f"TODO: a fonte lista custos {opcoes} para variantes deste echo; escolha um"


def gerar_sets(novos: Mapping[str, SetImportado], atual: SetsFile, commit: Commit) -> tuple[dict[str, Any], list[str]]:
    avisos: list[str] = []
    sets: dict[str, Any] = {nome: _set_json(conjunto) for nome, conjunto in sorted(novos.items())}
    sets |= _orfaos(atual.sets, novos, commit, avisos, "set")
    meta = atual.meta.model_dump() | {
        "descricao": (
            "Sets (sonatas), gerado por scripts/importar_dados_jogo.py (fonte em fonte_dados_jogo.json). "
            "Chave = nome em inglês; nome_pt também vira alias em stat_aliases.json. 'pecas' = tamanho do set "
            "completo. 'bonus' lista só efeitos que são status fixos (por número de peças); 'efeitos' traz o "
            "texto completo de cada bônus, inclusive os condicionais."
        )
    }
    return {"_meta": meta, "sets": sets}, avisos


def _set_json(conjunto: SetImportado) -> dict[str, Any]:
    return {
        "nome_pt": conjunto.nome_pt,
        "pecas": conjunto.pecas,
        "bonus": {str(pecas): stats for pecas, stats in sorted(conjunto.bonus.items())},
        "efeitos": {str(pecas): {"en": en, "pt": pt} for pecas, (en, pt) in sorted(conjunto.efeitos.items())},
        "status": "ok",
    }


def _orfaos(
    atuais: Mapping[str, EchoRaw | SetRaw], novos: Mapping[str, object], commit: Commit, avisos: list[str], tipo: str
) -> dict[str, Any]:
    """Entradas que sumiram da fonte ficam (podem estar em characters.json), marcadas para revisão."""
    status = f"TODO: não encontrado em {REPOSITORIO}@{commit.sha[:10]}; renomeie para o nome da fonte ou remova"
    orfaos = {nome: raw.model_dump() | {"status": status} for nome, raw in atuais.items() if nome not in novos}
    avisos.extend(f"{tipo} '{nome}' não existe na fonte; mantido com status TODO" for nome in orfaos)
    return orfaos


def _nomes_pt(echoes_json: Mapping[str, Any], sets_json: Mapping[str, Any]) -> dict[Categoria, dict[str, str | None]]:
    """Todas as chaves do catálogo (com ou sem nome PT): todas entram na checagem de colisão."""

    def nomes(entradas: Mapping[str, Mapping[str, Any]]) -> dict[str, str | None]:
        return {chave: entrada.get("nome_pt") for chave, entrada in entradas.items()}

    return {"echoes": nomes(echoes_json["echoes"]), "sets": nomes(sets_json["sets"])}


def mesclar_aliases(
    aliases: AliasesFile, nomes_pt: Mapping[Categoria, Mapping[str, str | None]]
) -> tuple[dict[str, Any], list[str]]:
    """Só acrescenta: aliases existentes nunca são removidos. Nome PT que já aponta para outra chave é pulado."""
    avisos: list[str] = []
    resultado = aliases.model_dump(by_alias=True)
    for categoria, catalogo in nomes_pt.items():
        existentes: dict[str, list[str]] = resultado[categoria]
        for chave, nome in _sem_colisao(existentes, catalogo, categoria, avisos).items():
            lista = existentes.setdefault(chave, [])
            if fold(nome) not in {fold(alias) for alias in lista}:
                lista.append(nome)
    return resultado, avisos


def _sem_colisao(
    existentes: Mapping[str, list[str]], catalogo: Mapping[str, str | None], categoria: Categoria, avisos: list[str]
) -> dict[str, str]:
    indice = NameIndex.build({chave: existentes.get(chave, []) for chave in catalogo.keys() | existentes.keys()})
    novos = {chave: nome for chave, nome in catalogo.items() if nome}
    repetidos = {nome for nome, total in Counter(fold(nome) for nome in novos.values()).items() if total > 1}
    aceitos: dict[str, str] = {}
    for chave, nome in novos.items():
        outras = indice.candidates(nome) - {chave}
        if fold(nome) in repetidos or outras:
            conflito = sorted(outras) or "outro nome PT igual"
            avisos.append(f"alias {categoria} '{nome}' → {chave} pulado: já aponta para {conflito}")
            continue
        aceitos[chave] = nome
    return aceitos


def gerar_ressonadores(elenco: Elenco) -> dict[str, Any]:
    return {
        "_meta": {
            "descricao": (
                "Ressonadores jogáveis, gerado por scripts/importar_dados_jogo.py (fonte em fonte_dados_jogo.json). "
                "Chave = nome em inglês, a mesma de 'personagem' em characters.json. 'elemento' e 'tipo_arma' "
                "apontam para as listas deste arquivo. Não edite à mão: a próxima importação sobrescreve."
            )
        },
        "elementos": {chave: _traducao_json(t) for chave, t in elenco.elementos.items()},
        "tipos_arma": {chave: _traducao_json(t) for chave, t in elenco.tipos_arma.items()},
        "ressonadores": {
            nome: {"nome_pt": r.nome_pt, "elemento": r.elemento, "tipo_arma": r.tipo_arma, "raridade": r.raridade}
            for nome, r in elenco.ressonadores.items()
        },
    }


def gerar_armas(elenco: Elenco) -> dict[str, Any]:
    return {
        "_meta": {
            "descricao": (
                "Armas, gerado por scripts/importar_dados_jogo.py (fonte em fonte_dados_jogo.json). Chave = nome em "
                "inglês, usada em 'armas' de characters.json. 'tipo' aponta para tipos_arma em resonators.json. "
                "Não edite à mão: a próxima importação sobrescreve."
            )
        },
        "armas": {nome: {"nome_pt": a.nome_pt, "tipo": a.tipo, "raridade": a.raridade} for nome, a in elenco.armas.items()},
    }


def _traducao_json(traducao: Traducao) -> dict[str, str | None]:
    return {"en": traducao.en, "pt": traducao.pt}


# --- Gravação ---


def registro_da_fonte(commit: Commit, tem_pt: bool) -> dict[str, Any]:
    return {
        "repositorio": REPOSITORIO,
        "ref": commit.ref,
        "commit": commit.sha,
        "data_commit": commit.data,
        "versao": commit.mensagem,
        "url": f"https://github.com/{REPOSITORIO}/tree/{commit.sha}",
        "textmap_pt": tem_pt,
        "importado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "como_atualizar": (
            "A branch padrão do repositório é a versão do jogo (ex.: 3.7 → 3.8). Quando o último commit de lá for "
            "diferente de 'commit', rode: uv run python scripts/importar_dados_jogo.py"
        ),
    }


def gravar_validado(data_dir: Path, arquivos: Mapping[str, object]) -> None:
    """Valida o conjunto completo numa cópia; data/ só muda se a cópia carregar sem erros."""
    with tempfile.TemporaryDirectory() as temporario:
        copia = Path(temporario) / "data"
        shutil.copytree(data_dir, copia)
        for nome, conteudo in arquivos.items():
            escrever_atomico(copia / nome, conteudo)
        load_game_data(copia)
    for nome, conteudo in arquivos.items():
        escrever_atomico(data_dir / nome, conteudo)


# --- Ícones ---


def importar_icones(
    imagens: ImagensDoCatalogo, catalogo: Catalogo, elenco: Elenco, baixar: Callable[[str], bytes] = _baixar
) -> list[str]:
    """Echos e armas que ainda não têm imagem: nada já no catálogo (inclusive enviado à mão) é sobrescrito.

    Ressonadores ficam de fora: a imagem deles é escolhida à mão na página.
    """
    icones, avisos = icones_do_catalogo(catalogo, elenco)
    faltando = [icone for icone in icones if not imagens.existe(icone.categoria, icone.chave)]
    print(f"\nÍcones: {len(icones) - len(faltando)} já no catálogo, baixando {len(faltando)} de {ICONES}")
    with ThreadPoolExecutor(max_workers=DOWNLOADS_SIMULTANEOS) as pool:
        falhas = [falha for falha in pool.map(lambda icone: _salvar_icone(imagens, icone, baixar), faltando) if falha]
    return [*avisos, *falhas]


def icones_do_catalogo(catalogo: Catalogo, elenco: Elenco) -> tuple[list[Icone], list[str]]:
    candidatos: list[tuple[CategoriaImagem, str, str | None]] = [
        *(("echoes", nome, echo.icone) for nome, echo in catalogo.echoes.items()),
        *(("armas", nome, arma.icone) for nome, arma in elenco.armas.items()),
    ]
    icones: list[Icone] = []
    avisos: list[str] = []
    for categoria, chave, caminho in candidatos:
        url = url_do_icone(caminho or "")
        if url is None:
            avisos.append(f"ícone {categoria} '{chave}': caminho '{caminho or ''}' fora de {PREFIXO_UI_DO_JOGO}; envie à mão")
            continue
        icones.append(Icone(categoria=categoria, chave=chave, url=url))
    return icones, avisos


def url_do_icone(caminho: str) -> str | None:
    """'/Game/Aki/UI/UIResources/.../T_X_UI.T_X_UI' → '<ICONES>/UIResources/.../T_X_UI.webp'."""
    if not caminho.startswith(PREFIXO_UI_DO_JOGO):
        return None
    relativo = caminho.removeprefix(PREFIXO_UI_DO_JOGO).split(".", 1)[0]
    return f"{ICONES}/{relativo}.webp"


def _salvar_icone(imagens: ImagensDoCatalogo, icone: Icone, baixar: Callable[[str], bytes]) -> str | None:
    """Devolve o aviso da falha: um ícone que não veio não cancela a importação."""
    try:
        imagens.salvar(icone.categoria, icone.chave, baixar(icone.url))
    except (FonteIndisponivel, ImagemRecusada) as erro:
        return f"ícone {icone.categoria} '{icone.chave}': {erro}"
    return None


def _relatorio(catalogo: Catalogo, elenco: Elenco, tabelas: TabelasFonte, avisos: Sequence[str]) -> None:
    sem_pt = sum(1 for echo in catalogo.echoes.values() if echo.nome_pt is None)
    print(
        f"\n{len(catalogo.echoes)} echos, {len(catalogo.sets)} sets, {len(elenco.ressonadores)} ressonadores "
        f"e {len(elenco.armas)} armas importados."
    )
    if tabelas.textos_pt is not None:
        print(f"Echos sem nome PT: {sem_pt}")
    if avisos:
        print(f"\nAvisos ({len(avisos)}):")
        print("\n".join(f"  - {aviso}" for aviso in avisos))


if __name__ == "__main__":
    sys.exit(main())
