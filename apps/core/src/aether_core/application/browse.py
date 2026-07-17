"""Server-side directory browser (for picking instance roots in the UI).

The Core runs on the server machine; admins pick instance directories that
exist *there*, not on their own computer. This lists directories only —
never file contents — and is gated behind ``instances.write``.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DirEntry:
    name: str
    path: str


@dataclass
class BrowseResult:
    path: str | None
    parent: str | None
    separator: str
    entries: list[DirEntry]


def _roots() -> list[DirEntry]:
    """Sensible starting points for the current OS."""
    entries: list[DirEntry] = []
    home = Path.home()
    entries.append(DirEntry(name=f"🏠 {home.name or 'home'}", path=str(home)))
    if os.name == "nt":
        import string

        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if Path(drive).exists():
                entries.append(DirEntry(name=drive, path=drive))
    else:
        entries.append(DirEntry(name="/ (raiz)", path="/"))
    return entries


def browse(path: str | None) -> BrowseResult:
    sep = os.sep
    if not path:
        return BrowseResult(path=None, parent=None, separator=sep, entries=_roots())

    target = Path(path).resolve()
    if not target.is_dir():
        # Fall back to roots so the UI never dead-ends.
        return BrowseResult(path=None, parent=None, separator=sep, entries=_roots())

    entries: list[DirEntry] = []
    try:
        for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
            try:
                if child.is_dir():
                    entries.append(DirEntry(name=child.name, path=str(child)))
            except OSError:
                continue
    except PermissionError:
        pass

    parent = target.parent
    parent_str = str(parent) if parent != target else None
    return BrowseResult(path=str(target), parent=parent_str, separator=sep, entries=entries)
