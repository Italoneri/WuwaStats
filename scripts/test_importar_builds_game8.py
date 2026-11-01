import pytest
from importar_builds_game8 import (
    BlocoGame8,
    BuildGerada,
    chave_da_build,
    escolher_personagens,
    ler_blocos,
    links_da_home,
    mesclar,
    meta_de_regen,
    montar_build,
    nomes_no_game8,
)

from wuwastats.config import PROJECT_ROOT
from wuwastats.domain.tables import GameData
from wuwastats.gamedata.loader import load_game_data

GAMEDATA_FIXTURE = PROJECT_ROOT / "fixtures" / "gamedata"


def _link(nome: str) -> str:
    return f'<a class="a-link" href="https://game8.co/games/Wuthering-Waves/archives/1"><img alt="x"> {nome}</a>'


# Mesma estrutura das páginas do Game8, com conteúdo inventado.
PAGINA = f"""
<h2>Build Guide</h2>
<h3 class="a-header--3">Electro DPS Build </h3>
<table class="a-table">
  <tr><th>Best Weapon</th><td><div class="align">{_link("Test Weapon")}</div></td></tr>
  <tr><th>Alt. Weapons</th>
    <td><div class="align">{_link("Alt Weapon")}</div><div class="align">{_link("Arma Fantasma")}</div></td></tr>
  <tr><th>Sonata Effect</th><td><div class="align"><b>5-pc</b>: {_link("Moonlit Clouds")}</div></td></tr>
  <tr><th>Cost Pattern</th><td><span>4 3 3 1 1</span></td></tr>
  <tr><th>Main Echo</th><td>{_link("Suhsin")}</td></tr>
</table>
<h4>Best Echo Stats</h4>
<table class="a-table">
  <tr><th colspan="3">Echo Main Stats Priority</th></tr>
  <tr><th>4 COST</th><th>3 COST</th><th>1 COST</th></tr>
  <tr><td class="center">Crit DMG or Crit Rate</td><td class="center">Electro DMG and ATK</td><td class="center">ATK%</td></tr>
  <tr><th colspan="3">Echo Substats Tuning Priority</th></tr>
  <tr><td colspan="3">1. CRIT DMG ★★★<br> 2. Energy Regen ★★<br> 3. Flat ATK ★<br> 4. Sorte ★<br></td></tr>
</table>
<p class="a-paragraph">Aim to reach <b>115-120% Energy Regen</b> every rotation.</p>
<h3 class="a-header--3">Test Weapon is the Best In Slot</h3>
<table class="a-table"><tr><th>Best Weapon</th><td>{_link("Test Weapon")}</td></tr></table>
<h2>Best Teams</h2>
<h3 class="a-header--3">Não é build</h3>
"""


@pytest.fixture(scope="module")
def dados() -> GameData:
    return load_game_data(GAMEDATA_FIXTURE)


def test_le_so_blocos_de_build_e_ignora_a_tabela_da_arma() -> None:
    blocos = ler_blocos(PAGINA)

    assert len(blocos) == 1
    bloco = blocos[0]
    assert (bloco.titulo, bloco.melhor_arma) == ("Electro DPS Build", "Test Weapon")
    assert bloco.alternativas == ("Alt Weapon", "Arma Fantasma")
    assert (bloco.sets, bloco.custos, bloco.echo_principal) == ((("Moonlit Clouds", 5),), (4, 3, 3, 1, 1), "Suhsin")
    assert bloco.principais == {"4": "Crit DMG or Crit Rate", "3": "Electro DMG and ATK", "1": "ATK%"}
    assert bloco.substatus == (("CRIT DMG", 3), ("Energy Regen", 2), ("Flat ATK", 1), ("Sorte", 1))


def test_monta_build_com_chaves_do_catalogo_e_marca_o_que_nao_reconheceu(dados: GameData) -> None:
    build = montar_build("Suoming", ler_blocos(PAGINA)[0], dados)

    assert build.chave == "Suoming_Electro_DPS"
    assert build.perfil["armas"] == {"melhor": "Test Weapon", "alternativas": ["Alt Weapon"]}
    assert build.perfil["principais"] == {"4": ["crit_dmg", "crit_rate"], "3": ["electro_dmg", "atk_pct"], "1": ["atk_pct"]}
    assert build.perfil["estrelas"] == {"crit_dmg": 3, "energy_regen": 2, "atk_flat": 1}
    assert build.perfil["sets"] == {"Moonlit Clouds": 5}
    assert (build.perfil["escala"], build.perfil["regen_energia_min"]) == ("ATQ", 115)
    assert build.avisos == ["arma 'Arma Fantasma' não está no catálogo", "substatus 'Sorte' não reconhecido"]
    assert build.perfil["status"].startswith("TODO: arma 'Arma Fantasma'")


