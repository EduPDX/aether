"""Contract test suite: generic checks any provider must pass.

Providers (first- or third-party) call :func:`check_provider_contract` from
their own tests; a non-empty return value is a contract violation.
"""

from aether_sdk.content import ContentAnalyzer
from aether_sdk.manifest import ProviderManifest


def check_provider_contract(provider: object) -> list[str]:
    """Run every generic contract check; returns human-readable violations."""
    problems: list[str] = []

    manifest = getattr(provider, "manifest", None)
    if not isinstance(manifest, ProviderManifest):
        return ["provider.manifest missing or not a ProviderManifest"]

    if not manifest.games:
        problems.append("manifest.games must list at least one game")

    try:
        ctypes = provider.content_types()  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 — reporting, not handling
        return problems + [f"content_types() raised: {exc!r}"]

    if not ctypes:
        problems.append("content_types() returned an empty list")

    seen: set[str] = set()
    for ct in ctypes:
        if ct.id in seen:
            problems.append(f"duplicate content type id {ct.id!r}")
        seen.add(ct.id)
        try:
            analyzer = provider.content_analyzer(ct.id)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            problems.append(f"content_analyzer({ct.id!r}) raised: {exc!r}")
            continue
        if not isinstance(analyzer, ContentAnalyzer):
            problems.append(f"analyzer for {ct.id!r} does not satisfy ContentAnalyzer")
        elif analyzer.content_type != ct.id:
            problems.append(
                f"analyzer.content_type {analyzer.content_type!r} != declared id {ct.id!r}"
            )

    try:
        provider.content_analyzer("__does_not_exist__")  # type: ignore[attr-defined]
        problems.append("content_analyzer must raise LookupError for unknown types")
    except LookupError:
        pass
    except Exception as exc:  # noqa: BLE001
        problems.append(f"unknown content type must raise LookupError, got {exc!r}")

    return problems
