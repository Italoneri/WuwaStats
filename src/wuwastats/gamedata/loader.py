"""Lê data/*.json, valida o esquema e resolve nomes (PT-BR/aliases) para chaves internas."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from wuwastats.domain.models import Custo
from wuwastats.domain.names import NameIndex, fold, is_pct_flat_pair, is_percent_stat, resolve_stat
from wuwastats.domain.tables import (
    BuildSpec,
    EchoInfo,
    GameData,
    MainStatTable,
    Perfil,
    SetInfo,
    SubstatTable,
    Variante,
)
from wuwastats.gamedata.schemas import (
    CUSTO_POR_CHAVE,
    ArquivosDeDados,
    BuildSpecRaw,
    CustoChave,
    PerfilRaw,
    SetRaw,
    SubstatsFile,
    VarianteRaw,
)


class GameDataError(Exception):
    def __init__(self, erros: list[str]) -> None:
        super().__init__("\n".join(erros))
        self.erros = erros


def load_game_data(data_dir: Path) -> GameData:
    arquivos = _ler_arquivos(data_dir)
    erros: list[str] = []
    dados = _montar(arquivos, erros)
    if erros:
        raise GameDataError(erros)
    return dados


def _ler_arquivos(data_dir: Path) -> ArquivosDeDados:
    conteudos: dict[str, Any] = {}
    erros: list[str] = []
    for campo in ArquivosDeDados.model_fields:
        caminho = data_dir / f"{campo}.json"
        try:
            conteudos[campo] = json.loads(caminho.read_text(encoding="utf-8"))
        except FileNotFoundError:
            erros.append(f"{caminho.name}: arquivo não encontrado em {data_dir}")
        except json.JSONDecodeError as erro:
            erros.append(f"{caminho.name}: JSON inválido (linha {erro.lineno}, coluna {erro.colno}): {erro.msg}")
    if erros:
        raise GameDataError(erros)
    try:
        return ArquivosDeDados.model_validate(conteudos)
    except ValidationError as erro:
        raise GameDataError([_formatar_erro(e, sufixo_arquivo=True) for e in erro.errors()]) from erro


def _formatar_erro(erro: Mapping[str, Any], sufixo_arquivo: bool = False, prefixo: str = "") -> str:
    partes = [str(parte) for parte in erro["loc"]]
    if sufixo_arquivo and partes:
        partes[0] = f"{partes[0]}.json"
    caminho = " › ".join(filter(None, [prefixo, *partes]))
    return f"{caminho}: {erro['msg']}"


def _montar(arquivos: ArquivosDeDados, erros: list[str]) -> GameData:
    substats = _substats(arquivos.substats)
    main_stats: dict[Custo, MainStatTable] = {
        CUSTO_POR_CHAVE[chave]: MainStatTable(primarios=dict(raw.primarios), secundario=dict(raw.secundario))
        for chave, raw in arquivos.main_stats.custos.items()
    }
    aliases = arquivos.stat_aliases
    stat_names = _indice(aliases.stats, _stats_conhecidos(substats, main_stats), "stats", erros)
    echo_names = _indice(aliases.echoes, set(arquivos.echoes.echoes), "echoes", erros)
    set_names = _indice(aliases.sets, set(arquivos.sets.sets), "sets", erros)
    resolvedor = _Resolvedor(stat_names, echo_names, set_names, main_stats, erros)
    return GameData(
        substats=substats,
        main_stats=main_stats,
        sets={nome: resolvedor.set_info(nome, raw) for nome, raw in arquivos.sets.sets.items()},
        echoes={nome: EchoInfo(custo=raw.custo) for nome, raw in arquivos.echoes.echoes.items()},
        echos_repetidos_contam=arquivos.sets.meta.echos_repetidos_contam,
        stat_names=stat_names,
        echo_names=echo_names,
        set_names=set_names,
        perfis={nome: resolvedor.perfil(nome, raw) for nome, raw in arquivos.characters.items()},
    )


def _substats(arquivo: SubstatsFile) -> dict[str, SubstatTable]:
    padrao = arquivo.meta.tolerancia_padrao

    def tolerancia(stat: str, propria: float | None) -> float:
        if propria is not None:
            return propria
        return padrao.percentual if is_percent_stat(stat) else padrao.fixo

    return {
        stat: SubstatTable(valores=tuple(raw.valores), tolerancia=tolerancia(stat, raw.tolerancia))
        for stat, raw in arquivo.substatus.items()
    }


def _stats_conhecidos(substats: Mapping[str, SubstatTable], main_stats: Mapping[Custo, MainStatTable]) -> set[str]:
    principais = {stat for tabela in main_stats.values() for stat in (*tabela.primarios, *tabela.secundario)}
    return set(substats) | principais


def _indice(aliases: Mapping[str, list[str]], conhecidos: set[str], categoria: str, erros: list[str]) -> NameIndex:
    onde = f"stat_aliases.json › {categoria}"
    erros.extend(f"{onde} › {chave}: não existe no catálogo" for chave in sorted(aliases.keys() - conhecidos))
    indice = NameIndex.build({chave: aliases.get(chave, []) for chave in conhecidos})
    for nome, chaves in sorted(indice.ambiguous_names().items()):
        if not (categoria == "stats" and is_pct_flat_pair(chaves)):
            erros.append(f"{onde}: '{nome}' aponta para mais de uma chave {sorted(chaves)}")
    return indice


@dataclass(frozen=True)
class _Resolvedor:
    """Converte nomes escritos à mão (PT-BR, aliases) em chaves internas, acumulando erros."""

    stat_names: NameIndex
    echo_names: NameIndex
    set_names: NameIndex
    main_stats: Mapping[Custo, MainStatTable]
    erros: list[str]

    def set_info(self, nome: str, raw: SetRaw) -> SetInfo:
        onde = f"sets.json › {nome} › bonus"
        bonus = {pecas: self._stats(stats, f"{onde} › {pecas}") for pecas, stats in raw.bonus.items()}
        return SetInfo(pecas=raw.pecas, bonus=bonus)

    def perfil(self, nome: str, raw: PerfilRaw) -> Perfil:
        onde = f"characters.json › {nome}"
        base_campos = raw.model_dump(exclude={"personagem", "armas_assinatura", "variantes"})
        variantes = (
            self._variante(base_campos, variante, f"{onde} › variantes › {indice}")
            for indice, variante in enumerate(raw.variantes)
        )
        return Perfil(
            personagem=raw.personagem,
            armas_assinatura=frozenset(fold(arma) for arma in raw.armas_assinatura),
            base=self._spec(raw, onde),
            variantes=tuple(v for v in variantes if v is not None),
        )

    def _variante(self, base_campos: dict[str, Any], raw: VarianteRaw, onde: str) -> Variante | None:
        campos = base_campos | raw.model_dump(exclude={"condicao"}, exclude_unset=True)
        try:
            spec_raw = BuildSpecRaw.model_validate(campos)
        except ValidationError as erro:
            self.erros.extend(_formatar_erro(e, prefixo=onde) for e in erro.errors())
            return None
        return Variante(condicao=raw.condicao, spec=self._spec(spec_raw, onde))

    def _spec(self, raw: BuildSpecRaw, onde: str) -> BuildSpec:
        return BuildSpec(
            escala=raw.escala,
            regen_energia_min=raw.regen_energia_min,
            custos=tuple(raw.custos),
            set=self._nome(self.set_names, raw.set, f"{onde} › set"),
            echo_principal=self._nome(self.echo_names, raw.echo_principal, f"{onde} › echo_principal"),
            principais={
                CUSTO_POR_CHAVE[chave]: self._principais(chave, nomes, f"{onde} › principais › {chave}")
                for chave, nomes in raw.principais.items()
            },
            pesos=self._stats(raw.pesos, f"{onde} › pesos"),
        )

    def _nome(self, indice: NameIndex, nome: str | None, onde: str) -> str | None:
        if nome is None:
            return None
        resolvido = indice.resolve(nome)
        if resolvido is None:
            self.erros.append(f"{onde}: '{nome}' não está no catálogo nem nos aliases")
        return resolvido

    def _stat(self, nome: str, onde: str) -> str | None:
        stat = resolve_stat(self.stat_names, nome)
        if stat is None:
            self.erros.append(f"{onde}: status '{nome}' desconhecido ou ambíguo (ex.: use 'ATQ%' em vez de 'ATQ')")
        return stat

    def _principais(self, chave: CustoChave, nomes: list[str], onde: str) -> frozenset[str]:
        stats = frozenset(stat for stat in (self._stat(nome, onde) for nome in nomes) if stat)
        custo = CUSTO_POR_CHAVE[chave]
        invalidos = sorted(stats - set(self.main_stats[custo].primarios))
        if invalidos:
            self.erros.append(f"{onde}: {invalidos} não podem ser principal de echo custo {custo}")
        return stats

    def _stats(self, valores: Mapping[str, float], onde: str) -> dict[str, float]:
        resolvidos: dict[str, float] = {}
        for nome, valor in valores.items():
            stat = self._stat(nome, f"{onde} › {nome}")
            if stat is None:
                continue
            if stat in resolvidos:
                self.erros.append(f"{onde} › {nome}: {stat} aparece mais de uma vez")
            resolvidos[stat] = valor
        return resolvidos
