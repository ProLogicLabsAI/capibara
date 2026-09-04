"""Validation of CAPIBARA capability cards against schema/capability.v0.yaml.

A "catalog" file may contain either a single capability card (a YAML mapping)
or a list of cards (a YAML sequence). A directory is validated by loading
every ``*.yaml`` / ``*.yml`` file found anywhere beneath it (recursive), so
the public repo's domain-partitioned ``catalogs/<domain>/*.yaml`` layout is
discovered from the ``catalogs/`` root — a plain, non-recursive glob would
find nothing there. ``schema/capability.v0.yaml`` itself is always skipped,
so validating a directory that contains both ``catalogs/`` and ``schema/``
never tries to validate the grammar file as a card.

Beyond JSON Schema, this module also enforces the CONTRIBUTING.md gate
invariants that the schema's ``type`` pattern cannot express on its own:
a card's ``id`` must match its filename (single-card files only), ids must
be unique across a catalog, ``string``/``object`` are not semantic type
tokens, and no field may name a model or vendor. A type token outside the
documented vocabulary is a warning, not an error, so a new domain token is
never blocked outright.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft7Validator

# Documented semantic type token vocabulary (CONTRIBUTING.md "Semantic type
# tokens" table). Shared with capibara.projections so export never disagrees
# with validation about which tokens are "known".
TOKEN_VOCABULARY = frozenset(
    {
        "text",
        "text/diff",
        "text/code",
        "text/markdown",
        "text/yaml",
        "text/pdf",
        "json-object",
        "identifier",
        "enum-label",
        "boolean",
        "flag",
        "image",
        "url",
    }
)

# Substrings that flag a field as naming a model or vendor rather than
# describing a capability (CONTRIBUTING.md gate invariants). Deliberately
# coarse and case-insensitive; false positives are rare in capability prose.
_MODEL_NAME_MARKERS = (
    "gpt-",
    "chatgpt",
    "claude",
    "gemini",
    "llama",
    "mistral",
    "openai",
    "anthropic",
)


class SchemaNotFoundError(FileNotFoundError):
    """Raised when capability.v0.yaml cannot be located."""


@dataclass
class ValidationResult:
    """Outcome of validating a single capability card."""

    source: Path
    card_id: str | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def find_repo_root(start: Path) -> Path | None:
    """Walk `start` and its parents for a directory with both catalogs/ and
    schema/capability.v0.yaml (a dev checkout of this repo)."""
    start = start.resolve()
    for candidate in (start, *start.parents):
        if (candidate / "catalogs").is_dir() and (
            candidate / "schema" / "capability.v0.yaml"
        ).is_file():
            return candidate
    return None


def packaged_root() -> Path | None:
    """Return the installed package's directory if it bundles catalogs/ and
    schema/ alongside the module (force-included at build time)."""
    pkg_dir = Path(__file__).resolve().parent
    if (pkg_dir / "catalogs").is_dir() and (pkg_dir / "schema" / "capability.v0.yaml").is_file():
        return pkg_dir
    return None


def resolve_schema_path(near: Path | None = None) -> Path:
    """Resolve capability.v0.yaml: try a repo root found near `near` first
    (e.g. an explicit --catalog target that lives far from CWD), then a repo
    root found from the current directory, then the installed package's
    bundled schema."""
    starts = []
    if near is not None:
        starts.append(near.parent if near.is_file() else near)
    starts.append(Path.cwd())

    for start in starts:
        root = find_repo_root(start)
        if root is not None:
            return root / "schema" / "capability.v0.yaml"

    root = packaged_root()
    if root is not None:
        return root / "schema" / "capability.v0.yaml"

    raise SchemaNotFoundError(
        f"capability.v0.yaml not found near {near or Path.cwd()} or in the installed package."
    )


def load_schema(schema_path: Path | None = None) -> dict:
    """Load and parse capability.v0.yaml."""
    path = schema_path if schema_path is not None else resolve_schema_path()
    if not path.is_file():
        raise SchemaNotFoundError(f"capability.v0.yaml not found at {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# Directory segments a recursive directory scan never descends *into* below
# the given root: common build/venv/vcs artifacts so `capibara validate .`
# from a dev checkout does not pick up an editable install's copy of
# catalogs/ under .venv/, or a packaging output dir. Checked relative to the
# scanned root, not as an absolute-path substring — otherwise this would
# also skip a *resolved* packaged root that legitimately lives under a
# site-packages/ directory (a real `pip install capibara` layout).
_SKIP_PATH_SEGMENTS = {"schema", "site-packages", "dist", "build", "node_modules", "__pycache__"}


def _should_skip(yaml_file: Path, root: Path) -> bool:
    if yaml_file.name == "capability.v0.yaml":
        return True
    try:
        rel_parts = yaml_file.resolve().relative_to(root).parts
    except ValueError:
        rel_parts = yaml_file.parts
    return any(part.startswith(".") or part in _SKIP_PATH_SEGMENTS for part in rel_parts)


def load_cards(path: str | Path) -> list[tuple[Path, Any, bool]]:
    """Load capability cards from a file or directory.

    Returns a list of (source_path, card, is_single_card_file) triples.
    `is_single_card_file` is True when the source YAML file's top-level value
    was a mapping (one card per file, the public repo's layout) and False
    when it came from a list element in a multi-card catalog file. Directory
    loading is recursive; it always skips schema/capability.v0.yaml plus
    hidden and build/venv/vcs directories found *beneath* the given root
    (see _SKIP_PATH_SEGMENTS) — never the root itself.
    """
    p = Path(path)
    if p.is_dir():
        resolved_root = p.resolve()
        triples: list[tuple[Path, Any, bool]] = []
        yaml_files = sorted(set(p.rglob("*.yaml")) | set(p.rglob("*.yml")))
        for yaml_file in yaml_files:
            if _should_skip(yaml_file, resolved_root):
                continue
            triples.extend(load_cards(yaml_file))
        return triples

    if not p.is_file():
        raise FileNotFoundError(f"No such file or directory: {p}")

    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if isinstance(data, list):
        return [(p, card, False) for card in data]
    if isinstance(data, dict):
        return [(p, data, True)]
    raise ValueError(
        f"{p}: expected a capability card (mapping) or a catalog (list), got {type(data).__name__}"
    )


def validate_card(card: dict, schema: dict) -> list[str]:
    """Validate a single card against the schema, returning readable error strings."""
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(card), key=lambda e: list(e.path))
    messages = []
    for err in errors:
        field_path = ".".join(str(part) for part in err.path) or "<root>"
        messages.append(f"{field_path}: {err.message}")
    return messages


def _fields(card: dict, section: str) -> list[dict]:
    value = card.get(section)
    return [f for f in value if isinstance(f, dict)] if isinstance(value, list) else []


def _id_filename_error(card: dict, source: Path, is_single_card_file: bool) -> list[str]:
    if not is_single_card_file:
        return []
    card_id = card.get("id")
    if isinstance(card_id, str) and card_id != source.stem:
        return [f"id: '{card_id}' does not match filename stem '{source.stem}' ({source.name})"]
    return []


def _bare_type_errors(card: dict) -> list[str]:
    errors = []
    for section in ("inputs", "outputs"):
        for f in _fields(card, section):
            if f.get("type") in ("string", "object"):
                errors.append(
                    f"{section}.{f.get('name', '?')}.type: bare '{f['type']}' is not a "
                    "semantic type token — use a CAPIBARA vocabulary token (CONTRIBUTING.md)"
                )
    return errors


def _unknown_token_warnings(card: dict) -> list[str]:
    warnings = []
    for section in ("inputs", "outputs"):
        for f in _fields(card, section):
            token = f.get("type")
            if token and token not in ("string", "object") and token not in TOKEN_VOCABULARY:
                warnings.append(
                    f"{section}.{f.get('name', '?')}.type: '{token}' is not in the documented "
                    "token vocabulary (CONTRIBUTING.md) — fine if this is a deliberate new "
                    "domain token"
                )
    return warnings


def _model_name_errors(card: dict) -> list[str]:
    errors: list[str] = []

    def _walk(value: Any, path: str) -> None:
        if isinstance(value, str):
            lowered = value.lower()
            for marker in _MODEL_NAME_MARKERS:
                if marker in lowered:
                    errors.append(
                        f"{path or '<root>'}: contains model-name marker '{marker}' — capability "
                        "cards must not name a model or vendor (CONTRIBUTING.md)"
                    )
                    break
        elif isinstance(value, dict):
            for k, v in value.items():
                _walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(value, list):
            for i, v in enumerate(value):
                _walk(v, f"{path}[{i}]")

    _walk(card, "")
    return errors


def validate_card_gates(
    card: dict, source: Path, is_single_card_file: bool
) -> tuple[list[str], list[str]]:
    """CONTRIBUTING.md gate checks beyond JSON Schema. Returns (errors, warnings)."""
    errors = [
        *_id_filename_error(card, source, is_single_card_file),
        *_bare_type_errors(card),
        *_model_name_errors(card),
    ]
    warnings = _unknown_token_warnings(card)
    return errors, warnings


def validate_path(path: str | Path, schema: dict | None = None) -> list[ValidationResult]:
    """Validate every card found at path (file, catalog, or directory).

    Schema errors and gate errors are combined per card. Duplicate ids are
    flagged catalog-wide: the first occurrence of an id stays clean, later
    occurrences report the duplicate and name the earlier source.
    """
    if schema is None:
        schema = load_schema()
    results: list[ValidationResult] = []
    seen_ids: dict[str, Path] = {}
    for source, card, is_single in load_cards(path):
        if not isinstance(card, dict):
            results.append(
                ValidationResult(
                    source=source,
                    card_id=None,
                    errors=[f"<root>: expected a mapping, got {type(card).__name__}"],
                )
            )
            continue

        errors = validate_card(card, schema)
        gate_errors, warnings = validate_card_gates(card, source, is_single)
        errors = errors + gate_errors

        card_id = card.get("id")
        if isinstance(card_id, str):
            prior = seen_ids.get(card_id)
            if prior is not None and prior != source:
                errors.append(f"id: duplicate id '{card_id}' also used by {prior}")
            else:
                seen_ids[card_id] = source

        results.append(
            ValidationResult(source=source, card_id=card_id, errors=errors, warnings=warnings)
        )
    return results
