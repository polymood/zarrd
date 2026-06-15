# zarrd

A desktop and command line tool for inspecting, editing, and converting Zarr v2 and v3 stores. It provides a Qt interface for browsing hierarchies, viewing and editing array data and attributes, building stores from scratch or from existing v2/v3 stores, and applying bulk operations across many stores. The same functionality is available from the command line for batch conversion and scripting.

## Requirements

Python 3.12 or newer. Dependencies are managed with [uv](https://docs.astral.sh/uv/).

## Installation

```
uv sync
```

This creates a virtual environment and installs the runtime and development dependencies declared in `pyproject.toml`.

## Graphical interface

```
uv run zarrd gui [path/to/store.zarr]
```

The window opens on a dark theme by default and can be switched to light from the View menu. It is organized into three workspace tabs. Opening a store from the File menu loads it into the Explorer and Tree Editor tabs, and the status bar shows the path and whether the store is read only or writable.

### Explorer

A hierarchy tree alongside Data, Metadata, and Attributes panels. Array data is loaded lazily, and arrays with more than two dimensions expose per axis index selectors. Editing a cell or saving attributes writes through to disk when the store is writable.

### Tree Editor

A structural editor for the open store. The toolbar provides Add group, Add array, Rename, and Delete. A side panel shows node metadata and a JSON attributes editor with Merge and Replace actions. Edits apply to disk immediately, and a notice appears when the store is read only.

### Bulk Edit

Applies a queue of operations to many stores at once. First build the target list with Add stores, Add directory, or Add glob, where a directory expands to the store subdirectories it contains. Then build the operation queue, which supports add group, add array, merge or replace attributes, delete attribute keys, delete node, and rename node. The queue is reorderable and editable. Choose whether to modify the stores in place or write modified copies to an output directory so the originals stay untouched. Run executes off the user interface thread with a progress bar and a per store, per operation log.

The Tools menu offers a v2 to v3 conversion dialog and a shortcut to add the current store to the Bulk Edit tab.

## Command line interface

```
uv run zarrd info <store>
uv run zarrd tree <store>
uv run zarrd convert <source> <dest> --to 3 [--overwrite]
uv run zarrd bulk <stores|globs|parent-dir> -o <out-dir> --to 3 [--overwrite]
```

`info` prints store metadata, and `tree` prints the hierarchy. `convert` converts a single store between formats. `bulk` converts many stores and accepts individual store paths, shell globs, or a parent directory whose immediate subdirectories are stores. Output names default to `<name>_v{fmt}.zarr` and can be changed with `--suffix`. Use `--log-file` to also append progress to a file and `-v` for per array detail.

## Development

```
uv run mypy zarrd
```

The codebase is fully type annotated and checked under mypy strict mode.

## License

Released under the MIT License. See `LICENSE` for details.
