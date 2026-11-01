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
    Arma,
    ArmasPerfil,
    BuildSpec,
    EchoInfo,
    FaixaNota,
    GameData,
    MainStatTable,
    Perfil,
    Ressonador,
    SetInfo,
    SubstatTable,
    Traducao,
    Variante,
)
from wuwastats.gamedata.schemas import (
    CUSTO_POR_CHAVE,
    ArmasPerfilRaw,
    ArquivosDeDados,
    BuildSpecRaw,
    CustoChave,
    EchoRaw,
    PerfilRaw,
    ResonatorsFile,
    SetRaw,
    SubstatsFile,
    VarianteRaw,
    WeaponsFile,
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
    _conferir_elenco(arquivos.resonators, arquivos.weapons, erros)
    ressonador_names = _indice_pt({nome: r.nome_pt for nome, r in arquivos.resonators.ressonadores.items()}, "resonators", erros)
    arma_names = _indice_pt({nome: a.nome_pt for nome, a in arquivos.weapons.armas.items()}, "weapons", erros)
    pecas_dos_sets = {nome: raw.pecas for nome, raw in arquivos.sets.sets.items()}
    nomes = (stat_names, echo_names, set_names, ressonador_names, arma_names)
    resolvedor = _Resolvedor(*nomes, main_stats, pecas_dos_sets, erros)
    return GameData(
        substats=substats,
        main_stats=main_stats,
        sets={nome: resolvedor.set_info(nome, raw) for nome, raw in arquivos.sets.sets.items()},
        echoes={nome: _echo_info(raw) for nome, raw in arquivos.echoes.echoes.items()},
        echos_repetidos_contam=arquivos.sets.meta.echos_repetidos_contam,
        stat_names=stat_names,
        echo_names=echo_names,
        set_names=set_names,
        perfis={nome: resolvedor.perfil(nome, raw) for nome, raw in arquivos.characters.items()},
        notas=tuple(FaixaNota(nota=f.nota, min=f.min) for f in arquivos.notas.faixas),
        elementos={chave: Traducao(en=t.en, pt=t.pt) for chave, t in arquivos.resonators.elementos.items()},
        tipos_arma={chave: Traducao(en=t.en, pt=t.pt) for chave, t in arquivos.resonators.tipos_arma.items()},
        ressonadores={
            nome: Ressonador(elemento=r.elemento, tipo_arma=r.tipo_arma, raridade=r.raridade)
            for nome, r in arquivos.resonators.ressonadores.items()
        },
        armas={nome: Arma(tipo=a.tipo, raridade=a.raridade) for nome, a in arquivos.weapons.armas.items()},
        ressonador_names=ressonador_names,
        arma_names=arma_names,
    )


def _echo_info(raw: EchoRaw) -> EchoInfo:
    habilidade = Traducao(en=raw.habilidade.en, pt=raw.habilidade.pt) if raw.habilidade else None
    return EchoInfo(custo=raw.custo, sets=tuple(raw.sets), habilidade=habilidade)


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


def _conferir_elenco(ressonadores: ResonatorsFile, armas: WeaponsFile, erros: list[str]) -> None:
    for nome, r in ressonadores.ressonadores.items():
        onde = f"resonators.json › ressonadores › {nome}"
        if r.elemento not in ressonadores.elementos:
            erros.append(f"{onde} › elemento: '{r.elemento}' não existe em elementos")
        if r.tipo_arma not in ressonadores.tipos_arma:
            erros.append(f"{onde} › tipo_arma: '{r.tipo_arma}' não existe em tipos_arma")
    erros.extend(
        f"weapons.json › armas › {nome} › tipo: '{a.tipo}' não existe em tipos_arma de resonators.json"
        for nome, a in armas.armas.items()
        if a.tipo not in ressonadores.tipos_arma
    )


def _indice_pt(nomes_pt: Mapping[str, str | None], arquivo: str, erros: list[str]) -> NameIndex:
    """Chave em inglês + nome PT (primeiro, para virar o rótulo)."""
    indice = NameIndex.build({chave: [pt] if pt else [] for chave, pt in nomes_pt.items()})
    erros.extend(
        f"{arquivo}.json: '{nome}' aponta para mais de uma chave {sorted(chaves)}"
        for nome, chaves in sorted(indice.ambiguous_names().items())
    )
    return indice


@dataclass(frozen=True)
class _Resolvedor:
    """Converte nomes escritos à mão (PT-BR, aliases) em chaves internas, acumulando erros."""

    stat_names: NameIndex
    echo_names: NameIndex
    set_names: NameIndex
    ressonador_names: NameIndex
    arma_names: NameIndex
    main_stats: Mapping[Custo, MainStatTable]
    pecas_dos_sets: Mapping[str, int | None]
    erros: list[str]

    def set_info(self, nome: str, raw: SetRaw) -> SetInfo:
        onde = f"sets.json › {nome} › bonus"
        bonus = {pecas: self._stats(stats, f"{onde} › {pecas}") for pecas, stats in raw.bonus.items()}
        return SetInfo(pecas=raw.pecas, bonus=bonus)

    def perfil(self, nome: str, raw: PerfilRaw) -> Perfil:
        onde = f"characters.json › {nome}"
        base_campos = raw.model_dump(exclude={"personagem", "armas_assinatura", "armas", "variantes", "descricao", "status"})
        variantes = (
            self._variante(base_campos, variante, f"{onde} › variantes › {indice}")
            for indice, variante in enumerate(raw.variantes)
        )
        return Perfil(
            personagem=self._nome(self.ressonador_names, raw.personagem, f"{onde} › personagem") or raw.personagem,
            armas_assinatura=self._armas_assinatura(raw.armas_assinatura),
            base=self._spec(raw, onde),
            variantes=tuple(v for v in variantes if v is not None),
            armas=self._armas(raw.armas, f"{onde} › armas") if raw.armas else None,
            descricao=raw.descricao,
        )

    def _armas_assinatura(self, nomes: list[str]) -> frozenset[str]:
        """A tela do personagem mostra a arma em PT: uma arma do catálogo vale por todos os nomes dela."""
        todos: set[str] = set()
        for nome in nomes:
            chave = self.arma_names.resolve(nome)
            todos |= {nome, *((chave, *self.arma_names.aliases_by_key.get(chave, ())) if chave else ())}
        return frozenset(fold(nome) for nome in todos)

    def _armas(self, raw: ArmasPerfilRaw, onde: str) -> ArmasPerfil:
        alternativas = (self._nome(self.arma_names, nome, f"{onde} › alternativas") for nome in raw.alternativas)
        return ArmasPerfil(
            melhor=self._nome(self.arma_names, raw.melhor, f"{onde} › melhor"),
            alternativas=tuple(a for a in alternativas if a),
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
            custos=tuple(raw.custos),
            sets=self._sets(raw.sets, f"{onde} › sets"),
            echo_principal=self._nome(self.echo_names, raw.echo_principal, f"{onde} › echo_principal"),
            principais={
                CUSTO_POR_CHAVE[chave]: self._principais(chave, nomes, f"{onde} › principais › {chave}")
                for chave, nomes in raw.principais.items()
            },
            estrelas=self._stats(raw.estrelas, f"{onde} › estrelas"),
            metas=tuple(raw.metas),
        )

    def _sets(self, pedidos: Mapping[str, int], onde: str) -> dict[str, int]:
        """Nenhum set pode pedir mais peças do que tem (a soma até 5 o schema já conferiu)."""
        sets: dict[str, int] = {}
        for nome, pecas in pedidos.items():
            chave = self._nome(self.set_names, nome, f"{onde} › {nome}")
            maximo = self.pecas_dos_sets.get(chave) if chave else None
            if chave and maximo is not None and pecas > maximo:
                self.erros.append(f"{onde} › {nome}: {chave} tem {maximo} peças; a build pede {pecas}")
            if chave:
                sets[chave] = pecas
        return sets

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

    def _stats[V](self, valores: Mapping[str, V], onde: str) -> dict[str, V]:
        resolvidos: dict[str, V] = {}
        for nome, valor in valores.items():
            stat = self._stat(nome, f"{onde} › {nome}")
            if stat is None:
                continue
            if stat in resolvidos:
                self.erros.append(f"{onde} › {nome}: {stat} aparece mais de uma vez")
            resolvidos[stat] = valor
        return resolvidos
