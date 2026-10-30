from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

Recorte = tuple[float, float, float, float]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    data_dir: Path = PROJECT_ROOT / "data"
    cache_dir: Path = PROJECT_ROOT / "cache" / "vision"

    nvidia_api_key: SecretStr | None = None
    nvidia_vision_model: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_timeout_s: float = Field(default=60.0, gt=0)
    nvidia_max_retries: int = Field(default=2, ge=0)
    nvidia_max_tokens: int = Field(default=1024, gt=0)
    nvidia_concorrencia: int = Field(default=2, ge=1, le=5)

    # Título exato da janela do jogo, para a captura por atalho (F8/F9).
    captura_titulo_janela: str = "Wuthering Waves"

    # Recorte do painel do echo em frações da imagem: [x0, y0, x1, y1]. Vazio = imagem inteira.
    echo_recorte: Recorte | None = None

    @field_validator("echo_recorte")
    @classmethod
    def _recorte_dentro_da_imagem(cls, recorte: Recorte | None) -> Recorte | None:
        if recorte is None:
            return None
        x0, y0, x1, y1 = recorte
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError("ECHO_RECORTE deve ser [x0, y0, x1, y1] com 0 <= x0 < x1 <= 1 e 0 <= y0 < y1 <= 1")
        return recorte
