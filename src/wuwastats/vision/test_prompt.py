from wuwastats.domain.tables import GameData
from wuwastats.vision.prompt import prompt_echo


def test_prompt_lista_nomes_validos_de_status_sets_e_echos(dados: GameData) -> None:
    prompt = prompt_echo(dados)

    assert "Taxa CRIT / Crit Rate / CRIT Rate" in prompt
    assert "Regen. de Energia" in prompt
    assert "Moonlit Clouds" in prompt
    assert "Suhsin" in prompt
    assert "SOMENTE com um objeto JSON" in prompt
