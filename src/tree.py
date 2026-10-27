"""Turns the flat list of secrets into the rows of the sidebar: folders and secrets.

Names that contain ``/`` (AWS, Parameter Store, Vault) are shown as a tree whose folders can be
collapsed. While a search is active the matches are listed flat, with their full names.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from src.models import SecretItem
from src.search import matches_query

# Folders start expanded only for small lists; a long list opens collapsed.
EXPAND_ALL_LIMIT = 60

FOLDER = "folder"
SECRET = "secret"


@dataclass(frozen=True)
class Node:
    """One visible row of the sidebar.

    Attributes:
        kind: FOLDER or SECRET.
        title: Text to show (folder name, secret leaf name or, in a search, the full name).
        depth: Indentation level.
        path: For folders, their full path ("app/prod").
        secret: For secrets, the item behind the row.
        count: For folders, how many secrets they contain (at any depth).
        expanded: For folders, whether their content is shown.
    """

    kind: str
    title: str
    depth: int = 0
    path: str = ""
    secret: Optional[SecretItem] = None
    count: int = 0
    expanded: bool = False


@dataclass
class _Folder:
    name: str
    path: str
    folders: Dict[str, "_Folder"] = field(default_factory=dict)
    secrets: List[SecretItem] = field(default_factory=list)

    def count(self) -> int:
        return len(self.secrets) + sum(f.count() for f in self.folders.values())


def _parts(secret: SecretItem) -> List[str]:
    return [p for p in secret.secret_id.strip("/").split("/") if p] or [secret.secret_id]


def has_folders(secrets: List[SecretItem]) -> bool:
    """True when at least one name has a ``/`` in it, so a tree makes sense."""
    return any(len(_parts(s)) > 1 for s in secrets)


def folder_paths(secrets: List[SecretItem]) -> Set[str]:
    """Every folder path that appears in the names."""
    paths: Set[str] = set()
    for secret in secrets:
        parts = _parts(secret)
        for i in range(1, len(parts)):
            paths.add("/".join(parts[:i]))
    return paths


def default_expanded(secrets: List[SecretItem]) -> Set[str]:
    """Folders open when the list is first shown."""
    return folder_paths(secrets) if len(secrets) <= EXPAND_ALL_LIMIT else set()


def _build_trie(secrets: List[SecretItem]) -> _Folder:
    root = _Folder("", "")
    for secret in secrets:
        parts = _parts(secret)
        folder = root
        for i, name in enumerate(parts[:-1], start=1):
            path = "/".join(parts[:i])
            folder = folder.folders.setdefault(name, _Folder(name, path))
        folder.secrets.append(secret)
    return root


def _walk(folder: _Folder, depth: int, expanded: Set[str], out: List[Node]) -> None:
    for name in sorted(folder.folders, key=str.lower):
        child = folder.folders[name]
        is_open = child.path in expanded
        out.append(Node(FOLDER, name, depth, child.path, count=child.count(), expanded=is_open))
        if is_open:
            _walk(child, depth + 1, expanded, out)
    for secret in sorted(folder.secrets, key=lambda s: _parts(s)[-1].lower()):
        out.append(Node(SECRET, _parts(secret)[-1], depth, secret=secret))


def build_nodes(secrets: List[SecretItem], expanded: Set[str], query: str = "") -> List[Node]:
    """List the rows to show.

    Args:
        secrets: Every secret of the active context.
        expanded: Paths of the folders that are open.
        query: Text of the search box; when not blank the matches are listed flat.

    Returns:
        List[Node]: Folder and secret rows in display order.
    """
    if query.strip():
        matches = [s for s in secrets if matches_query(s, query)]
        return [
            Node(SECRET, s.secret_id, 0, secret=s)
            for s in sorted(matches, key=lambda s: s.secret_id.lower())
        ]
    if not has_folders(secrets):
        return [
            Node(SECRET, s.secret_id, 0, secret=s)
            for s in sorted(secrets, key=lambda s: s.secret_id.lower())
        ]
    nodes: List[Node] = []
    _walk(_build_trie(secrets), 0, expanded, nodes)
    return nodes
