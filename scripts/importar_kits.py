"""Importa o kit oficial (habilidades, multiplicadores, sequências, tags) dos ressonadores para data/kits.json.

    uv run python scripts/importar_kits.py --personagens Aemeath Yangyang Suoming
    uv run python scripts/importar_kits.py                     # todos os jogáveis

Texto e números vêm de Arikatsu/WutheringWaves_Data no commit de data/fonte_dados_jogo.json (ou --ref), com o textmap
PT (sem PT, usa o texto oficial em inglês e avisa). As imagens vêm de nanoka.cc e ficam em data/imagens/kit/; a barra do
forte não está nas tabelas do Arikatsu, então o caminho dela sai do JSON do personagem no nanoka. O texto em inglês desse
mesmo JSON serve de referência para apontar lixo no PT; as correções ficam em data/kit_correcoes.json. Só os personagens
pedidos são trocados em kits.json. Os resumos (data/kit_resumos.json) são escritos à mão e não são tocados aqui.
"""

import argparse
import io
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from importar_dados_jogo import (
    ARQUIVO_FONTE,
    CAMINHO_PERSONAGENS,
    CAMINHO_TEXTMAP,
    DOWNLOADS_SIMULTANEOS,
    RAW,
    REPOSITORIO,
    TIPO_PERSONAGEM_JOGAVEL,
    FonteIndisponivel,
    TextoFonte,
    _baixar,
    _Fonte,
    _textmap,
    url_do_icone,
)
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from revisao_kit import Correcao, corrigir, ler_correcoes, suspeitos

from wuwastats.config import PROJECT_ROOT
from wuwastats.gamedata.aliases import escrever_atomico
from wuwastats.gamedata.imagens import ImagemRecusada
from wuwastats.gamedata.kit_texto import Paragrafo, converter_texto, preencher
from wuwastats.gamedata.kits import (
    ARQUIVO_KITS,
    Bonus,
    Habilidade,
    ImagensDoKit,
    Kit,
    KitsFile,
    Multiplicador,
    Sequencia,
    TagKit,
)

CAMINHO_ARVORE = "BinData/skillTree/skilltree.json"
CAMINHO_HABILIDADES = "BinData/skill/skill.json"
CAMINHO_MULTIPLICADORES = "BinData/skill/skilldescription.json"
CAMINHO_TIPOS = "BinData/skill/skilltype.json"
CAMINHO_SEQUENCIAS = "BinData/resonate_chain/resonantchain.json"
CAMINHO_TAGS = "BinData/role/roletag.json"

NANOKA_PERSONAGEM = "https://static.nanoka.cc/ww/{versao}/en/character/{id}.json"
VERSAO_NANOKA = "3.8.1"

# SkillType: ordem em que o jogo mostra o kit (ATQ Normal, Habilidade, Circuito, Liberação, Intro, Outro).
ORDEM_HABILIDADES = (1, 2, 6, 3, 5, 11)
TIPO_CIRCUITO = 6
TIPOS_INERENTES = (4, 7, 8, 9, 10)
TIPO_RUPTURA = 12
NO_BONUS = 4
NIVEIS = 10


# --- Formato dos arquivos da fonte (só os campos usados) ---


class PersonagemKitFonte(_Fonte):
    id: int = Field(alias="Id")
    chave_nome: str = Field(alias="Name")
    tipo: int = Field(alias="RoleType")
    teste: bool = Field(alias="IsTrial")
    tags: list[int] = Field(alias="Tag")
    grupo_arvore: int = Field(alias="SkillTreeGroupId")
    grupo_sequencias: int = Field(alias="ResonantChainGroupId")


class NoFonte(_Fonte):
    indice: int = Field(alias="NodeIndex")
    grupo: int = Field(alias="NodeGroup")
    tipo: int = Field(alias="NodeType")
    habilidade: int = Field(alias="SkillId")
    titulo: str = Field(alias="PropertyNodeTitle")
    parametros: list[str] = Field(alias="PropertyNodeParam")


class HabilidadeKitFonte(_Fonte):
    id: int = Field(alias="Id")
    tipo: int = Field(alias="SkillType")
    chave_nome: str = Field(alias="SkillName")
    chave_descricao: str = Field(alias="SkillDescribe")
    parametros: list[str] = Field(alias="SkillDetailNum")
    icone: str = Field(alias="Icon")
    grupo_niveis: int = Field(alias="SkillLevelGroupId")


class ValoresFonte(_Fonte):
    valores: list[str] = Field(alias="ArrayString")


