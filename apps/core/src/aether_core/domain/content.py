"""Content items as the Core sees them: a file plus analyzed metadata."""

from dataclasses import dataclass

from aether_sdk import ContentMetadata

DISABLED_SUFFIX = ".disabled"


@dataclass
class ContentItem:
    file: str
    enabled: bool
    size_bytes: int
    mtime: int
    metadata: ContentMetadata
    icon_file: str | None = None
    duplicate: bool = False


def is_enabled(file_name: str) -> bool:
    return not file_name.lower().endswith(DISABLED_SUFFIX)


def toggled_name(file_name: str) -> str:
    """The name this file gets when its enabled state flips."""
    if file_name.lower().endswith(DISABLED_SUFFIX):
        return file_name[: -len(DISABLED_SUFFIX)]
    return file_name + DISABLED_SUFFIX


def mark_duplicates(items: list[ContentItem]) -> None:
    """Flag items sharing the same non-empty content id."""
    by_id: dict[str, list[ContentItem]] = {}
    for item in items:
        cid = item.metadata.content_id
        if cid:
            by_id.setdefault(cid, []).append(item)
    for group in by_id.values():
        if len(group) > 1:
            for item in group:
                item.duplicate = True
