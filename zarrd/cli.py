from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Sequence

import zarr
from zarr import Array

from zarrd import __version__
from zarrd.convert import ConvertResult, convert_store, default_dest
from zarrd.core import build_tree, detect_format, node_info

log = logging.getLogger("zarrd")


def _setup_logging(verbose: bool, log_file: str | None) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, mode="a"))
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
        force=True,
    )


def _print_tree(path: str) -> int:
    node = zarr.open(store=path, mode="r")
    if isinstance(node, Array):
        info = node_info(node, "/")
        assert info.array is not None
        a = info.array
        print(f"/ (array) shape={a.shape} dtype={a.dtype} v{a.zarr_format}")
        return 0
    tree = build_tree(node, "/")
    _render(tree, "")
    return 0


def _render(tree, prefix: str) -> None:  # type: ignore[no-untyped-def]
    children = tree.children
    for i, child in enumerate(children):
        last = i == len(children) - 1
        branch = "└── " if last else "├── "
        if child.kind == "array" and child.array is not None:
            a = child.array
            label = f"{child.name}  [{a.dtype} {a.shape} chunks={a.chunks} v{a.zarr_format}]"
        else:
            label = f"{child.name}/  [group v{child.zarr_format}]"
        print(prefix + branch + label)
        if child.kind == "group":
            _render(child, prefix + ("    " if last else "│   "))


def _print_info(path: str) -> int:
    fmt = detect_format(path)
    node = zarr.open(store=path, mode="r")
    info = node_info(node, "/")
    print(f"path: {path}")
    print(f"detected format: zarr v{fmt}")
    print(f"kind: {info.kind}")
    if info.array is not None:
        a = info.array
        print(f"shape: {a.shape}")
        print(f"chunks: {a.chunks}")
        print(f"dtype: {a.dtype}")
        print(f"order: {a.order}")
        print(f"fill_value: {a.fill_value}")
        print(f"compressors: {', '.join(a.compressors) or 'none'}")
        print(f"filters: {', '.join(a.filters) or 'none'}")
        print(f"nbytes: {a.nbytes}")
    if info.group is not None:
        print(f"members: {info.group.n_members}")
    if info.attrs:
        print("attributes:")
        for k, v in info.attrs.items():
            print(f"  {k}: {v}")
    return 0


def _report(results: Sequence[ConvertResult]) -> int:
    failures = 0
    for r in results:
        status = "OK" if r.ok else "FAIL"
        print(
            f"[{status}] {r.source} -> {r.dest} "
            f"(arrays={r.arrays_converted} groups={r.groups_converted} "
            f"bytes={r.bytes_copied})"
        )
        for err in r.errors:
            failures += 1
            print(f"        error: {err}", file=sys.stderr)
    return 1 if failures else 0


def _cmd_convert(args: argparse.Namespace) -> int:
    def progress(path: str, done: int, total: int) -> None:
        if not args.quiet:
            print(f"  [{done}/{total}] {path}", file=sys.stderr)

    result = convert_store(
        args.source,
        args.dest,
        target_format=args.to,
        overwrite=args.overwrite,
        progress=progress,
    )
    return _report([result])


def _resolve_sources(patterns: Sequence[str]) -> list[Path]:
    sources: list[Path] = []
    for pattern in patterns:
        p = Path(pattern)
        if any(ch in pattern for ch in "*?["):
            sources.extend(sorted(Path().glob(pattern)))
        elif (
            p.is_dir()
            and not (p / "zarr.json").exists()
            and not (p / ".zgroup").exists()
            and not (p / ".zarray").exists()
        ):
            sources.extend(sorted(c for c in p.iterdir() if c.is_dir()))
        else:
            sources.append(p)
    return sources