class MultiplicadorFonte(_Fonte):
    grupo_niveis: int = Field(alias="SkillLevelGroupId")
    chave_nome: str = Field(alias="AttributeName")
    chave_formato: str = Field(alias="Description")
    ordem: int = Field(alias="Order")
    detalhes: list[ValoresFonte] = Field(alias="SkillDetailNum")


class SequenciaFonte(_Fonte):
    grupo: int = Field(alias="GroupId")
    numero: int = Field(alias="GroupIndex")
    chave_nome: str = Field(alias="NodeName")
    chave_descricao: str = Field(alias="AttributesDescription")
    parametros: list[str] = Field(alias="AttributesDescriptionParams")
    icone: str = Field(alias="NodeIcon")


class TagFonte(_Fonte):
    id: int = Field(alias="Id")
    chave_nome: str = Field(alias="TagName")
    chave_descricao: str = Field(alias="TagDesc")
    cor: str = Field(alias="TagNameColor")


class TipoFonte(_Fonte):
    id: int = Field(alias="Id")
    chave_nome: str = Field(alias="TypeName")


class ForteNanoka(BaseModel):
    icon: str = ""


class InstrucaoNanoka(BaseModel):
    image_list: list[str] = []


class PassoNanoka(BaseModel):
    desc: dict[str, InstrucaoNanoka] = {}


class ForteNovoNanoka(BaseModel):
    instructions: dict[str, PassoNanoka] = {}


class TextoNanoka(BaseModel):
    desc: str = ""


class NoNanoka(BaseModel):
    skill: TextoNanoka = TextoNanoka()


class PersonagemNanoka(BaseModel):
    """JSON do personagem no nanoka (em inglês): ilustrações do forte e o texto que serve de referência para o PT."""

    forte: ForteNanoka = ForteNanoka()
    forte_new: ForteNovoNanoka = ForteNovoNanoka()
    skill_trees: dict[str, NoNanoka] = {}
    chains: dict[str, TextoNanoka] = {}

    def texto_habilidade(self, indice_no: int) -> str:
        no = self.skill_trees.get(str(indice_no))
        return no.skill.desc if no else ""

    def texto_sequencia(self, numero: int) -> str:
        sequencia = self.chains.get(str(numero))
        return sequencia.desc if sequencia else ""


@dataclass(frozen=True)
class TabelasKit:
    personagens: list[PersonagemKitFonte]
    nos: list[NoFonte]
    habilidades: list[HabilidadeKitFonte]
    multiplicadores: list[MultiplicadorFonte]
    sequencias: list[SequenciaFonte]
    tags: list[TagFonte]
    tipos: list[TipoFonte]
    textos_pt: Mapping[str, str]
    textos_en: Mapping[str, str]


@dataclass(frozen=True)
class ImagemKit:
    nome: str
    url: str


class KitIncompleto(Exception):
    pass


@dataclass
class _Textos:
    """Texto PT oficial com as correções do personagem; sem PT, o oficial em inglês, e o aviso fica registrado.

    O inglês do nanoka é a referência para apontar parágrafo PT com lixo.
    """

    tabelas: TabelasKit
    nanoka: PersonagemNanoka
    correcoes: Sequence[Correcao] = ()
    avisos: list[str] = field(default_factory=list)
    correcoes_usadas: set[int] = field(default_factory=set)

    def __call__(self, chave: str) -> str:
        texto = self.tabelas.textos_pt.get(chave, "").strip()
        if texto:
            corrigido, usadas = corrigir(texto, self.correcoes)
            self.correcoes_usadas |= usadas
            return corrigido
        self.avisos.append(f"{chave} sem PT; usado o texto em inglês")
        return self.tabelas.textos_en.get(chave, "").strip()

    def paragrafos(self, chave: str, parametros: Sequence[str], ingles: str) -> list[Paragrafo]:
        """`ingles` é o mesmo texto no nanoka; vazio quando o nanoka não tem, e aí não há conferência."""
        paragrafos, avisos = converter_texto(self(chave), parametros)
        if ingles:
            avisos += suspeitos(paragrafos, converter_texto(ingles, parametros)[0])
        self.avisos.extend(f"{chave}: {aviso}" for aviso in avisos)
        return paragrafos

    def correcoes_sem_uso(self) -> list[str]:
        return [
            f"correção não achou o trecho '{c.trecho}' (confira kit_correcoes.json)"
            for i, c in enumerate(self.correcoes)
            if i not in self.correcoes_usadas
        ]


# --- Montagem do kit (puro) ---


