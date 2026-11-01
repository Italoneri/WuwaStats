from wuwastats.gamedata.historico import AnaliseSalva


def test_abre_analise_salva_antes_dos_atributos_da_tela() -> None:
    salva = {
        "id": "20261031-120000-abcdef",
        "nome": "Antiga",
        "build": "Suoming_DPS",
        "criado_em": "2026-10-31T12:00:00",
        "score_medio_pct": 43.1,
        "nota_media": "B",
        "entrada": {
            "build": "Suoming_DPS",
            "regen_total_informado": 145.2,
            "echos": [{"custo": 4, "principal": {"stat": "Dano CRIT", "valor": 44}}],
        },
    }

    assert AnaliseSalva.model_validate(salva).entrada.atributos == ()
