"""Prompts da extração. Mudou o texto de forma que muda as respostas? Suba a versão do tipo (invalida o cache dele)."""

from typing import Literal

from wuwastats.domain.names import NameIndex
from wuwastats.domain.tables import GameData

TipoPrint = Literal["echo", "personagem"]
PROMPT_VERSAO: dict[TipoPrint, int] = {"echo": 1, "personagem": 2}


def prompt_echo(dados: GameData) -> str:
    return f"""Você recebe o print da tela de um echo de Wuthering Waves (jogo em português do Brasil).
Responda SOMENTE com um objeto JSON, sem markdown e sem texto antes ou depois, neste formato:
{{"nome": string|null, "custo": 1|3|4, "set": string|null,
 "principal": {{"stat": string, "valor": number, "percentual": boolean}},
 "substatus": [{{"stat": string, "valor": number, "percentual": boolean}}]}}

Regras:
- "valor" é número com ponto decimal e sem o sinal de % (ex.: "17,4%" vira 17.4 com "percentual": true).
- "percentual" é true quando o valor aparece com %, false quando é valor fixo.
- "principal" é o status principal do echo. Ignore o status fixo secundário (ATQ ou HP fixo que todo echo tem).
- "substatus": os substatus desbloqueados, na ordem da tela, no máximo 5. Não invente substatus que não aparecem.
- "stat": use exatamente um dos nomes abaixo. Nomes na mesma linha são o mesmo status;
  para ATQ, HP e DEF o campo "percentual" diferencia o valor em % do fixo.
{_linhas(dados.stat_names)}
- "set": nome da sonata exatamente como aparece no jogo. Conhecidos: {_lista(dados.set_names)}.
  Se for outro, transcreva o nome exato.
- "nome": nome do echo exatamente como aparece no jogo. Conhecidos: {_lista(dados.echo_names)}.
  Se for outro, transcreva o nome exato.
- Se não conseguir ler um campo, use null."""


PROMPT_PERSONAGEM = """Você recebe o print da tela de atributos de um personagem de Wuthering Waves (jogo em português do Brasil).
Responda SOMENTE com um objeto JSON, sem markdown e sem texto antes ou depois, neste formato:
{"personagem": string|null, "nivel": integer|null,
 "arma": string|null, "arma_nivel": integer|null, "arma_rank": integer|null,
 "regen_energia_total": number|null,
 "atributos": [{"stat": string, "valor": number, "percentual": boolean}]}

Regras:
- "personagem": nome do personagem exatamente como aparece. "nivel": nível atual do personagem (ex.: "Nv. 90/90" vira 90).
- "arma": nome da arma equipada exatamente como aparece. "arma_nivel": nível atual da arma.
  "arma_rank": rank (sintonização) da arma, de 1 a 5.
- "regen_energia_total": valor total de Regen. de Energia mostrado nos atributos, com ponto decimal
  e sem o sinal de % (ex.: "125,4%" vira 125.4).
- "atributos": todos os atributos totais visíveis (HP, ATQ, DEF, Taxa CRIT, Dano CRIT, Regen. de Energia,
  bônus de dano e de cura), na ordem da tela. "stat" é o nome exatamente como aparece; "valor" com ponto decimal
  e sem o sinal de %; "percentual" true quando o valor aparece com %. Inclua os bônus que aparecem com 0%.
- Se um campo não estiver visível ou não puder ser lido, use null (ou [] em "atributos")."""


def _linhas(indice: NameIndex) -> str:
    grupos = sorted({" / ".join(nomes) for nomes in indice.aliases_by_key.values() if nomes})
    return "\n".join(f"  * {grupo}" for grupo in grupos)


def _lista(indice: NameIndex) -> str:
    nomes = sorted({nome for chave, aliases in indice.aliases_by_key.items() for nome in (chave, *aliases)})
    return ", ".join(nomes) or "(nenhum cadastrado)"
