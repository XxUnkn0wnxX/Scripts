#!/usr/bin/env python3
"""
Export selected Safari bookmark folders to browser-importable HTML.
"""

from __future__ import annotations

import argparse
import html
import os
import plistlib
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent


def is_repo_root(candidate: Path) -> bool:
    return (candidate / ".git").exists() or (
        (candidate / "requirements.txt").is_file() and (candidate / "docs").is_dir()
    )


def resolve_repo_root(start_dir: Path, max_depth: int = 1) -> Path:
    candidate = start_dir.resolve()
    fallback = candidate

    for depth in range(max_depth + 1):
        if depth == 1:
            fallback = candidate
        if is_repo_root(candidate):
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent

    return fallback


REPO_ROOT = resolve_repo_root(SCRIPT_DIR)
REPO_VENV_DIR = REPO_ROOT / ".venv"
DOCS_PATH = REPO_ROOT / "docs" / "safari-bookmarks-export.md"


def normalize_platform_path(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def resolve_repo_venv_python() -> Optional[Path]:
    candidates = [
        REPO_VENV_DIR / "bin" / "python",
        REPO_VENV_DIR / "bin" / "python3",
        REPO_VENV_DIR / "Scripts" / "python.exe",
    ]
    return next((candidate for candidate in candidates if candidate.exists()), None)


def ensure_repo_venv_or_reexec(argv: Optional[Sequence[str]] = None) -> None:
    active_argv = list(argv if argv is not None else sys.argv[1:])
    repo_venv_python = resolve_repo_venv_python()
    if not REPO_VENV_DIR.exists() or repo_venv_python is None:
        docs_hint = str(DOCS_PATH.relative_to(REPO_ROOT)) if DOCS_PATH.exists() else "docs/safari-bookmarks-export.md"
        raise SystemExit(
            "No local .venv was found for safari_bookmarks_export.py.\n"
            f"Create one in {REPO_ROOT} and install the repo requirements before running the script.\n"
            f"See {docs_hint} for setup instructions."
        )

    if normalize_platform_path(Path(sys.prefix)) != normalize_platform_path(REPO_VENV_DIR) and os.environ.get(
        "SAFARI_BOOKMARKS_EXPORT_REEXEC"
    ) != "1":
        os.environ["SAFARI_BOOKMARKS_EXPORT_REEXEC"] = "1"
        os.execv(str(repo_venv_python), [str(repo_venv_python), str(SCRIPT_PATH), *active_argv])


ensure_repo_venv_or_reexec()


from rich.console import Console
from rich.markup import escape as rich_escape
from rich.table import Table
from rich.tree import Tree


APP_NAME = "safari-bookmarks-export"
DEFAULT_SOURCE = "$HOME/Library/Safari/Bookmarks.plist"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR
SAFARI_EPOCH_OFFSET = 978307200

console = Console()
error_console = Console(stderr=True)


class CliError(RuntimeError):
    """Raised for user-visible CLI failures."""


class HelpfulFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    def _get_help_string(self, action: argparse.Action) -> str:
        help_text = action.help or ""
        if "%(default)" in help_text:
            return help_text
        if action.default in (None, False) or action.default == argparse.SUPPRESS:
            return help_text
        if isinstance(action, argparse._StoreTrueAction):
            return help_text
        return f"{help_text} (default: %(default)s)"


@dataclass
class BookmarkNode:
    title: str
    path: tuple[str, ...]
    url: Optional[str] = None
    added: Optional[int] = None
    children: list["BookmarkNode"] = field(default_factory=list)

    @property
    def is_folder(self) -> bool:
        return self.url is None

    @property
    def bookmark_count(self) -> int:
        if not self.is_folder:
            return 1
        return sum(child.bookmark_count for child in self.children)

    @property
    def folder_count(self) -> int:
        if not self.is_folder:
            return 0
        return 1 + sum(child.folder_count for child in self.children)

    @property
    def display_path(self) -> str:
        return " / ".join(self.path)


def get_title(item: dict[str, Any], fallback: str = "Untitled") -> str:
    title = item.get("Title")
    if isinstance(title, str) and title.strip():
        return title.strip()

    uri_dict = item.get("URIDictionary")
    if isinstance(uri_dict, dict):
        uri_title = uri_dict.get("title")
        if isinstance(uri_title, str) and uri_title.strip():
            return uri_title.strip()

    return fallback


def safari_timestamp_to_unix(value: Any) -> Optional[int]:
    if isinstance(value, datetime):
        return int(value.timestamp())
    if isinstance(value, (int, float)):
        return int(value + SAFARI_EPOCH_OFFSET)
    return None


def parse_safari_item(item: dict[str, Any], path: tuple[str, ...]) -> Optional[BookmarkNode]:
    item_type = item.get("WebBookmarkType")
    if item_type == "WebBookmarkTypeLeaf":
        url = item.get("URLString")
        if not isinstance(url, str) or not url:
            return None
        title = get_title(item, url)
        return BookmarkNode(
            title=title,
            path=(*path, title),
            url=url,
            added=safari_timestamp_to_unix(item.get("WebBookmarkDateAdded")),
        )

    children = item.get("Children")
    if item_type == "WebBookmarkTypeList" or isinstance(children, list):
        title = get_title(item, "Bookmarks")
        node_path = (*path, title) if title != "Bookmarks" or path else (title,)
        parsed_children = [
            parsed
            for child in children or []
            if isinstance(child, dict)
            for parsed in [parse_safari_item(child, node_path)]
            if parsed is not None
        ]
        return BookmarkNode(title=title, path=node_path, children=parsed_children)

    return None


def load_bookmarks(source: Path) -> BookmarkNode:
    if not source.exists():
        raise CliError(f"Safari bookmarks plist was not found: {source}")

    try:
        with source.open("rb") as bookmark_file:
            plist = plistlib.load(bookmark_file)
    except Exception as error:
        raise CliError(f"Could not read Safari bookmarks plist: {error}") from error

    if not isinstance(plist, dict):
        raise CliError("Safari bookmarks plist did not contain the expected dictionary root.")

    root = parse_safari_item(plist, ())
    if root is None:
        raise CliError("Safari bookmarks plist did not contain a recognizable bookmark tree.")
    return root


def iter_folders(node: BookmarkNode) -> Iterable[BookmarkNode]:
    if node.is_folder:
        yield node
        for child in node.children:
            yield from iter_folders(child)


def iter_root_folders(root: BookmarkNode) -> Iterable[BookmarkNode]:
    for child in root.children:
        if child.is_folder:
            yield child


def normalize_name(value: str, case_sensitive: bool) -> str:
    return value if case_sensitive else value.casefold()


def split_folder_path(query: str) -> list[str]:
    parts = [part.strip() for part in query.split("/")]
    if not all(parts):
        raise CliError(f"Folder path has an empty segment: {query}")
    return parts


def normalize_list_query(parts: Optional[Sequence[str]]) -> Optional[str]:
    if parts is None or not parts:
        return None
    query = " ".join(parts).strip()
    return query or None


def child_folders(node: BookmarkNode) -> list[BookmarkNode]:
    return [child for child in node.children if child.is_folder]


def descendant_folders(node: BookmarkNode) -> list[BookmarkNode]:
    descendants: list[BookmarkNode] = []
    for child in child_folders(node):
        descendants.append(child)
        descendants.extend(descendant_folders(child))
    return descendants


def match_folder_level(folders: Sequence[BookmarkNode], query: str, *, case_sensitive: bool) -> list[BookmarkNode]:
    normalized_query = normalize_name(query, case_sensitive)
    exact_matches = [
        folder for folder in folders if normalize_name(folder.title, case_sensitive) == normalized_query
    ]
    if exact_matches:
        return exact_matches
    return [
        folder for folder in folders if normalized_query in normalize_name(folder.title, case_sensitive)
    ]


def match_folder_level_exact(folders: Sequence[BookmarkNode], query: str, *, case_sensitive: bool) -> list[BookmarkNode]:
    normalized_query = normalize_name(query, case_sensitive)
    return [
        folder for folder in folders if normalize_name(folder.title, case_sensitive) == normalized_query
    ]


def resolve_exact_folder_path(root: BookmarkNode, query: str, *, case_sensitive: bool) -> BookmarkNode:
    current_level = child_folders(root)
    selected: Optional[BookmarkNode] = None

    for part in split_folder_path(query):
        matches = match_folder_level_exact(current_level, part, case_sensitive=case_sensitive)
        if not matches:
            raise CliError(f"No exact folder match was found for path segment '{part}' in list query: {query}")
        if len(matches) > 1:
            summarize_matches(matches)
            raise CliError(f"List query path segment matched multiple folders exactly: {part}")
        selected = matches[0]
        current_level = child_folders(selected)

    if selected is None:
        raise CliError(f"List query did not contain a usable folder path: {query}")
    return selected


def resolve_target_folders(
    search_root: BookmarkNode,
    searches: Sequence[str],
    *,
    case_sensitive: bool,
    include_nested: bool,
) -> list[BookmarkNode]:
    selected: list[BookmarkNode] = []
    selected_ids: set[int] = set()
    search_pool = descendant_folders(search_root) if include_nested else child_folders(search_root)

    for search in searches:
        matches = match_folder_level(search_pool, search, case_sensitive=case_sensitive)
        if not matches:
            raise CliError(f"No matching Safari bookmark folder was found for search: {search}")

        for folder in matches:
            folder_id = id(folder)
            if folder_id not in selected_ids:
                selected.append(folder)
                selected_ids.add(folder_id)

    return selected


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    cleaned = cleaned.strip("-._")
    return cleaned or "safari-bookmarks"


def default_output_path(folders: Sequence[BookmarkNode]) -> Path:
    if len(folders) == 1:
        base_name = slugify(folders[0].title)
    else:
        base_name = "selected-safari-bookmarks"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return DEFAULT_OUTPUT_DIR / f"{base_name}-{timestamp}.html"


def dedupe_folders(folders: Iterable[BookmarkNode]) -> list[BookmarkNode]:
    selected: list[BookmarkNode] = []
    selected_ids: set[int] = set()
    for folder in folders:
        folder_id = id(folder)
        if folder_id not in selected_ids:
            selected.append(folder)
            selected_ids.add(folder_id)
    return selected


def format_add_date(node: BookmarkNode) -> str:
    return f' ADD_DATE="{node.added}"' if node.added else ""


def write_html_node(lines: list[str], node: BookmarkNode, indent: int) -> None:
    prefix = "    " * indent
    escaped_title = html.escape(node.title, quote=True)

    if node.is_folder:
        lines.append(f"{prefix}<DT><H3>{escaped_title}</H3>")
        lines.append(f"{prefix}<DL><p>")
        for child in node.children:
            write_html_node(lines, child, indent + 1)
        lines.append(f"{prefix}</DL><p>")
        return

    escaped_url = html.escape(node.url or "", quote=True)
    lines.append(f'{prefix}<DT><A HREF="{escaped_url}"{format_add_date(node)}>{escaped_title}</A>')


def export_html(folders: Sequence[BookmarkNode], output: Path) -> None:
    lines = [
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>",
        '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
        "<TITLE>Safari Bookmarks Export</TITLE>",
        "<H1>Safari Bookmarks Export</H1>",
        "<DL><p>",
    ]
    for folder in folders:
        write_html_node(lines, folder, 1)
    lines.append("</DL><p>")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_folder_list(
    root: BookmarkNode,
    include_nested: bool,
    include_bookmarks: bool,
    folders_only: bool,
    list_query: Optional[str],
    case_sensitive: bool,
) -> None:
    list_root = resolve_exact_folder_path(root, list_query, case_sensitive=case_sensitive) if list_query else root

    if include_bookmarks:
        tree = Tree(f"[bold cyan]{rich_escape(list_root.title)}[/] [dim]({list_root.bookmark_count})[/]")
        add_list_tree_nodes(tree, list_root, recursive=include_nested, include_bookmarks=not folders_only)
        console.print(tree)
        return

    if include_nested:
        tree = Tree(f"[bold cyan]{rich_escape(list_root.title)}[/] [dim]({list_root.bookmark_count})[/]")
        add_folder_tree_nodes(tree, list_root)
        console.print(tree)
        return

    table_title = "Safari Root Bookmark Folders" if list_query is None else f"Folders Under {list_root.display_path}"
    table = Table(title=table_title)
    table.add_column("Folder")
    table.add_column("Bookmarks", justify="right")
    table.add_column("Nested Folders", justify="right")
    table.add_column("Path")

    folders = iter_root_folders(list_root) if list_query is None else child_folders(list_root)
    for folder in folders:
        table.add_row(
            folder.title,
            str(folder.bookmark_count),
            str(max(folder.folder_count - 1, 0)),
            folder.display_path,
        )

    console.print(table)


def add_folder_tree_nodes(tree: Tree, node: BookmarkNode) -> None:
    for child in node.children:
        if not child.is_folder:
            continue
        branch = tree.add(f"[bold cyan]{rich_escape(child.title)}[/] [dim]({child.bookmark_count})[/]")
        add_folder_tree_nodes(branch, child)


def add_list_tree_nodes(tree: Tree, node: BookmarkNode, recursive: bool, include_bookmarks: bool) -> None:
    for child in node.children:
        if child.is_folder:
            branch = tree.add(f"[bold cyan]{rich_escape(child.title)}[/] [dim]({child.bookmark_count})[/]")
            if recursive:
                add_list_tree_nodes(branch, child, recursive=recursive, include_bookmarks=include_bookmarks)
        elif include_bookmarks:
            tree.add(f"[green]{rich_escape(child.title)}[/] [dim]{rich_escape(child.url or '')}[/]")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="safari_bookmarks_export.py",
        description="Export selected Safari bookmark folders to Firefox/Chrome importable HTML.",
        epilog=(
            "Search syntax:\n"
            "  --search \"Dev\"                  Search the current list scope for Dev. Exact matches win, partial matches follow.\n"
            "  --list BookmarksMenu / Gaming --search \"some folder\"\n"
            "                                  Search inside BookmarksMenu / Gaming.\n"
            "  --list BookmarksMenu / Gaming --search \"some folder\" --all\n"
            "                                  Search all nested folders under Gaming.\n"
            "\n"
            "List syntax:\n"
            "  --list                          List root folders.\n"
            "  --list \"Dev\"                    List child folders inside root folder Dev. Exact match only.\n"
            "  --list Dev / Tools              List child folders inside Dev / Tools. Exact match only.\n"
            "  --list Dev / \"My Tools\" / Docs  Quote only folder names that contain spaces.\n"
            "  --list Dev / Tools --all        Print every nested folder under Dev / Tools.\n"
            "  --list Dev / Tools --tree       Print folders and bookmarks directly under Dev / Tools.\n"
            "  --list Dev / Tools --tree --all\n"
            "                                  Print all nested folders and bookmarks under Dev / Tools.\n"
            "  --list Dev / Tools --export     Export Dev / Tools.\n"
            "\n"
            "Common uses:\n"
            "  safari_bookmarks_export.py --list\n"
            "  safari_bookmarks_export.py --list --all\n"
            "  safari_bookmarks_export.py --list \"Dev Docs\" --tree --all\n"
            "  safari_bookmarks_export.py --list \"Dev Docs\" --export\n"
            "  safari_bookmarks_export.py --search \"Dev Docs\"\n"
            "  safari_bookmarks_export.py --list BookmarksMenu / Gaming --search \"some folder\"\n"
        ),
        formatter_class=HelpfulFormatter,
    )
    parser.add_argument(
        "--search",
        action="append",
        dest="searches",
        metavar="QUERY",
        help="Search child folders in the current --list scope, or root when --list is omitted. Can be used more than once.",
    )
    parser.add_argument(
        "-s",
        "--source",
        default=DEFAULT_SOURCE,
        help="Safari Bookmarks.plist path.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output HTML file for --export. Defaults to the script folder with a dated filename.",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Write selected folder(s) to Firefox/Chrome importable HTML.",
    )
    parser.add_argument(
        "--list",
        nargs="*",
        metavar="QUERY",
        help="List root folders, or list child folders under an exact slash-separated folder path.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="With --list, print every nested folder as a tree.",
    )
    parser.add_argument(
        "--tree",
        action="store_true",
        help="With --list, include bookmark entries in tree output.",
    )
    parser.add_argument(
        "--folders-only",
        action="store_true",
        help="With --tree, hide bookmark entries and show nested folders only.",
    )
    return parser


