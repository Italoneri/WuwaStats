from typing import Any

import pytest
from pydantic import ValidationError

from wuwastats.domain.metas import MetaDeStatus, Veredito, comparar_meta, formatar_valor, metas_unicas

ROT: dict[str, Any] = {"tipo": "rotacao", "fonte": "prydwen"}
ESC: dict[str, Any] = {"tipo": "escala", "fonte": "game8"}

CASOS = [
    (MetaDeStatus(stat="energy_regen", min=105, max=130, **ROT), 100, "abaixo", "abaixo da meta, faltam 5%"),
    (MetaDeStatus(stat="energy_regen", min=105, max=130, **ROT), 130, "dentro", "dentro da faixa"),
    (MetaDeStatus(stat="energy_regen", min=105, max=130, **ROT), 131.5, "acima", "acima da faixa, 1.5% sobrando"),
    (MetaDeStatus(stat="energy_regen", min=120, **ROT), 200, "dentro", "dentro da faixa"),
    (MetaDeStatus(stat="crit_dmg", min=210, max=260, **ROT), 280, "acima", "acima da faixa, quanto mais melhor"),
    (MetaDeStatus(stat="energy_regen", min=250, **ESC), 240, "abaixo", "abaixo, perde poder"),
    (MetaDeStatus(stat="energy_regen", min=250, **ESC), 250, "acima", "no teto, o que passar sobra"),
    (MetaDeStatus(stat="energy_regen", min=125, max=150, **ESC), 130, "dentro", "rendendo, faltam 20% para o teto"),
    (MetaDeStatus(stat="hp_flat", min=50000, **ESC), 48000, "abaixo", "abaixo, perde poder"),
    (MetaDeStatus(stat="crit_rate", min=60, max=80, **ROT), None, None, None),
]


@pytest.mark.parametrize(("meta", "valor", "veredito", "mensagem"), CASOS)
def test_compara_meta_com_valor_lido(
    meta: MetaDeStatus, valor: float | None, veredito: Veredito | None, mensagem: str | None
) -> None:
    analise = comparar_meta(meta, valor, None if valor is None else "tela")

    assert (analise.meta, analise.valor, analise.veredito, analise.mensagem) == (meta, valor, veredito, mensagem)


def test_guarda_a_origem_do_valor() -> None:
    meta = MetaDeStatus(stat="energy_regen", min=120, **ROT)

    assert comparar_meta(meta, 125, "echos").origem == "echos"


@pytest.mark.parametrize(
    ("stat", "valor", "texto"),
    [("hp_flat", 50000, "50.000"), ("crit_rate", 62.5, "62.5%"), ("energy_regen", 105.0, "105%"), ("def_flat", 1234.6, "1.235")],
)
def test_formata_valor(stat: Any, valor: float, texto: str) -> None:
    assert formatar_valor(stat, valor) == texto


@pytest.mark.parametrize(
    ("campos", "erro"),
    [
        ({"stat": "energy_regen", "min": 105, "max": 100}, "max menor que min"),
        ({"stat": "energy_regen", "min": 90}, "começa em 100%"),
        ({"stat": "crit_rate", "min": 60, "explicacao": ""}, "explicacao"),
        ({"stat": "hp_pct", "min": 60}, "stat"),
    ],
)
def test_rejeita_meta_invalida(campos: dict[str, Any], erro: str) -> None:
    with pytest.raises(ValidationError, match=erro):
        MetaDeStatus(**campos, **ROT)


def test_rejeita_stat_repetido() -> None:
    metas = [MetaDeStatus(stat="crit_rate", min=60, **ROT), MetaDeStatus(stat="crit_rate", min=70, **ESC)]

    with pytest.raises(ValueError, match="meta de crit_rate repetida"):
        metas_unicas(metas)


def test_aceita_metas_de_stats_diferentes() -> None:
    metas = [MetaDeStatus(stat="crit_rate", min=60, **ROT), MetaDeStatus(stat="crit_dmg", min=210, **ROT)]

    assert metas_unicas(metas) == metas
