"""Resolve nomes lidos (do jogo, da IA ou digitados) para chaves internas."""

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

CRIT_RATE = "crit_rate"
CRIT_DMG = "crit_dmg"
ENERGY_REGEN = "energy_regen"


def fold(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[\s.]+", " ", without_accents).strip().casefold()


def is_percent_stat(key: str) -> bool:
    return not key.endswith("_flat")


def is_pct_flat_pair(keys: frozenset[str]) -> bool:
    """Um mesmo nome (ex.: 'ATQ') pode servir a atk_pct e atk_flat: o sinal de % desempata."""
    return len(keys) == 2 and len({is_percent_stat(key) for key in keys}) == 2


@dataclass(frozen=True)
class NameIndex:
    keys_by_name: Mapping[str, frozenset[str]]
    aliases_by_key: Mapping[str, tuple[str, ...]]

    @classmethod
    def build(cls, aliases_by_key: Mapping[str, Iterable[str]]) -> "NameIndex":
        originals = {key: tuple(aliases) for key, aliases in aliases_by_key.items()}
        keys_by_name: dict[str, set[str]] = {}
        for key, aliases in originals.items():
            for name in (key, *aliases):
                keys_by_name.setdefault(fold(name), set()).add(key)
        return cls({name: frozenset(keys) for name, keys in keys_by_name.items()}, originals)

    @property
    def keys(self) -> frozenset[str]:
        return frozenset(self.aliases_by_key)

    def candidates(self, name: str) -> frozenset[str]:
        return self.keys_by_name.get(fold(name), frozenset())

    def ambiguous_names(self) -> dict[str, frozenset[str]]:
        return {name: keys for name, keys in self.keys_by_name.items() if len(keys) > 1}

    def resolve(self, name: str) -> str | None:
        return _single(self.candidates(name))


def resolve_stat(index: NameIndex, name: str, percentual: bool | None = None) -> str | None:
    candidates = index.candidates(name)
    stripped = name.rstrip()
    if not candidates and stripped.endswith("%"):
        return resolve_stat(index, stripped[:-1], percentual=True)
    if len(candidates) > 1 and percentual is not None:
        candidates = frozenset(key for key in candidates if is_percent_stat(key) == percentual)
    return _single(candidates)


def _single(candidates: frozenset[str]) -> str | None:
    return next(iter(candidates)) if len(candidates) == 1 else None
