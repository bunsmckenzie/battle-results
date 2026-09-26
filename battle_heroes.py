"""Combine validated hero identity matching with adjacent join-value recognition."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from hero_matcher import match_battle_heroes
from hero_values import extract_battle_join_values


@dataclass(frozen=True)
class BattleHeroReading:
    name: str | None
    join_value: int
    match_confidence: float
    value_confidence: float

    @property
    def accepted(self) -> bool:
        return self.name is not None


def analyze_battle_heroes(image_path: Path | str) -> dict[str, BattleHeroReading]:
    matches = match_battle_heroes(image_path)
    values = extract_battle_join_values(image_path)
    if matches.keys() != values.keys():
        raise ValueError("Hero matcher and join-value reader returned different slots")
    return {
        slot: BattleHeroReading(
            name=match.name,
            join_value=values[slot].value,
            match_confidence=match.confidence,
            value_confidence=values[slot].confidence,
        )
        for slot, match in matches.items()
    }