def _bloco(texto: str = "Aim for 120% Energy Regen.", sets: tuple[tuple[str, int | None], ...] = ()) -> BlocoGame8:
    return BlocoGame8(
        titulo="Healer Build",
        melhor_arma=None,
        alternativas=(),
        sets=sets,
        custos=(4, 3, 3, 1, 1),
        echo_principal=None,
        principais={"1": "HP%"},
        substatus=(),
        texto=texto,
    )


def test_sem_meta_de_regen_fica_100_com_todo(dados: GameData) -> None:
    build = montar_build("Shorekeeper", _bloco(texto="Heals the team."), dados)

    assert (build.perfil["regen_energia_min"], build.perfil["escala"]) == (100, "HP")
    assert build.avisos == ["o Game8 não cita meta de Regen. de Energia; ficou 100"]


def test_le_e_guarda_combinacao_de_sets() -> None:
    celula = f"<b>3-pc</b> : {_link('Moonlit Clouds')} <b>2-pc</b> : {_link('Heart of Sworn Vigil')}"
    pagina = PAGINA.replace(f"<b>5-pc</b>: {_link('Moonlit Clouds')}", celula)

    assert ler_blocos(pagina)[0].sets == (("Moonlit Clouds", 3), ("Heart of Sworn Vigil", 2))


def test_set_sem_numero_de_pecas_usa_o_tamanho_do_set(dados: GameData) -> None:
    build = montar_build("Shorekeeper", _bloco(sets=(("Moonlit Clouds", None), ("Heart of Sworn Vigil", None))), dados)

    assert build.perfil["sets"] == {"Moonlit Clouds": 5}
    assert build.avisos == ["set 'Heart of Sworn Vigil': o site não diz quantas peças e sets.json não sabe o tamanho"]


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("aim to reach 115-120% Energy Regen", 115),
        ("Aim for 250% Energy Regen", 250),
        ("around 115% to 120% Energy Regen", 115),
        ("Basic Attack DMG 25% Energy Regen 115% Stats shown", 115),
        ("prioritize getting her ER to around 120% , followed by", 120),
        ("As for Energy Regen , we recommend you get her to 120% to have", 120),
        ("gives 12% Energy Regen", None),
        ("Energy Regen 12% bonus", None),
        ("no target here", None),
    ],
)
def test_acha_a_meta_de_regen_no_texto(texto: str, esperado: int | None) -> None:
    assert meta_de_regen(texto) == esperado


@pytest.mark.parametrize(
    ("personagem", "titulo", "esperado"),
    [
        ("Hsin", "Unison/Electro Flare DPS Build", "Hsin_Unison_Electro_Flare_DPS"),
        ("Rover: Havoc", "Rover Havoc Burst DPS Build", "Rover_Havoc_Burst_DPS"),
        ("Jingran", "Fusion DPS Build (w/ Sig)", "Jingran_Fusion_DPS_w_Sig"),
    ],
)
def test_gera_chave_valida_a_partir_do_titulo(personagem: str, titulo: str, esperado: str) -> None:
    assert chave_da_build(personagem, titulo) == esperado


def test_acha_links_e_o_nome_do_rover_no_game8() -> None:
    relativo = '<a href="/games/Wuthering-Waves/archives/9">Rover (Havoc)</a>'
    home = relativo + relativo.replace('href="', 'href="https://game8.co')

    assert links_da_home(home) == {"Rover (Havoc)": ["https://game8.co/games/Wuthering-Waves/archives/9"]}
    assert nomes_no_game8("Rover: Havoc") == ["Rover: Havoc", "Rover (Havoc)"]


def test_sem_substituir_preserva_quem_ja_tem_build(dados: GameData) -> None:
    atuais = {"Suoming_Mao": {"personagem": "Suoming"}}

    assert escolher_personagens(dados, atuais, None, substituir=False) == ["Shorekeeper"]
    assert escolher_personagens(dados, atuais, ["Suoming"], substituir=True) == ["Suoming"]


def test_substituir_troca_so_as_builds_dos_personagens_gerados() -> None:
    atuais = {"Suoming_Mao": {"personagem": "Suoming"}, "Shorekeeper_Mao": {"personagem": "Shorekeeper"}}
    nova = BuildGerada(chave="Suoming_Game8", perfil={"personagem": "Suoming"})

    resultado = mesclar(atuais, [nova], {"Suoming"})

    assert resultado == {"Shorekeeper_Mao": {"personagem": "Shorekeeper"}, "Suoming_Game8": {"personagem": "Suoming"}}
