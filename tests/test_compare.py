from pathlib import Path

from capibara.catalog import get_card, load_catalog
from capibara.compare import compare_cards, comparison_to_dict

REPO_ROOT = Path(__file__).parent.parent
CATALOGS_DIR = REPO_ROOT / "catalogs"


def _card(card_id: str) -> dict:
    cards = load_catalog(CATALOGS_DIR)
    card = get_card(cards, card_id)
    assert card is not None
    return card


def test_compare_shared_owner_and_domain_differing_intent_and_inputs():
    a = _card("review-pull-request")
    b = _card("draft-pr-description")
    comparison = compare_cards(a, b)

    assert not comparison.identical
    # owner is shared (platform-engineering on both) so it must not appear as a scalar diff
    assert not any(d.field == "owner" for d in comparison.scalar_diffs)
    # intent differs
    intent_diff = next(d for d in comparison.scalar_diffs if d.field == "intent")
    assert intent_diff.a == a["intent"]
    assert intent_diff.b == b["intent"]

    inputs_diff = next(ld for ld in comparison.list_diffs if ld.field == "inputs")
    only_a_names = {item["name"] for item in inputs_diff.only_a}
    only_b_names = {item["name"] for item in inputs_diff.only_b}
    assert "repo_context" in only_a_names
    assert "template_ref" in only_b_names


def test_compare_shared_field_with_changed_description_is_not_remove_plus_add():
    """`linked_issue` is present in both cards (same name, same type) but with
    a different description — it must show up as a changed entry within
    `shared`, keyed by name, not split across only_a and only_b as if it
    were two unrelated fields."""
    a = _card("review-pull-request")
    b = _card("draft-pr-description")
    comparison = compare_cards(a, b)

    inputs_diff = next(ld for ld in comparison.list_diffs if ld.field == "inputs")
    only_a_names = {item["name"] for item in inputs_diff.only_a}
    only_b_names = {item["name"] for item in inputs_diff.only_b}
    assert "linked_issue" not in only_a_names
    assert "linked_issue" not in only_b_names

    shared_by_name = {item["name"]: item for item in inputs_diff.shared}
    assert "linked_issue" in shared_by_name
    assert shared_by_name["linked_issue"]["changed"] is True
    assert (
        shared_by_name["linked_issue"]["a"]["description"]
        != shared_by_name["linked_issue"]["b"]["description"]
    )
    # the field genuinely is unchanged in `type` — only description differs
    assert (
        shared_by_name["linked_issue"]["a"]["type"] == shared_by_name["linked_issue"]["b"]["type"]
    )


def test_compare_identical_card_with_itself():
    a = _card("classify-risk")
    comparison = compare_cards(a, dict(a))
    assert comparison.identical
    assert comparison.scalar_diffs == []
    for ld in comparison.list_diffs:
        assert ld.only_a == []
        assert ld.only_b == []


def test_comparison_to_dict_is_json_shaped():
    a = _card("review-pull-request")
    b = _card("draft-pr-description")
    payload = comparison_to_dict(compare_cards(a, b))
    assert payload["a"] == "review-pull-request"
    assert payload["b"] == "draft-pr-description"
    assert isinstance(payload["scalars"], list)
    assert "inputs" in payload["lists"]
    assert "outputs" in payload["lists"]
