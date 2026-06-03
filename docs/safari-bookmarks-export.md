# safari_bookmarks_export.py

[`safari_bookmarks_export.py`](../python/safari_bookmarks_export.py) exports selected folders from Safari's `$HOME/Library/Safari/Bookmarks.plist` into Netscape bookmarks HTML, which Firefox and Chrome can import.

## What It Does

- reads `$HOME/Library/Safari/Bookmarks.plist`
- lists top-level Safari bookmark folders with bookmark counts
- searches child folders in the current `--list` scope
- clones each matched folder with its nested folders and bookmarks
- prints browsable folder/bookmark trees with `--list --tree`
- writes Firefox/Chrome importable HTML
- creates a default output file beside the script when `--output` is not provided

## Dependencies

Install the repo requirements before running the script:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

This script uses:

- Python standard library modules for plist parsing, path handling, HTML escaping, and argument parsing
- [`rich`](https://github.com/Textualize/rich) for terminal tables and trees

`rich` is already listed in the repo [`requirements.txt`](../requirements.txt).

## Basic Usage

Search for one folder:

```bash
python3 python/safari_bookmarks_export.py --search "Dev Docs"
```

Search inside a selected folder:

```bash
python3 python/safari_bookmarks_export.py --list BookmarksMenu / Gaming --search "some folder"
```

Search through every nested folder under a selected folder:

```bash
python3 python/safari_bookmarks_export.py --list BookmarksMenu / Gaming --search "some folder" --all
```

List top-level folders:

```bash
python3 python/safari_bookmarks_export.py --list
```

List child folders under an exact root folder name:

```bash
python3 python/safari_bookmarks_export.py --list "Dev Docs"
```

List child folders under an exact nested folder path:

```bash
python3 python/safari_bookmarks_export.py --list "Folder A" / FolderB
```

List every nested folder as a tree:

```bash
python3 python/safari_bookmarks_export.py --list --all
```

List folders and bookmarks directly under a folder:

```bash
python3 python/safari_bookmarks_export.py --list "Folder A" --tree
```

List every nested folder and bookmark under a folder:

```bash
python3 python/safari_bookmarks_export.py --list "Folder A" --tree --all
```

Browse and export a nested folder in one run:

```bash
python3 python/safari_bookmarks_export.py --list BookmarksMenu / "Somefolder B" --all --tree --export
```

When `--export` is used and `--output` is omitted, the script writes to a dated file in the same folder as the script:

```bash
python3 python/safari_bookmarks_export.py --list "Dev Docs" --export
```

Example output path:

```text
python/Dev-Docs-2026-06-03_14-22-10.html
```

## Arguments

<table>
  <thead>
    <tr>
      <th>Argument</th>
      <th>Type</th>
      <th>Notes</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><nobr><code>--search</code></nobr></td>
      <td>Option</td>
      <td>Search child folders in the current <code>--list</code> scope, or root when <code>--list</code> is omitted. Can be used more than once.</td>
    </tr>
    <tr>
      <td><nobr><code>-s</code>, <code>--source</code></nobr></td>
      <td>Option</td>
      <td>Override the Safari plist path.</td>
    </tr>
    <tr>
      <td><nobr><code>-o</code>, <code>--output</code></nobr></td>
      <td>Option</td>
      <td>With <code>--export</code>, write to a specific HTML file.</td>
    </tr>
    <tr>
      <td><nobr><code>--export</code></nobr></td>
      <td>Flag</td>
      <td>Write selected <code>--list</code> folder results to Firefox/Chrome importable HTML. Cannot be used with <code>--search</code>.</td>
    </tr>
    <tr>
      <td><nobr><code>--list</code></nobr></td>
      <td>Flag</td>
      <td>Print top-level folders, or list child folders under an exact slash-separated folder path.</td>
    </tr>
    <tr>
      <td><nobr><code>--all</code></nobr></td>
      <td>Flag</td>
      <td>With <code>--list</code>, print every nested folder as a tree.</td>
    </tr>
    <tr>
      <td><nobr><code>--tree</code></nobr></td>
      <td>Flag</td>
      <td>With <code>--list</code>, include bookmark entries in tree output.</td>
    </tr>
    <tr>
      <td><nobr><code>--folders-only</code></nobr></td>
      <td>Flag</td>
      <td>With <code>--tree</code>, hide bookmark entries and show only folders.</td>
    </tr>
  </tbody>
</table>

## Searching

Plain searches check only the top-level folders shown by `--list`.
Folder matching is case-insensitive. The search prefers exact matches first, then falls back to partial matches.

```bash
python3 python/safari_bookmarks_export.py --search "Dev"
```

This can match a root folder named `Dev Docs`.

Use `--list` to scope a search inside an exact folder path:

```bash
python3 python/safari_bookmarks_export.py --list BookmarksMenu / Gaming --search "some folder"
```

This looks for exact folder path `BookmarksMenu / Gaming`, then searches only the child folders under `Gaming`.

Add `--all` to search every descendant folder under that selected scope:

```bash
python3 python/safari_bookmarks_export.py --list BookmarksMenu / Gaming --search "some folder" --all
```

If the final search term matches multiple folders, the script lists all of them:

```bash
python3 python/safari_bookmarks_export.py --search "Dev"
```

`--search` is discovery-only. It cannot be combined with `--export`.

## Listing

`--list` without a value lists the top-level Safari folders:

```bash
python3 python/safari_bookmarks_export.py --list
```

`--list` with a value requires exact folder names. Use `/` to walk deeper. Quotes are only needed around folder names that contain spaces:

```bash
python3 python/safari_bookmarks_export.py --list "Folder A"
python3 python/safari_bookmarks_export.py --list FolderA / "Folder B" / FolderC
```

Add `--all` to print every nested folder below the selected folder as a tree:

```bash
python3 python/safari_bookmarks_export.py --list FolderA / "Folder B" --all
```

Add `--tree` to include bookmark entries while browsing. Without `--all`, it shows only the selected folder's direct contents:

```bash
python3 python/safari_bookmarks_export.py --list FolderA / "Folder B" --tree
```

Use `--tree --all` to recurse through every nested folder and bookmark under the selected folder:

```bash
python3 python/safari_bookmarks_export.py --list FolderA / "Folder B" --tree --all
```

Add `--export` to write that selected folder while still printing the requested list/tree view:

```bash
python3 python/safari_bookmarks_export.py --list FolderA / "Folder B" --all --tree --export
```

## Importing

Firefox:

```text
Bookmarks > Manage Bookmarks > Import and Backup > Import Bookmarks from HTML
```

Chrome:

```text
Bookmarks Manager > three-dot menu > Import bookmarks
```

## Good To Know

- Safari does not need to be open.
- The default Safari bookmarks path is based on `$HOME`, not a hardcoded user path.
- The standard Safari bookmarks location is under the user's Library folder, so it is not tied to Intel or Apple Silicon Macs.
- The script only reads `Bookmarks.plist`; it does not modify Safari bookmarks.
- Output HTML is ignored by Git through the repo's `*.html` ignore rule.