def montar_kit(
    tabelas: TabelasKit,
    personagem: PersonagemKitFonte,
    nanoka: PersonagemNanoka,
    correcoes: Sequence[Correcao] = (),
) -> tuple[Kit, list[ImagemKit], list[str]]:
    textos = _Textos(tabelas, nanoka, correcoes)
    imagens: list[ImagemKit] = []
    nos = sorted((no for no in tabelas.nos if no.grupo == personagem.grupo_arvore), key=lambda no: no.indice)
    por_tipo = _habilidades_por_tipo(tabelas, nos)
    forte = [nome for i, caminho in enumerate(caminhos_do_forte(nanoka), 1) if (nome := _imagem(f"forte-{i}", caminho, imagens))]

    def habilidade(no: NoFonte, fonte: HabilidadeKitFonte) -> Habilidade:
        return _habilidade(tabelas, textos, no, fonte, imagens, forte if fonte.tipo == TIPO_CIRCUITO else [])

    principais = [habilidade(no, fonte) for tipo in ORDEM_HABILIDADES for no, fonte in por_tipo.get(tipo, [])]
    inerentes = sorted((par for tipo in TIPOS_INERENTES for par in por_tipo.get(tipo, [])), key=lambda par: par[0].indice)
    ruptura = por_tipo.get(TIPO_RUPTURA, [])
    kit = Kit(
        id_jogo=personagem.id,
        tags=_tags(tabelas, textos, personagem),
        habilidades=principais,
        inerentes=[habilidade(no, fonte) for no, fonte in [*inerentes, *ruptura]],
        bonus=_bonus(textos, nos),
        sequencias=_sequencias(tabelas, textos, personagem, imagens),
    )
    return kit, imagens, [*textos.avisos, *textos.correcoes_sem_uso()]


def _habilidades_por_tipo(tabelas: TabelasKit, nos: list[NoFonte]) -> dict[int, list[tuple[NoFonte, HabilidadeKitFonte]]]:
    por_id = {h.id: h for h in tabelas.habilidades}
    por_tipo: dict[int, list[tuple[NoFonte, HabilidadeKitFonte]]] = {}
    for no in nos:
        if no.tipo == NO_BONUS:
            continue
        fonte = por_id.get(no.habilidade)
        if fonte is None:
            raise KitIncompleto(f"nó {no.indice} aponta para a habilidade {no.habilidade}, que não existe")
        por_tipo.setdefault(fonte.tipo, []).append((no, fonte))
    return por_tipo


def _habilidade(
    tabelas: TabelasKit,
    textos: _Textos,
    no: NoFonte,
    fonte: HabilidadeKitFonte,
    imagens: list[ImagemKit],
    ilustracoes: list[str],
) -> Habilidade:
    tipos = {t.id: t.chave_nome for t in tabelas.tipos}
    return Habilidade(
        tipo=textos(tipos[fonte.tipo]) if fonte.tipo in tipos else "",
        nome=_uma_linha(textos(fonte.chave_nome)),
        imagem=_imagem(f"habilidade-{no.indice}", fonte.icone, imagens),
        ilustracoes=ilustracoes,
        descricao=textos.paragrafos(fonte.chave_descricao, fonte.parametros, textos.nanoka.texto_habilidade(no.indice)),
        multiplicadores=_multiplicadores(tabelas, textos, fonte.grupo_niveis),
    )


def _multiplicadores(tabelas: TabelasKit, textos: _Textos, grupo: int) -> list[Multiplicador]:
    linhas = sorted((m for m in tabelas.multiplicadores if m.grupo_niveis == grupo and m.detalhes), key=lambda m: m.ordem)
    return [
        Multiplicador(
            nome=textos(linha.chave_nome), valores=[_formatado(textos, linha, v) for v in linha.detalhes[0].valores[:NIVEIS]]
        )
        for linha in linhas
    ]


def _formatado(textos: _Textos, linha: MultiplicadorFonte, valor: str) -> str:
    return preencher(textos(linha.chave_formato), [valor]) if linha.chave_formato else valor


def _tags(tabelas: TabelasKit, textos: _Textos, personagem: PersonagemKitFonte) -> list[TagKit]:
    por_id = {t.id: t for t in tabelas.tags}
    return [
        TagKit(nome=textos(t.chave_nome), descricao=textos(t.chave_descricao), cor=t.cor)
        for t in (por_id[i] for i in personagem.tags if i in por_id)
    ]


