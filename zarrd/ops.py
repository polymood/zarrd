from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

import numpy as np
import zarr
from zarr import Array, Group

OpKind = Literal[
    "add_group",
    "add_array",
    "set_attrs",
    "replace_attrs",
    "del_attr_keys",
    "delete",
    "rename",
]
LogFn = Callable[[str], None]

DTYPES = [
    "int8", "int16", "int32", "int64",
    "uint8", "uint16", "uint32", "uint64",
    "float16", "float32", "float64",
    "bool", "complex64", "complex128",
]
INITS = ["zeros", "ones", "arange", "random"]


class EditError(RuntimeError):
    pass


@dataclass
class EditOp:
    kind: OpKind
    path: str = "/"
    name: str = ""
    dtype: str = "float64"
    shape: tuple[int, ...] = ()
    chunks: tuple[int, ...] | None = None
    fill: str = "0"
    init: str = "zeros"
    attrs: dict[str, Any] = field(default_factory=dict)
    keys: list[str] = field(default_factory=list)

    def describe(self) -> str:
        p = self.path or "/"
        if self.kind == "add_group":
            return f"add group '{self.name}' under {p}"
        if self.kind == "add_array":
            return (
                f"add array '{self.name}' under {p} "
                f"[{self.dtype} {self.shape} chunks={self.chunks or 'auto'} init={self.init}]"
            )
        if self.kind == "set_attrs":
            return f"merge attrs into {p}: {sorted(self.attrs)}"
        if self.kind == "replace_attrs":
            return f"replace attrs of {p}: {sorted(self.attrs)}"
        if self.kind == "del_attr_keys":
            return f"delete attr keys from {p}: {self.keys}"
        if self.kind == "delete":
            return f"delete node {p}"
        if self.kind == "rename":
            return f"rename {p} -> '{self.name}'"
        return self.kind


def make_init_data(
    shape: tuple[int, ...], dtype: str, init: str
) -> np.ndarray[Any, Any] | None:
    if init == "zeros":
        return None
    np_dtype = np.dtype(dtype)
    n = int(np.prod(shape)) if shape else 1
    if init == "ones":
        return np.ones(shape, dtype=np_dtype)
    if init == "arange":
        return np.arange(n).reshape(shape).astype(np_dtype)
    if init == "random":
        rng = np.random.default_rng()
        if np_dtype.kind in ("i", "u"):
            return rng.integers(0, 100, size=shape).astype(np_dtype)
        if np_dtype.kind == "b":
            return rng.integers(0, 2, size=shape).astype(bool)
        return rng.standard_normal(shape).astype(np_dtype)
    return None


def _norm(path: str) -> str:
    return path.strip("/").strip()


def _open_root(store_path: str) -> Group:
    node = zarr.open(store=store_path, mode="r+")
    if not isinstance(node, Group):
        raise EditError("store root is an array; structural edits need a group root")
    return node


def _resolve_node(root: Group, path: str) -> Array[Any] | Group:
    key = _norm(path)
    if not key:
        return root
    return root[key]


def _resolve_group(root: Group, path: str) -> Group:
    node = _resolve_node(root, path)
    if not isinstance(node, Group):
        raise EditError(f"{path} is not a group")
    return node


def add_group(store_path: str, parent_path: str, name: str) -> str:
    if not name.strip():
        raise EditError("group name required")
    root = _open_root(store_path)
    parent = _resolve_group(root, parent_path)
    parent.create_group(name.strip(), overwrite=False)
    return _join(parent_path, name.strip())


def add_array(
    store_path: str,
    parent_path: str,
    name: str,
    shape: tuple[int, ...],
    chunks: tuple[int, ...] | None,
    dtype: str,
    fill: str = "0",
    init: str = "zeros",
) -> str:
    if not name.strip():
        raise EditError("array name required")
    root = _open_root(store_path)
    parent = _resolve_group(root, parent_path)
    try:
        fill_value: Any = np.array(fill, dtype=np.dtype(dtype)).item()
    except (ValueError, TypeError):
        fill_value = 0
    arr = parent.create_array(
        name.strip(),
        shape=shape,
        chunks=chunks if chunks else "auto",
        dtype=dtype,
        fill_value=fill_value,
        overwrite=False,
    )
    data = make_init_data(tuple(shape), dtype, init)
    if data is not None:
        arr[...] = data
    return _join(parent_path, name.strip())


def set_attributes(
    store_path: str, path: str, attrs: dict[str, Any], replace: bool = False
) -> None:
    root = _open_root(store_path)
    node = _resolve_node(root, path)
    if replace:
        node.attrs.put(attrs)
    else:
        node.update_attributes(attrs)


def delete_attr_keys(store_path: str, path: str, keys: list[str]) -> None:
    root = _open_root(store_path)
    node = _resolve_node(root, path)
    for key in keys:
        if key in node.attrs:
            del node.attrs[key]


