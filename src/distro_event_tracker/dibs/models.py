"""Typed dibs domain models."""

from dataclasses import dataclass
from typing import TypeAlias

DibsQuantity: TypeAlias = int | str


@dataclass(frozen=True, slots=True)
class DibsClaim:
    user_id: int
    item_name: str
    quantity: DibsQuantity