def _bonus(textos: _Textos, nos: list[NoFonte]) -> list[Bonus]:
    """Os nós de status da árvore somados por nome: 'ATQ+' 1,80% + 4,20% → 'ATQ' 6%."""
    somas: dict[str, tuple[float, str]] = {}
    for no in (n for n in nos if n.tipo == NO_BONUS and n.parametros):
        nome = textos(no.titulo).rstrip("+").strip()
        bruto = no.parametros[0]
        sufixo = "%" if bruto.endswith("%") else ""
        try:
            valor = float(bruto.rstrip("%"))
        except ValueError:
            textos.avisos.append(f"bônus '{nome}' do nó {no.indice} com valor '{bruto}' fora do formato; ignorado")
            continue
        anterior, _ = somas.get(nome, (0.0, sufixo))
        somas[nome] = (anterior + valor, sufixo)
    return [Bonus(nome=nome, valor=f"{_numero(total)}{sufixo}") for nome, (total, sufixo) in somas.items()]


def _numero(valor: float) -> str:
    return f"{valor:.2f}".rstrip("0").rstrip(".")


def _sequencias(
    tabelas: TabelasKit, textos: _Textos, personagem: PersonagemKitFonte, imagens: list[ImagemKit]
) -> list[Sequencia]:
    linhas = sorted((s for s in tabelas.sequencias if s.grupo == personagem.grupo_sequencias), key=lambda s: s.numero)
    return [
        Sequencia(
            numero=s.numero,
            nome=_uma_linha(textos(s.chave_nome)),
            imagem=_imagem(f"sequencia-{s.numero}", s.icone, imagens),
            descricao=textos.paragrafos(s.chave_descricao, s.parametros, textos.nanoka.texto_sequencia(s.numero)),
        )
        for s in linhas
    ]


def _imagem(nome: str, caminho: str | None, imagens: list[ImagemKit]) -> str | None:
    url = url_do_icone(caminho or "")
    if url is None:
        return None
    imagens.append(ImagemKit(nome, url))
    return nome


def _uma_linha(texto: str) -> str:
    return " ".join(texto.split())


# --- Imagens ---


def baixar_imagens(
    imagens: ImagensDoKit, chave: str, lista: Sequence[ImagemKit], baixar: Callable[[str], bytes] = _baixar
) -> list[str]:
    """Baixa as que faltam; uma imagem que não veio vira aviso (a página desenha placeholder)."""
    faltando = [imagem for imagem in lista if not imagens.existe(chave, imagem.nome)]

    def salvar(imagem: ImagemKit) -> str | None:
        try:
            imagens.salvar(chave, imagem.nome, baixar(imagem.url))
        except (FonteIndisponivel, ImagemRecusada) as erro:
            return f"imagem {chave} '{imagem.nome}': {erro}"
        return None

    with ThreadPoolExecutor(max_workers=DOWNLOADS_SIMULTANEOS) as pool:
        return [falha for falha in pool.map(salvar, faltando) if falha]


def baixar_nanoka(id_jogo: int, versao: str, baixar: Callable[[str], bytes] = _baixar) -> tuple[PersonagemNanoka, str | None]:
    """JSON do personagem no nanoka; se não vier, um vazio (sem forte e sem conferência do texto) e o aviso."""
    url = NANOKA_PERSONAGEM.format(versao=versao, id=id_jogo)
    try:
        return PersonagemNanoka.model_validate_json(baixar(url)), None
    except (FonteIndisponivel, ValidationError) as erro:
        return PersonagemNanoka(), f"nanoka de {id_jogo} (ilustrações do forte e conferência do texto): {erro}"


def caminhos_do_forte(nanoka: PersonagemNanoka) -> list[str]:
    """Personagens antigos têm uma imagem só (forte.icon); os novos, uma por instrução (forte_new), sem repetir."""
    if nanoka.forte.icon:
        return [nanoka.forte.icon]
    passos = nanoka.forte_new.instructions.values()
    caminhos = [c for passo in passos for instrucao in passo.desc.values() for c in instrucao.image_list]
    return list(dict.fromkeys(caminhos))


# --- Execução ---