def delete_node(store_path: str, path: str) -> None:
    key = _norm(path)
    if not key:
        raise EditError("cannot delete the store root")
    root = _open_root(store_path)
    del root[key]


def rename_node(store_path: str, path: str, new_name: str) -> str:
    key = _norm(path)
    new_name = new_name.strip()
    if not key:
        raise EditError("cannot rename the store root")
    if not new_name or "/" in new_name:
        raise EditError("new name must be a single path segment")
    base = Path(store_path)
    if not base.is_dir():
        raise EditError("rename is only supported for local directory stores")
    src_dir = base / key
    parent = key.rsplit("/", 1)[0] if "/" in key else ""
    dest_rel = f"{parent}/{new_name}" if parent else new_name
    dest_dir = base / dest_rel
    if not src_dir.is_dir():
        raise EditError(f"node directory not found: {src_dir}")
    if dest_dir.exists():
        raise EditError(f"target already exists: {dest_rel}")
    shutil.move(str(src_dir), str(dest_dir))
    return dest_rel


def apply_op(store_path: str, op: EditOp) -> str:
    if op.kind == "add_group":
        return add_group(store_path, op.path, op.name)
    if op.kind == "add_array":
        return add_array(
            store_path,
            op.path,
            op.name,
            op.shape,
            op.chunks,
            op.dtype,
            op.fill,
            op.init,
        )
    if op.kind == "set_attrs":
        set_attributes(store_path, op.path, op.attrs, replace=False)
        return op.path
    if op.kind == "replace_attrs":
        set_attributes(store_path, op.path, op.attrs, replace=True)
        return op.path
    if op.kind == "del_attr_keys":
        delete_attr_keys(store_path, op.path, op.keys)
        return op.path
    if op.kind == "delete":
        delete_node(store_path, op.path)
        return op.path
    if op.kind == "rename":
        return rename_node(store_path, op.path, op.name)
    raise EditError(f"unknown op kind: {op.kind}")


def copy_store(src: str | Path, dst: str | Path, overwrite: bool = False) -> str:
    src_p = Path(src)
    dst_p = Path(dst)
    if not src_p.exists():
        raise EditError(f"source not found: {src_p}")
    if dst_p.exists():
        if not overwrite:
            raise EditError(f"destination exists: {dst_p}")
        if dst_p.is_dir():
            shutil.rmtree(dst_p)
        else:
            dst_p.unlink()
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    if src_p.is_dir():
        shutil.copytree(src_p, dst_p)
    else:
        shutil.copy2(src_p, dst_p)
    return str(dst_p)


@dataclass
class StoreOpResult:
    store: str
    source: str = ""
    applied: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def run_bulk(
    store_paths: list[str],
    ops: list[EditOp],
    log: LogFn | None = None,
    stop: Callable[[], bool] | None = None,
    copy_to: str | None = None,
    overwrite: bool = False,
) -> list[StoreOpResult]:
    out_dir = Path(copy_to) if copy_to else None
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
    results: list[StoreOpResult] = []
    for si, store_path in enumerate(store_paths, start=1):
        if stop is not None and stop():
            break
        target = store_path
        if log is not None:
            log(f"[{si}/{len(store_paths)}] {store_path}")
        if out_dir is not None:
            dest = out_dir / Path(store_path).name
            try:
                target = copy_store(store_path, dest, overwrite=overwrite)
                if log is not None:
                    log(f"        copied to {dest}")
            except Exception as exc:  # noqa: BLE001
                res = StoreOpResult(store=str(dest), source=store_path)
                res.errors.append(f"copy failed: {exc}")
                if log is not None:
                    log(f"        ERROR: copy failed: {exc}")
                results.append(res)
                continue
        res = StoreOpResult(store=target, source=store_path)
        for op in ops:
            try:
                apply_op(target, op)
                res.applied += 1
                if log is not None:
                    log(f"        ok: {op.describe()}")
            except Exception as exc:  # noqa: BLE001
                msg = f"{op.describe()}: {exc}"
                res.errors.append(msg)
                if log is not None:
                    log(f"        ERROR: {msg}")
        results.append(res)
    return results


def _join(parent: str, name: str) -> str:
    parent = _norm(parent)
    return f"/{parent}/{name}" if parent else f"/{name}"


def is_store(path: str | Path) -> bool:
    p = Path(path)
    return (
        (p / "zarr.json").exists()
        or (p / ".zgroup").exists()
        or (p / ".zarray").exists()
    )


def resolve_stores(patterns: list[str]) -> list[str]:
    out: list[str] = []
    for pattern in patterns:
        p = Path(pattern)
        if any(ch in pattern for ch in "*?["):
            out.extend(str(c) for c in sorted(Path().glob(pattern)))
        elif p.is_dir() and not is_store(p):
            out.extend(
                str(c) for c in sorted(p.iterdir()) if c.is_dir() and is_store(c)
            )
        else:
            out.append(str(p))
    seen: set[str] = set()
    unique: list[str] = []
    for s in out:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique
