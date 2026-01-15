# rule_ir.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, Literal

@dataclass(frozen=True)
class Condition:
    actor: str
    predicate: str
    value: bool

@dataclass(frozen=True)
class Action:
    actor: str
    name: str

@dataclass(frozen=True)
class RelationAtom:
    """
    Object property atom:
      predicate(subject, object)
    Example:
      providesAISystem(AIprovider, AIsystem)
    """
    predicate: str
    subject: str
    object: str

@dataclass(frozen=True)
class RuleIR:
    rid: str
    conditions: Tuple[Condition, ...]
    actions: Tuple[Action, ...]
    relations: Tuple[RelationAtom, ...] = ()
