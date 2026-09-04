"""Capability catalog loading and resolution for the CAPIBARA CLI.

A "catalog" is whatever `capibara.validate.load_cards` can load: a single
card file, a catalog file (YAML list of cards), or a directory of such
files. The default catalog is resolved in one order, shared by every CLI
command:

1. `--catalog PATH` (explicit)
2. `$CAPIBARA_CATALOG` environment variable
3. a dev checkout found by walking the current directory and its parents
   for a directory containing both `catalogs/` and `schema/capability.v0.yaml`
4. the installed package's bundled `catalogs/` (force-included at build time)
"""

from __future__ import annotations

import os
from pathlib import Path

from capibara.validate import (
    find_repo_root,
    load_cards,
    load_schema,
    packaged_root,
    resolve_schema_path,
    validate_card,
    validate_card_gates,
)


class CatalogNotFoundError(FileNotFoundError):
    """Raised when no catalog path can be resolved."""


class InvalidCatalogError(ValueError):
    """Raised when strict loading encounters one or more invalid cards."""


def resolve_catalog_path(explicit: Path | None = None) -> Path:
    """Resolve the catalog file or directory to load cards from."""
    if explicit is not None:
        return explicit

    env = os.environ.get("CAPIBARA_CATALOG")
    if env:
        return Path(env)

    root = find_repo_root(Path.cwd())
    if root is not None:
        return root / "catalogs"

    root = packaged_root()
    if root is not None:
        return root / "catalogs"

    raise CatalogNotFoundError(
        "No catalog found. Tried: --catalog, $CAPIBARA_CATALOG, a dev checkout "
        "(a directory with catalogs/ and schema/capability.v0.yaml above the current "
        "directory), and the installed package's bundled catalogs."
    )


def domain_for(source: Path, catalogs_root: Path) -> str | None:
    """Return the domain (first path segment under catalogs_root), or None
    when the card lives directly in catalogs_root with no domain subfolder."""
    try:
        rel = source.resolve().relative_to(catalogs_root.resolve())
    except ValueError:
        return None
    return rel.parts[0] if len(rel.parts) >= 2 else None


def load_catalog_with_sources(
    path: str | Path | None = None, *, strict: bool = True
) -> list[tuple[Path, dict]]:
    """Load and validate every card at path (or the resolved catalog),
    keeping each card's source path for domain derivation.

    With strict=True (default), raises InvalidCatalogError if any card fails
    schema or gate validation, so callers never see a malformed catalog.
    With strict=False, invalid cards are silently skipped.
    """
    resolved = Path(path) if path is not None else resolve_catalog_path()
    # Anchor schema resolution to the catalog actually in use, not to the
    # process's CWD: an explicit --catalog / $CAPIBARA_CATALOG may point
    # somewhere far from the current directory.
    schema = load_schema(resolve_schema_path(resolved))

    pairs: list[tuple[Path, dict]] = []
    invalid: list[str] = []
    for source, card, is_single in load_cards(resolved):
        if not isinstance(card, dict):
            invalid.append(f"{source}: expected a mapping, got {type(card).__name__}")
            continue
        errors = validate_card(card, schema)
        gate_errors, _warnings = validate_card_gates(card, source, is_single)
        errors = errors + gate_errors
        if errors:
            invalid.append(f"{source} ({card.get('id', '?')}): {'; '.join(errors)}")
            continue
        pairs.append((source, card))

    if strict and invalid:
        raise InvalidCatalogError("Invalid card(s) in catalog:\n" + "\n".join(invalid))

    return pairs


def load_catalog(path: str | Path | None = None, *, strict: bool = True) -> list[dict]:
    """Load and validate every card at path (or the resolved catalog); cards only."""
    return [card for _source, card in load_catalog_with_sources(path, strict=strict)]


def get_card(cards: list[dict], card_id: str) -> dict | None:
    """Return the card with the given id, or None if not found."""
    for card in cards:
        if card.get("id") == card_id:
            return card
    return None


def get_card_with_source(pairs: list[tuple[Path, dict]], card_id: str) -> tuple[Path, dict] | None:
    """Return the (source, card) pair with the given id, or None if not found."""
    for source, card in pairs:
        if card.get("id") == card_id:
            return source, card
    return None