def _cmd_bulk(args: argparse.Namespace) -> int:
    _setup_logging(args.verbose, args.log_file)
    sources = _resolve_sources(args.sources)
    if not sources:
        log.error("no source stores found for: %s", " ".join(args.sources))
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log.info(
        "bulk convert: %d store(s) -> %s (target v%d)",
        len(sources),
        out_dir,
        args.to,
    )

    results: list[ConvertResult] = []
    started = time.perf_counter()
    for i, src in enumerate(sources, start=1):
        dest = default_dest(src, out_dir, args.to, args.suffix)
        log.info("[%d/%d] %s -> %s", i, len(sources), src, dest.name)

        def progress(path: str, done: int, total: int) -> None:
            log.debug("        array %d/%d %s", done, total, path)

        t0 = time.perf_counter()
        if dest.exists() and not args.overwrite:
            log.warning(
                "[%d/%d] skipped, destination exists: %s", i, len(sources), dest
            )
            r = ConvertResult(source=str(src), dest=str(dest), target_format=args.to)
            r.errors.append("destination exists (use --overwrite)")
            results.append(r)
            continue
        try:
            r = convert_store(
                src,
                dest,
                target_format=args.to,
                overwrite=args.overwrite,
                progress=progress,
            )
        except Exception as exc:  # noqa: BLE001
            log.error("[%d/%d] FAILED %s: %s", i, len(sources), src, exc)
            r = ConvertResult(source=str(src), dest=str(dest), target_format=args.to)
            r.errors.append(str(exc))
            results.append(r)
            continue
        elapsed = time.perf_counter() - t0
        results.append(r)
        if r.ok:
            log.info(
                "[%d/%d] OK %s (arrays=%d groups=%d %.1f MiB %.2fs)",
                i,
                len(sources),
                dest.name,
                r.arrays_converted,
                r.groups_converted,
                r.bytes_copied / 1048576,
                elapsed,
            )
        else:
            log.warning(
                "[%d/%d] done with %d error(s): %s",
                i,
                len(sources),
                len(r.errors),
                dest.name,
            )
            for err in r.errors:
                log.warning("        %s", err)

    ok = sum(1 for r in results if r.ok)
    failed = len(results) - ok
    total_bytes = sum(r.bytes_copied for r in results)
    log.info(
        "summary: %d ok, %d failed, %.1f MiB in %.2fs",
        ok,
        failed,
        total_bytes / 1048576,
        time.perf_counter() - started,
    )
    return 1 if failed else 0


def _cmd_gui(args: argparse.Namespace) -> int:
    from zarrd.gui.app import run

    return run(args.path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zarrd", description="Zarr multi-tool: view, edit, and convert zarr stores"
    )
    parser.add_argument("--version", action="version", version=f"zarrd {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_gui = sub.add_parser("gui", help="launch the GUI")
    p_gui.add_argument("path", nargs="?", default=None, help="store to open on start")
    p_gui.set_defaults(func=_cmd_gui)

    p_info = sub.add_parser("info", help="print store metadata")
    p_info.add_argument("path")
    p_info.set_defaults(func=lambda a: _print_info(a.path))

    p_tree = sub.add_parser("tree", help="print the hierarchy tree")
    p_tree.add_argument("path")
    p_tree.set_defaults(func=lambda a: _print_tree(a.path))

    p_conv = sub.add_parser("convert", help="convert a single store")
    p_conv.add_argument("source")
    p_conv.add_argument("dest")
    p_conv.add_argument("--to", type=int, choices=(2, 3), default=3)
    p_conv.add_argument("--overwrite", action="store_true")
    p_conv.add_argument("-q", "--quiet", action="store_true")
    p_conv.set_defaults(func=_cmd_convert)

    p_bulk = sub.add_parser("bulk", help="bulk-convert many stores")
    p_bulk.add_argument("sources", nargs="+", help="stores, globs, or a parent dir")
    p_bulk.add_argument("-o", "--out-dir", required=True)
    p_bulk.add_argument("--to", type=int, choices=(2, 3), default=3)
    p_bulk.add_argument("--overwrite", action="store_true")
    p_bulk.add_argument("--suffix", default="_v{fmt}")
    p_bulk.add_argument(
        "--log-file", default=None, help="also append logs to this file"
    )
    p_bulk.add_argument(
        "-v", "--verbose", action="store_true", help="log each array as it is copied"
    )
    p_bulk.set_defaults(func=_cmd_bulk)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
