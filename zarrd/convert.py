from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

import numpy as np
import zarr
from zarr import Array, Group

ZarrFormat = Literal[2, 3]
ProgressFn = Callable[[str, int, int], None]


class ConversionError(RuntimeError):
    pass


@dataclass
class ConvertResult:
    source: str
    dest: str
    target_format: int
    arrays_converted: int = 0
    groups_converted: int = 0
    bytes_copied: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _iter_chunk_blocks(
    shape: tuple[int, ...], chunks: tuple[int, ...]
) -> list[tuple[slice, ...]]:
    if not shape:
        return [()]
    ranges: list[list[slice]] = []
    for dim, chunk in zip(shape, chunks):
        step = chunk if chunk > 0 else dim
        dim_slices = [slice(i, min(i + step, dim)) for i in range(0, dim, step or 1)]
        if not dim_slices:
            dim_slices = [slice(0, 0)]
        ranges.append(dim_slices)
    blocks: list[tuple[slice, ...]] = [()]
    for dim_slices in ranges:
        blocks = [b + (s,) for b in blocks for s in dim_slices]
    return blocks


def _copy_array(
    src: Array[Any],
    dest_parent: Group,
    name: str,
    target_format: ZarrFormat,
    overwrite: bool,
) -> int:
    chunks = tuple(int(c) for c in src.chunks)
    shape = tuple(int(s) for s in src.shape)
    dim_names = getattr(src.metadata, "dimension_names", None)
    dim_arg = (
        tuple(dim_names) if (target_format == 3 and dim_names is not None) else None
    )
    dest = dest_parent.create_array(
        name,
        shape=shape,
        chunks=chunks,
        dtype=src.dtype,
        fill_value=src.fill_value,
        attributes=dict(src.attrs),
        overwrite=overwrite,
        dimension_names=dim_arg,
    )
    copied = 0
    if 0 in shape or not shape:
        if not shape:
            dest[...] = src[...]
            copied += int(src.nbytes)
        return copied
    for block in _iter_chunk_blocks(shape, chunks):
        chunk_data = np.asarray(src[block])
        dest[block] = chunk_data
        copied += int(chunk_data.nbytes)
    return copied


def _copy_group(
    src: Group,
    dest: Group,
    target_format: ZarrFormat,
    overwrite: bool,
    result: ConvertResult,
    progress: ProgressFn | None,
    total: int,
    counter: list[int],
) -> None:
    dest.update_attributes(dict(src.attrs))
    members = sorted(src.members(), key=lambda kv: kv[0])
    for name, obj in members:
        if isinstance(obj, Group):
            child = dest.create_group(name, overwrite=overwrite)
            result.groups_converted += 1
            _copy_group(
                obj, child, target_format, overwrite, result, progress, total, counter
            )
        else:
            try:
                result.bytes_copied += _copy_array(
                    obj, dest, name, target_format, overwrite
                )
                result.arrays_converted += 1
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"{obj.path}: {exc}")
            counter[0] += 1
            if progress is not None:
                progress(obj.path, counter[0], total)


def _count_arrays(group: Group) -> int:
    n = 0
    for _, obj in group.members():
        if isinstance(obj, Group):
            n += _count_arrays(obj)
        else:
            n += 1
    return n


def convert_store(
    source: str | Path,
    dest: str | Path,
    target_format: ZarrFormat = 3,
    overwrite: bool = False,
    progress: ProgressFn | None = None,
) -> ConvertResult:
    source = str(source)
    dest = str(dest)
    if Path(dest).exists() and not overwrite:
        raise ConversionError(f"destination exists: {dest} (use overwrite)")

    src_node = zarr.open(store=source, mode="r")
    result = ConvertResult(source=source, dest=dest, target_format=target_format)

    if isinstance(src_node, Array):
        parent = zarr.open_group(
            store=dest, mode="w", zarr_format=target_format
        )
        name = Path(source).name or "array"
        result.bytes_copied += _copy_array(
            src_node, parent, name, target_format, overwrite=True
        )
        result.arrays_converted += 1
        if progress is not None:
            progress(name, 1, 1)
        return result

    src_group: Group = src_node
    dest_group = zarr.open_group(store=dest, mode="w", zarr_format=target_format)
    result.groups_converted += 1
    total = max(_count_arrays(src_group), 1)
    counter = [0]
    _copy_group(
        src_group,
        dest_group,
        target_format,
        overwrite=True,
        result=result,
        progress=progress,
        total=total,
        counter=counter,
    )
    return result


def default_dest(
    source: str | Path,
    out_dir: str | Path,
    target_format: ZarrFormat,
    suffix: str = "_v{fmt}",
) -> Path:
    stem = Path(source).name
    if stem.endswith(".zarr"):
        stem = stem[: -len(".zarr")]
    return Path(out_dir) / f"{stem}{suffix.format(fmt=target_format)}.zarr"


def bulk_convert(
    sources: list[str | Path],
    out_dir: str | Path,
    target_format: ZarrFormat = 3,
    overwrite: bool = False,
    suffix: str = "_v{fmt}",
    progress: ProgressFn | None = None,
) -> list[ConvertResult]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[ConvertResult] = []
    for src in sources:
        src_path = Path(src)
        dest = default_dest(src_path, out_dir, target_format, suffix)
        try:
            results.append(
                convert_store(
                    src_path, dest, target_format, overwrite=overwrite, progress=progress
                )
            )
        except Exception as exc:  # noqa: BLE001
            r = ConvertResult(
                source=str(src_path), dest=str(dest), target_format=target_format
            )
            r.errors.append(str(exc))
            results.append(r)
    return results