def summarize_matches(matches: Sequence[BookmarkNode]) -> None:
    table = Table(title="Matched Folders")
    table.add_column("Folder")
    table.add_column("Bookmarks", justify="right")
    table.add_column("Path")
    for folder in matches:
        table.add_row(folder.title, str(folder.bookmark_count), folder.display_path)
    console.print(table)


def run(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    list_requested = args.list is not None
    list_query = normalize_list_query(args.list)
    searches = list(args.searches or [])

    if args.tree and not list_requested:
        parser.error("--tree can only be used with --list")
    if args.folders_only and not args.tree:
        parser.error("--folders-only can only be used with --list --tree")
    if args.all and not list_requested:
        parser.error("--all can only be used with --list")
    if args.output and not args.export:
        parser.error("--output can only be used with --export")
    if args.export and searches:
        parser.error("--export cannot be used with --search")
    if not list_requested and not searches:
        parser.error("provide --search, or use --list")

    source_path = Path(os.path.expandvars(os.path.expanduser(args.source)))
    root = load_bookmarks(source_path)
    list_root = resolve_exact_folder_path(root, list_query, case_sensitive=False) if list_query else root

    list_export_targets: list[BookmarkNode] = []
    if list_requested:
        print_folder_list(
            root,
            include_nested=args.all,
            include_bookmarks=args.tree,
            folders_only=args.folders_only,
            list_query=list_query,
            case_sensitive=False,
        )
        list_export_targets = [list_root] if list_query else list(iter_root_folders(root))
        if not searches and not args.export:
            return 0

    search_matches = (
        resolve_target_folders(list_root, searches, case_sensitive=False, include_nested=args.all) if searches else []
    )
    if searches:
        summarize_matches(search_matches)
        if not args.export and not list_requested:
            return 0

    if not args.export:
        return 0

    export_targets = dedupe_folders(list_export_targets)
    if not export_targets:
        raise CliError("No folders were selected for export.")

    output = args.output or default_output_path(export_targets)
    export_html(export_targets, output)
    if not searches:
        summarize_matches(export_targets)
    console.print(f"[bold green]Exported[/] {len(export_targets)} folder(s) to [bold]{output}[/]")
    return 0


def main() -> None:
    try:
        raise SystemExit(run())
    except CliError as error:
        error_console.print(f"[bold red]Error:[/] {error}")
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
