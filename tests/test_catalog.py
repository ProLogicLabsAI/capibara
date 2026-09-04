from pathlib import Path

import pytest

from capibara.catalog import (
    CatalogNotFoundError,
    InvalidCatalogError,
    domain_for,
    get_card,
    get_card_with_source,
    load_catalog,
    load_catalog_with_sources,
    resolve_catalog_path,
)

REPO_ROOT = Path(__file__).parent.parent
CATALOGS_DIR = REPO_ROOT / "catalogs"
FIXTURES_DIR = Path(__file__).parent / "fixtures"

EXPECTED_CARD_COUNT = 15


def test_default_catalog_loads_fifteen_cards():
    cards = load_catalog(CATALOGS_DIR)
    assert len(cards) == EXPECTED_CARD_COUNT
    assert "classify-risk" in {c["id"] for c in cards}
    assert "review-pull-request" in {c["id"] for c in cards}


def test_get_card_hit_and_miss():
    cards = load_catalog(CATALOGS_DIR)
    assert get_card(cards, "classify-risk")["intent"].startswith("Classify")
    assert get_card(cards, "does-not-exist") is None


def test_get_card_with_source_hit_and_miss():
    pairs = load_catalog_with_sources(CATALOGS_DIR)
    hit = get_card_with_source(pairs, "classify-risk")
    assert hit is not None
    source, card = hit
    assert card["id"] == "classify-risk"
    assert source.name == "classify-risk.yaml"
    assert get_card_with_source(pairs, "does-not-exist") is None


def test_strict_load_raises_on_invalid_card():
    with pytest.raises(InvalidCatalogError):
        load_catalog(FIXTURES_DIR / "invalid-embedded-threshold.yaml")


def test_non_strict_load_skips_invalid_card():
    cards = load_catalog(FIXTURES_DIR / "invalid-embedded-threshold.yaml", strict=False)
    assert cards == []


def test_domain_for_card_in_domain_subfolder():
    source = CATALOGS_DIR / "software-engineering" / "review-pull-request.yaml"
    assert domain_for(source, CATALOGS_DIR) == "software-engineering"


def test_domain_for_card_directly_in_catalogs_root_is_none(tmp_path):
    flat_root = tmp_path / "catalogs"
    flat_root.mkdir()
    card_path = flat_root / "do-a-thing.yaml"
    card_path.write_text("id: do-a-thing\n")
    assert domain_for(card_path, flat_root) is None


def test_domain_for_card_outside_catalogs_root_is_none(tmp_path):
    outside = tmp_path / "elsewhere" / "do-a-thing.yaml"
    outside.parent.mkdir(parents=True)
    outside.write_text("id: do-a-thing\n")
    assert domain_for(outside, CATALOGS_DIR) is None


def test_resolve_catalog_path_explicit_wins_over_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CAPIBARA_CATALOG", "/should/not/be/used")
    assert resolve_catalog_path(tmp_path) == tmp_path


def test_resolve_catalog_path_env_var(monkeypatch):
    monkeypatch.delenv("CAPIBARA_CATALOG", raising=False)
    monkeypatch.setenv("CAPIBARA_CATALOG", str(CATALOGS_DIR))
    assert resolve_catalog_path() == CATALOGS_DIR


def test_resolve_catalog_path_dev_checkout_walk(monkeypatch):
    monkeypatch.delenv("CAPIBARA_CATALOG", raising=False)
    monkeypatch.chdir(REPO_ROOT / "catalogs" / "software-engineering")
    assert resolve_catalog_path() == REPO_ROOT / "catalogs"


def test_resolve_catalog_path_raises_clear_error_when_nothing_found(monkeypatch, tmp_path):
    monkeypatch.delenv("CAPIBARA_CATALOG", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("capibara.catalog.packaged_root", lambda: None)
    with pytest.raises(CatalogNotFoundError) as exc_info:
        resolve_catalog_path()
    message = str(exc_info.value)
    assert "--catalog" in message
    assert "CAPIBARA_CATALOG" in message