def main(argv: list[str] | None = None) -> int:
    for saida in (sys.stdout, sys.stderr):
        if isinstance(saida, io.TextIOWrapper):
            saida.reconfigure(encoding="utf-8")
    args = _argumentos(argv)
    data_dir: Path = args.data_dir
    sha = args.ref or json.loads((data_dir / ARQUIVO_FONTE).read_text(encoding="utf-8"))["commit"]
    try:
        print(f"Fonte: {REPOSITORIO}@{sha[:10]}")
        tabelas = baixar_tabelas(sha)
    except FonteIndisponivel as erro:
        print(f"Erro ao baixar a fonte: {erro}", file=sys.stderr)
        return 1

    escolhidos, avisos = _escolher(tabelas, args.personagens)
    correcoes = ler_correcoes(data_dir)
    kits: dict[str, Kit] = {}
    imagens = ImagensDoKit(data_dir)
    for chave, personagem in escolhidos.items():
        nanoka, aviso_nanoka = baixar_nanoka(personagem.id, args.versao_nanoka)
        avisos.extend([aviso_nanoka] if aviso_nanoka else [])
        try:
            kit, lista, avisos_kit = montar_kit(tabelas, personagem, nanoka, correcoes.get(chave, []))
        except KitIncompleto as erro:
            avisos.append(f"{chave}: kit não importado ({erro})")
            continue
        kits[chave] = kit
        avisos.extend(f"{chave}: {aviso}" for aviso in avisos_kit)
        avisos.extend(baixar_imagens(imagens, chave, lista))
        print(f"  {chave}: {len(kit.habilidades)} habilidades, {len(kit.inerentes)} inerentes, {len(kit.sequencias)} sequências")

    _gravar(data_dir, sha, kits)
    print(f"\n{len(kits)} kit(s) gravado(s) em {ARQUIVO_KITS}.")
    if avisos:
        print(f"\nAvisos ({len(avisos)}):")
        print("\n".join(f"  - {aviso}" for aviso in avisos))
    return 0


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--personagens", nargs="*", help="nomes em inglês (chaves de resonators.json); padrão: todos")
    parser.add_argument("--ref", help=f"commit da fonte; padrão: o de {ARQUIVO_FONTE}")
    parser.add_argument(
        "--versao-nanoka", default=VERSAO_NANOKA, help="versão dos dados do nanoka (barra do forte e texto de referência)"
    )
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    return parser.parse_args(argv)


def baixar_tabelas(sha: str) -> TabelasKit:
    def tabela[T](caminho: str, formato: TypeAdapter[list[T]]) -> list[T]:
        print(f"  baixando {caminho}")
        return formato.validate_json(_baixar(f"{RAW}/{sha}/{caminho}"))

    textmap = TypeAdapter(list[TextoFonte])
    return TabelasKit(
        personagens=tabela(CAMINHO_PERSONAGENS, TypeAdapter(list[PersonagemKitFonte])),
        nos=tabela(CAMINHO_ARVORE, TypeAdapter(list[NoFonte])),
        habilidades=tabela(CAMINHO_HABILIDADES, TypeAdapter(list[HabilidadeKitFonte])),
        multiplicadores=tabela(CAMINHO_MULTIPLICADORES, TypeAdapter(list[MultiplicadorFonte])),
        sequencias=tabela(CAMINHO_SEQUENCIAS, TypeAdapter(list[SequenciaFonte])),
        tags=tabela(CAMINHO_TAGS, TypeAdapter(list[TagFonte])),
        tipos=tabela(CAMINHO_TIPOS, TypeAdapter(list[TipoFonte])),
        textos_pt=_textmap(tabela(CAMINHO_TEXTMAP.format(idioma="pt"), textmap)),
        textos_en=_textmap(tabela(CAMINHO_TEXTMAP.format(idioma="en"), textmap)),
    )


def _escolher(tabelas: TabelasKit, nomes: Sequence[str] | None) -> tuple[dict[str, PersonagemKitFonte], list[str]]:
    """Chave = nome em inglês (a de resonators.json). Rover tem uma linha por gênero: fica a primeira."""
    jogaveis: dict[str, PersonagemKitFonte] = {}
    for personagem in tabelas.personagens:
        nome = tabelas.textos_en.get(personagem.chave_nome, "").strip()
        if personagem.tipo == TIPO_PERSONAGEM_JOGAVEL and not personagem.teste and nome:
            jogaveis.setdefault(nome, personagem)
    if not nomes:
        return jogaveis, []
    avisos = [f"'{nome}' não é um ressonador jogável na fonte" for nome in nomes if nome not in jogaveis]
    return {nome: jogaveis[nome] for nome in nomes if nome in jogaveis}, avisos


def _gravar(data_dir: Path, sha: str, novos: Mapping[str, Kit]) -> None:
    caminho = data_dir / ARQUIVO_KITS
    atuais = KitsFile.model_validate_json(caminho.read_bytes()).kits if caminho.is_file() else {}
    kits = dict(sorted({**atuais, **novos}.items()))
    meta = {
        "descricao": "Kit oficial dos ressonadores, gerado por scripts/importar_kits.py. Não edite à mão: a próxima "
        "importação sobrescreve. Resumos ficam em kit_resumos.json.",
        "repositorio": REPOSITORIO,
        "commit": sha,
        "importado_em": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    escrever_atomico(caminho, {"_meta": meta, "kits": {chave: kit.model_dump() for chave, kit in kits.items()}})


if __name__ == "__main__":
    raise SystemExit(main())
