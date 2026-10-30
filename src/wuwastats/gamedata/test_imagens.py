from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from wuwastats.gamedata.imagens import ImagemRecusada, ImagensDoCatalogo, nome_de_arquivo


def imagem(formato: str, tamanho: tuple[int, int] = (40, 30)) -> bytes:
    saida = BytesIO()
    Image.new("RGB", tamanho, "purple").save(saida, format=formato)
    return saida.getvalue()


@pytest.mark.parametrize("formato", ["PNG", "JPEG", "WEBP"])
def test_aceita_png_jpeg_e_webp_e_grava_sempre_png(tmp_path: Path, formato: str) -> None:
    imagens = ImagensDoCatalogo(tmp_path)

    imagens.salvar("echoes", "Reminiscence: Suhsin the Inevitable", imagem(formato))

    with Image.open(imagens.caminho("echoes", "Reminiscence: Suhsin the Inevitable")) as salva:
        assert (salva.format, salva.size) == ("PNG", (40, 30))


def test_reduz_imagem_grande_para_o_lado_maximo(tmp_path: Path) -> None:
    imagens = ImagensDoCatalogo(tmp_path)

    imagens.salvar("personagens", "Suoming", imagem("PNG", (3000, 1500)))

    with Image.open(imagens.caminho("personagens", "Suoming")) as salva:
        assert salva.size == (1024, 512)


@pytest.mark.parametrize(
    ("conteudo", "trecho"),
    [
        (b"nao sou imagem", "não é uma imagem"),
        (imagem("GIF"), "formato GIF"),
        (b"x" * (5 * 1024 * 1024 + 1), "maior que 5 MB"),
    ],
)
def test_recusa_arquivo_invalido(tmp_path: Path, conteudo: bytes, trecho: str) -> None:
    with pytest.raises(ImagemRecusada, match=trecho):
        ImagensDoCatalogo(tmp_path).salvar("armas", "Unspoken Rue", conteudo)


@pytest.mark.parametrize(
    ("chave", "nome"),
    [
        ("Reminiscence: Suhsin the Inevitable", "Reminiscence_Suhsin_the_Inevitable"),
        ("Rover: Havoc", "Rover_Havoc"),
        ("../..", "_"),
    ],
)
def test_nome_de_arquivo_seguro_no_windows(chave: str, nome: str) -> None:
    assert nome_de_arquivo(chave) == nome
