"""Structural comparison between two CAPIBARA capability cards.

No lab equivalent — new for public V0. Scalar fields (intent, subject,
owner, risk.level) are compared directly. Collections (tags, semantic_refs,
behavior_profiles, inputs, outputs) are compared as shared / only-in-A /
only-in-B sets. `inputs` and `outputs` are matched by `name`, so a changed
`type` on a shared field name reads as a change within "shared" rather than
a spurious remove-plus-add across only-in-A and only-in-B.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_SCALAR_FIELDS = ("intent", "subject", "owner")
_SIMPLE_LIST_FIELDS = ("tags", "semantic_refs")
_NAMED_LIST_FIELDS = ("inputs", "outputs")


@dataclass
class FieldDiff:
    field: str
    a: Any
    b: Any


@dataclass
class ListDiff:
    field: str
    shared: list[Any] = field(default_factory=list)
    only_a: list[Any] = field(default_factory=list)
    only_b: list[Any] = field(default_factory=list)


@dataclass
class CardComparison:
    id_a: str
    id_b: str
    scalar_diffs: list[FieldDiff] = field(default_factory=list)
    list_diffs: list[ListDiff] = field(default_factory=list)

    @property
    def identical(self) -> bool:
        return not self.scalar_diffs and not any(
            d.only_a
            or d.only_b
            or any(item.get("changed") for item in d.shared if isinstance(item, dict))
            for d in self.list_diffs
        )


def _risk_level(card: dict) -> Any:
    risk = card.get("risk")
    return risk.get("level") if isinstance(risk, dict) else None


def _compare_scalars(a: dict, b: dict) -> list[FieldDiff]:
    diffs = []
    for name in _SCALAR_FIELDS:
        va, vb = a.get(name), b.get(name)
        if va != vb:
            diffs.append(FieldDiff(field=name, a=va, b=vb))
    ra, rb = _risk_level(a), _risk_level(b)
    if ra != rb:
        diffs.append(FieldDiff(field="risk.level", a=ra, b=rb))
    return diffs


def _compare_simple_list(name: str, a: dict, b: dict) -> ListDiff:
    sa, sb = set(a.get(name) or []), set(b.get(name) or [])
    return ListDiff(
        field=name,
        shared=sorted(sa & sb),
        only_a=sorted(sa - sb),
        only_b=sorted(sb - sa),
    )


def _compare_behavior_profiles(a: dict, b: dict) -> ListDiff:
    la = {
        p["id"]: p for p in (a.get("behavior_profiles") or []) if isinstance(p, dict) and "id" in p
    }
    lb = {
        p["id"]: p for p in (b.get("behavior_profiles") or []) if isinstance(p, dict) and "id" in p
    }
    shared_keys = sorted(set(la) & set(lb))
    only_a_keys = sorted(set(la) - set(lb))
    only_b_keys = sorted(set(lb) - set(la))
    return ListDiff(
        field="behavior_profiles",
        shared=[
            {"id": key, "a": la[key], "b": lb[key], "changed": la[key] != lb[key]}
            for key in shared_keys
        ],
        only_a=[la[k] for k in only_a_keys],
        only_b=[lb[k] for k in only_b_keys],
    )


def _compare_named_list(name: str, a: dict, b: dict) -> ListDiff:
    """Compare inputs/outputs keyed by `name`: a changed `type` shows up as a
    changed entry in `shared`, never as a spurious remove-plus-add."""
    la = {
        item["name"]: item
        for item in (a.get(name) or [])
        if isinstance(item, dict) and "name" in item
    }
    lb = {
        item["name"]: item
        for item in (b.get(name) or [])
        if isinstance(item, dict) and "name" in item
    }
    shared_keys = sorted(set(la) & set(lb))
    only_a_keys = sorted(set(la) - set(lb))
    only_b_keys = sorted(set(lb) - set(la))
    return ListDiff(
        field=name,
        shared=[
            {"name": key, "a": la[key], "b": lb[key], "changed": la[key] != lb[key]}
            for key in shared_keys
        ],
        only_a=[la[k] for k in only_a_keys],
        only_b=[lb[k] for k in only_b_keys],
    )


def compare_cards(a: dict, b: dict) -> CardComparison:
    """Structurally compare two capability cards."""
    comparison = CardComparison(id_a=a.get("id", "?"), id_b=b.get("id", "?"))
    comparison.scalar_diffs = _compare_scalars(a, b)
    comparison.list_diffs = [
        *(_compare_simple_list(name, a, b) for name in _SIMPLE_LIST_FIELDS),
        _compare_behavior_profiles(a, b),
        *(_compare_named_list(name, a, b) for name in _NAMED_LIST_FIELDS),
    ]
    return comparison


def comparison_to_dict(comparison: CardComparison) -> dict:
    """JSON-serializable form of a CardComparison."""
    return {
        "a": comparison.id_a,
        "b": comparison.id_b,
        "identical": comparison.identical,
        "scalars": [{"field": d.field, "a": d.a, "b": d.b} for d in comparison.scalar_diffs],
        "lists": {
            ld.field: {"shared": ld.shared, "only_a": ld.only_a, "only_b": ld.only_b}
            for ld in comparison.list_diffs
        },
    }
