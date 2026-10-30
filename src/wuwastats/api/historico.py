"""Rotas das análises salvas. Erros viram HTTP pelos handlers de app.py."""

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from wuwastats.domain.analyze import analisar
from wuwastats.domain.models import EntradaBuild
from wuwastats.domain.tables import GameData, Perfil
from wuwastats.gamedata.historico import MAX_NOME, AnaliseSalva, HistoricoAnalises, ResumoAnaliseSalva, novo_id
from wuwastats.vision.parse import LeituraPersonagem


class PedidoSalvar(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    nome: str = Field(default="", max_length=MAX_NOME, description="Vazio = build + data e hora")
    entrada: EntradaBuild
    leitura: LeituraPersonagem | None = None


def rotas_historico(
    historico: HistoricoAnalises, perfil_da_build: Callable[[str], Perfil], dados_atuais: Callable[[], GameData]
) -> APIRouter:
    rotas = APIRouter(prefix="/api/historico", tags=["histórico"])

    @rotas.post("", status_code=201)
    def salvar(pedido: PedidoSalvar) -> ResumoAnaliseSalva:
        analise = analisar(pedido.entrada, perfil_da_build(pedido.entrada.build), dados_atuais())
        agora = datetime.now().astimezone()
        salva = AnaliseSalva(
            id=novo_id(agora),
            nome=pedido.nome.strip() or f"{pedido.entrada.build} · {agora:%d/%m %H:%M}",
            build=pedido.entrada.build,
            criado_em=agora,
            score_medio_pct=analise.conjunto.score_medio_pct,
            nota_media=analise.conjunto.nota_media,
            entrada=pedido.entrada,
            leitura=pedido.leitura,
        )
        historico.salvar(salva)
        return ResumoAnaliseSalva.model_validate(salva.model_dump(exclude={"entrada", "leitura"}))

    @rotas.get("")
    def listar(build: str | None = None) -> list[ResumoAnaliseSalva]:
        return historico.listar(build)

    @rotas.get("/{analise_id}")
    def ler(analise_id: str) -> AnaliseSalva:
        return historico.ler(analise_id)

    @rotas.delete("/{analise_id}", status_code=204)
    def apagar(analise_id: str) -> None:
        historico.apagar(analise_id)

    return rotas
