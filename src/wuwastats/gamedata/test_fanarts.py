from pathlib import Path

import pytest
from PIL import Image

from wuwastats.gamedata.fanarts import Credito, CreditoRecusado, Enquadramento, FanartsDoCatalogo, validar_credito
from wuwastats.gamedata.imagens import ImagemRecusada
from wuwastats.gamedata.test_imagens import imagem

CREDITO = Credito(artista="@fulano", link="https://www.pixiv.net/artworks/1")


def test_grava_webp_reduzido_e_le_o_credito(tmp_path: Path) -> None:
    fanarts = FanartsDoCatalogo(tmp_path)

    fanarts.salvar("Rover: Havoc", imagem("JPEG", (3840, 2160)), CREDITO)

    with Image.open(fanarts.caminho("Rover: Havoc")) as salva:
        assert (salva.format, salva.size) == ("WEBP", (1920, 1080))
    assert fanarts.credito("Rover: Havoc") == CREDITO


def test_sem_arquivo_troca_so_o_credito(tmp_path: Path) -> None:
    fanarts = FanartsDoCatalogo(tmp_path)
    fanarts.salvar("Suoming", imagem("PNG"), CREDITO)
    antes = fanarts.caminho("Suoming").read_bytes()

    fanarts.salvar("Suoming", None, Credito(artista="outra pessoa"))

    assert fanarts.caminho("Suoming").read_bytes() == antes
    assert fanarts.credito("Suoming") == Credito(artista="outra pessoa", link=None)


def test_recusa_credito_sem_fanart(tmp_path: Path) -> None:
    fanarts = FanartsDoCatalogo(tmp_path)

    with pytest.raises(ImagemRecusada, match="envie a imagem"):
        fanarts.salvar("Suoming", None, CREDITO)
    assert fanarts.credito("Suoming") is None


def test_guarda_o_enquadramento_e_le_credito_antigo_sem_ele(tmp_path: Path) -> None:
    fanarts = FanartsDoCatalogo(tmp_path)
    ajustado = validar_credito("@fulano", None, {"x": 30, "y": 8.5, "zoom": 1.4})
    fanarts.salvar("Suoming", imagem("PNG"), ajustado)
    fanarts.salvar("Aemeath", imagem("PNG"), CREDITO)
    fanarts.caminho("Aemeath").with_suffix(".json").write_text('{"artista": "@antigo", "link": null}', encoding="utf-8")

    assert fanarts.credito("Suoming") == ajustado
    assert fanarts.credito("Aemeath") == Credito(artista="@antigo", enquadramento=Enquadramento(x=50, y=25, zoom=1))


@pytest.mark.parametrize(
    ("artista", "link", "esperado"),
    [
        ("  @fulano  ", "  ", Credito(artista="@fulano", link=None)),
        ("fulano", "http://x.com/fulano/status/1", Credito(artista="fulano", link="http://x.com/fulano/status/1")),
    ],
)
def test_normaliza_credito(artista: str, link: str, esperado: Credito) -> None:
    assert validar_credito(artista, link) == esperado


@pytest.mark.parametrize(
    ("artista", "link", "enquadramento", "trecho"),
    [
        ("   ", None, None, "artista"),
        ("a" * 81, None, None, "artista"),
        ("fulano", "javascript:alert(1)", None, "http"),
        ("fulano", "pixiv.net/artworks/1", None, "http"),
        ("fulano", None, {"x": 101}, "enquadramento.x"),
        ("fulano", None, {"y": -1}, "enquadramento.y"),
        ("fulano", None, {"zoom": 0.5}, "enquadramento.zoom"),
        ("fulano", None, {"zoom": 3.5}, "enquadramento.zoom"),
    ],
)
def test_recusa_credito_invalido(artista: str, link: str | None, enquadramento: dict[str, float] | None, trecho: str) -> None:
    with pytest.raises(CreditoRecusado, match=trecho):
        validar_credito(artista, link, enquadramento)
