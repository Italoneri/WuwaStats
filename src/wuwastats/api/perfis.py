"""Rotas do editor de builds (characters.json). Erros viram HTTP pelos handlers de app.py."""

from fastapi import APIRouter

from wuwastats.api.repositorio import RepositorioDados
from wuwastats.gamedata.schemas import PerfilRaw


def rotas_perfis(repositorio: RepositorioDados) -> APIRouter:
    rotas = APIRouter(prefix="/api/perfis", tags=["editor de builds"])

    @rotas.get("", response_model_exclude_none=True)
    def listar() -> dict[str, PerfilRaw]:
        """Perfis como estão no arquivo, com nomes trocados pelas chaves internas (crit_rate, Moonlit Clouds...).
        Campos ausentes (null) não aparecem: numa variante, campo presente = substitui o da base."""
        return repositorio.perfis_editaveis()

    @rotas.put("/{chave}", response_model_exclude_none=True)
    def salvar(chave: str, perfil: PerfilRaw) -> PerfilRaw:
        """Cria ou substitui. Valida characters.json inteiro com o loader; se passar, faz backup, grava e recarrega."""
        repositorio.salvar_perfil(chave, perfil)
        return repositorio.perfis_editaveis()[chave]

    @rotas.delete("/{chave}", status_code=204)
    def apagar(chave: str) -> None:
        repositorio.apagar_perfil(chave)

    return rotas
