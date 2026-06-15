from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Literal, Union

import numpy as np
import zarr
from zarr import Array, Group

ZarrFormat = Literal[2, 3]
OpenMode = Literal["r", "r+", "a", "w", "w-"]
Node = Union[Array[Any], Group]


@dataclass(frozen=True)
class ArrayInfo:
    path: str
    name: str
    shape: tuple[int, ...]
    chunks: tuple[int, ...]
    dtype: str
    zarr_format: int
    order: str
    fill_value: Any
    nbytes: int
    compressors: tuple[str, ...]
    filters: tuple[str, ...]
    dimension_names: tuple[str | None, ...] | None
    ndim: int


@dataclass(frozen=True)
class GroupInfo:
    path: str
    name: str
    zarr_format: int
    n_members: int


@dataclass
class NodeInfo:
    path: str
    name: str
    kind: Literal["array", "group"]
    zarr_format: int
    attrs: dict[str, Any]
    array: ArrayInfo | None = None
    group: GroupInfo | None = None
    children: list[NodeInfo] = field(default_factory=list)


def detect_format(path: str | Path) -> ZarrFormat | None:
    p = Path(path)
    if (p / "zarr.json").exists():
        return 3
    if (p / ".zgroup").exists() or (p / ".zarray").exists():
        return 2
    try:
        node = open_node(str(p), mode="r")
    except Exception:
        return None
    fmt = int(node.metadata.zarr_format)
    return 3 if fmt == 3 else 2


def open_node(path: str | Path, mode: OpenMode = "r") -> Node:
    return zarr.open(store=str(path), mode=mode)


def open_group(path: str | Path, mode: OpenMode = "r") -> Group:
    node = zarr.open(store=str(path), mode=mode)
    if not isinstance(node, Group):
        raise TypeError(f"{path} is not a zarr group")
    return node


def _codec_names(codecs: Any) -> tuple[str, ...]:
    if codecs is None:
        return ()
    if not isinstance(codecs, (tuple, list)):
        codecs = (codecs,)
    out: list[str] = []
    for c in codecs:
        if c is None:
            continue
        name = getattr(c, "codec_name", None) or getattr(c, "codec_id", None)
        out.append(str(name) if name else type(c).__name__)
    return tuple(out)


def array_info(arr: Array[Any], path: str) -> ArrayInfo:
    name = path.rstrip("/").rsplit("/", 1)[-1] or "/"
    dim_names: tuple[str | None, ...] | None = None
    raw_dims = getattr(arr.metadata, "dimension_names", None)
    if raw_dims is not None:
        dim_names = tuple(raw_dims)
    return ArrayInfo(
        path=path,
        name=name,
        shape=tuple(int(s) for s in arr.shape),
        chunks=tuple(int(c) for c in arr.chunks),
        dtype=str(arr.dtype),
        zarr_format=int(arr.metadata.zarr_format),
        order=str(getattr(arr, "order", "C")),
        fill_value=_jsonable(arr.fill_value),
        nbytes=int(arr.nbytes),
        compressors=_codec_names(getattr(arr, "compressors", None)),
        filters=_codec_names(getattr(arr, "filters", None)),
        dimension_names=dim_names,
        ndim=int(arr.ndim),
    )


def group_info(grp: Group, path: str) -> GroupInfo:
    name = path.rstrip("/").rsplit("/", 1)[-1] or "/"
    return GroupInfo(
        path=path,
        name=name,
        zarr_format=int(grp.metadata.zarr_format),
        n_members=len(list(grp.keys())),
    )


def node_info(node: Node, path: str = "/") -> NodeInfo:
    attrs = dict(node.attrs)
    if isinstance(node, Array):
        return NodeInfo(
            path=path,
            name=path.rstrip("/").rsplit("/", 1)[-1] or "/",
            kind="array",
            zarr_format=int(node.metadata.zarr_format),
            attrs=attrs,
            array=array_info(node, path),
        )
    return NodeInfo(
        path=path,
        name=path.rstrip("/").rsplit("/", 1)[-1] or "/",
        kind="group",
        zarr_format=int(node.metadata.zarr_format),
        attrs=attrs,
        group=group_info(node, path),
    )


def walk(group: Group, path: str = "/") -> Iterator[tuple[str, Node]]:
    for name, obj in sorted(group.members(), key=lambda kv: kv[0]):
        child_path = (path.rstrip("/") + "/" + name) if path != "/" else "/" + name
        yield child_path, obj
        if isinstance(obj, Group):
            yield from walk(obj, child_path)


def build_tree(group: Group, path: str = "/") -> NodeInfo:
    root = node_info(group, path)
    for name, obj in sorted(group.members(), key=lambda kv: kv[0]):
        child_path = (path.rstrip("/") + "/" + name) if path != "/" else "/" + name
        if isinstance(obj, Group):
            root.children.append(build_tree(obj, child_path))
        else:
            root.children.append(node_info(obj, child_path))
    return root


def read_slice(arr: Array[Any], selection: tuple[Any, ...]) -> np.ndarray[Any, Any]:
    data = arr[selection]
    return np.asarray(data)


def _jsonable(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value
