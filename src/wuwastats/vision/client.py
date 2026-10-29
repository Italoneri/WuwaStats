"""Cliente da API de visão da NVIDIA (compatível com OpenAI)."""

from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI

from wuwastats.config import Settings
from wuwastats.vision.image import Imagem


class ModeloVisao(Protocol):
    @property
    def nome(self) -> str: ...

    def completar(self, prompt: str, imagem: Imagem) -> str: ...


class ConfiguracaoAusente(Exception):
    pass


@dataclass(frozen=True)
class ModeloNvidia:
    nome: str
    cliente: OpenAI
    max_tokens: int

    def completar(self, prompt: str, imagem: Imagem) -> str:
        resposta = self.cliente.chat.completions.create(
            model=self.nome,
            temperature=0,
            max_tokens=self.max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": imagem.data_url}},
                    ],
                }
            ],
        )
        if not resposta.choices:
            return ""
        return resposta.choices[0].message.content or ""


def criar_modelo_nvidia(settings: Settings) -> ModeloNvidia:
    chave = settings.nvidia_api_key.get_secret_value() if settings.nvidia_api_key else ""
    if not chave or not settings.nvidia_vision_model:
        raise ConfiguracaoAusente("defina NVIDIA_API_KEY e NVIDIA_VISION_MODEL no .env (veja .env.example)")
    cliente = OpenAI(
        base_url=settings.nvidia_base_url,
        api_key=chave,
        timeout=settings.nvidia_timeout_s,
        max_retries=settings.nvidia_max_retries,
    )
    return ModeloNvidia(nome=settings.nvidia_vision_model, cliente=cliente, max_tokens=settings.nvidia_max_tokens)
