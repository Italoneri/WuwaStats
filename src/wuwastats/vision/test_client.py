import json

import httpx2
import pytest
from openai import OpenAI

from wuwastats.config import Settings
from wuwastats.vision.client import ConfiguracaoAusente, ModeloNvidia, criar_modelo_nvidia
from wuwastats.vision.image import Imagem


def _resposta_chat(conteudo: str) -> dict[str, object]:
    return {
        "id": "chatcmpl-teste",
        "object": "chat.completion",
        "created": 0,
        "model": "modelo-teste",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": conteudo}}],
    }


def test_envia_prompt_e_imagem_com_temperatura_zero() -> None:
    requisicoes: list[httpx2.Request] = []

    def responder(requisicao: httpx2.Request) -> httpx2.Response:
        requisicoes.append(requisicao)
        return httpx2.Response(200, json=_resposta_chat('{"ok": true}'))

    cliente = OpenAI(
        api_key="chave-falsa",
        base_url="https://integrate.api.nvidia.com/v1",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(responder)),
    )
    modelo = ModeloNvidia(nome="modelo-teste", cliente=cliente, max_tokens=512)

    texto = modelo.completar("leia o echo", Imagem(conteudo=b"png", mime="image/png"))

    assert texto == '{"ok": true}'
    [requisicao] = requisicoes
    assert str(requisicao.url) == "https://integrate.api.nvidia.com/v1/chat/completions"
    corpo = json.loads(requisicao.content)
    assert (corpo["model"], corpo["temperature"], corpo["max_tokens"]) == ("modelo-teste", 0, 512)
    texto_prompt, imagem = corpo["messages"][0]["content"]
    assert texto_prompt == {"type": "text", "text": "leia o echo"}
    assert imagem["image_url"]["url"] == "data:image/png;base64,cG5n"


@pytest.mark.parametrize(
    "ambiente",
    [{"nvidia_vision_model": "m"}, {"nvidia_api_key": "k"}, {"nvidia_api_key": "", "nvidia_vision_model": "m"}],
)
def test_exige_chave_e_modelo_configurados(ambiente: dict[str, str]) -> None:
    settings = Settings.model_validate({"nvidia_api_key": None, "nvidia_vision_model": None, **ambiente})

    with pytest.raises(ConfiguracaoAusente, match="NVIDIA_API_KEY e NVIDIA_VISION_MODEL"):
        criar_modelo_nvidia(settings)
