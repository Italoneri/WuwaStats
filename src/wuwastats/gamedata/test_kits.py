import json
from pathlib import Path

from PIL import Image

from wuwastats.gamedata.kit_texto import Trecho
from wuwastats.gamedata.kits import ARQUIVO_KITS, ARQUIVO_RESUMOS, Habilidade, ImagensDoKit, Kit, ler_kit
from wuwastats.gamedata.test_imagens import imagem

KIT = Kit(
    id_jogo=1402,
    tags=[],
    habilidades=[
        Habilidade(
            tipo="ATQ Normal",
            nome="Plumilâmina",
            imagem="habilidade-1",
            ilustracoes=[],
            descricao=[[Trecho(texto="Ataca.", estilo="normal")]],
            multiplicadores=[],
        )
    ],
    inerentes=[],
    bonus=[],
    sequencias=[],
)


def _gravar(pasta: Path, nome: str, conteudo: dict[str, object]) -> None:
    (pasta / nome).write_text(json.dumps(conteudo, ensure_ascii=False), encoding="utf-8")


def _gravar_kit(pasta: Path) -> None:
    _gravar(pasta, ARQUIVO_KITS, {"_meta": {"descricao": "teste"}, "kits": {"Yangyang": KIT.model_dump()}})


def test_le_kit_com_resumo(tmp_path: Path) -> None:
    _gravar_kit(tmp_path)
    _gravar(tmp_path, ARQUIVO_RESUMOS, {"_meta": {"descricao": "teste"}, "resumos": {"Yangyang": "Resumo."}})

    assert ler_kit(tmp_path, "Yangyang") == (KIT, "Resumo.")


def test_sem_kit_devolve_none(tmp_path: Path) -> None:
    assert ler_kit(tmp_path, "Yangyang") is None


def test_kit_sem_resumo(tmp_path: Path) -> None:
    _gravar_kit(tmp_path)

    assert ler_kit(tmp_path, "Yangyang") == (KIT, None)


def test_caminho_da_imagem_aceita_chave_com_dois_pontos(tmp_path: Path) -> None:
    assert ImagensDoKit(tmp_path).caminho("Yangyang: Xuanling", "S1").parts[-2:] == ("Yangyang_Xuanling", "S1.png")


def test_salva_imagem_como_png(tmp_path: Path) -> None:
    imagens = ImagensDoKit(tmp_path)

    imagens.salvar("Yangyang", "forte", imagem("WEBP"))

    assert imagens.existe("Yangyang", "forte")
    with Image.open(imagens.caminho("Yangyang", "forte")) as salva:
        assert salva.format == "PNG"
