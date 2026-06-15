from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from zarrd.gui.dialogs import parse_ints
from zarrd.ops import DTYPES, INITS, EditOp, OpKind

OP_LABELS: list[tuple[str, OpKind]] = [
    ("Add group", "add_group"),
    ("Add array", "add_array"),
    ("Merge attributes", "set_attrs"),
    ("Replace attributes", "replace_attrs"),
    ("Delete attribute keys", "del_attr_keys"),
    ("Delete node", "delete"),
    ("Rename node", "rename"),
]


class OpDialog(QDialog):
    def __init__(self, op: EditOp | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Operation")
        self.setMinimumWidth(460)
        self._error = QLabel("")
        self._error.setStyleSheet("color: #b42318;")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._kind = QComboBox()
        for label, _kind in OP_LABELS:
            self._kind.addItem(label)
        self._kind.currentIndexChanged.connect(self._sync_visibility)
        form.addRow("Operation:", self._kind)

        self._path = QLineEdit("/")
        form.addRow("Target path:", self._path)
        self._path_hint = QLabel("parent group for add; node itself otherwise")
        self._path_hint.setStyleSheet("color: #6b7280;")
        form.addRow("", self._path_hint)

        self._name = QLineEdit()
        self._name_row = self._labelled(form, "Name:", self._name)

        self._shape = QLineEdit("100, 100")
        self._shape_row = self._labelled(form, "Shape:", self._shape)
        self._chunks = QLineEdit("")
        self._chunks_row = self._labelled(form, "Chunks (blank=auto):", self._chunks)
        self._dtype = QComboBox()
        self._dtype.addItems(DTYPES)
        self._dtype.setCurrentText("float64")
        self._dtype_row = self._labelled(form, "Dtype:", self._dtype)
        self._fill = QLineEdit("0")
        self._fill_row = self._labelled(form, "Fill value:", self._fill)
        self._init = QComboBox()
        self._init.addItems(INITS)
        self._init_row = self._labelled(form, "Initialize:", self._init)

        self._attrs = QPlainTextEdit()
        self._attrs.setPlaceholderText('{\n  "key": "value"\n}')
        self._attrs.setMaximumHeight(140)
        self._attrs_row = self._labelled(form, "Attributes (JSON):", self._attrs)

        self._keys = QLineEdit()
        self._keys.setPlaceholderText("comma-separated keys")
        self._keys_row = self._labelled(form, "Keys to delete:", self._keys)

        layout.addLayout(form)
        layout.addWidget(self._error)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if op is not None:
            self._load(op)
        self._sync_visibility()

    def _labelled(
        self, form: QFormLayout, label: str, field: QWidget
    ) -> tuple[QLabel, QWidget]:
        lab = QLabel(label)
        form.addRow(lab, field)
        return lab, field

    def _current_kind(self) -> OpKind:
        return OP_LABELS[self._kind.currentIndex()][1]

    def _sync_visibility(self) -> None:
        kind = self._current_kind()
        show_name = kind in ("add_group", "add_array", "rename")
        show_array = kind == "add_array"
        show_attrs = kind in ("set_attrs", "replace_attrs")
        show_keys = kind == "del_attr_keys"
        self._set_row(self._name_row, show_name)
        for row in (
            self._shape_row,
            self._chunks_row,
            self._dtype_row,
            self._fill_row,
            self._init_row,
        ):
            self._set_row(row, show_array)
        self._set_row(self._attrs_row, show_attrs)
        self._set_row(self._keys_row, show_keys)
        if kind in ("add_group", "add_array"):
            self._path_hint.setText("parent group that will contain the new node")
        elif kind == "rename":
            self._path_hint.setText("path of the node to rename")
        else:
            self._path_hint.setText("path of the target node ('/' for root)")

    def _set_row(self, row: tuple[QLabel, QWidget], visible: bool) -> None:
        row[0].setVisible(visible)
        row[1].setVisible(visible)

    def _load(self, op: EditOp) -> None:
        for i, (_label, kind) in enumerate(OP_LABELS):
            if kind == op.kind:
                self._kind.setCurrentIndex(i)
                break
        self._path.setText(op.path or "/")
        self._name.setText(op.name)
        if op.shape:
            self._shape.setText(", ".join(str(s) for s in op.shape))
        if op.chunks:
            self._chunks.setText(", ".join(str(c) for c in op.chunks))
        self._dtype.setCurrentText(op.dtype)
        self._fill.setText(op.fill)
        self._init.setCurrentText(op.init)
        if op.attrs:
            self._attrs.setPlainText(json.dumps(op.attrs, indent=2))
        if op.keys:
            self._keys.setText(", ".join(op.keys))

    def _accept(self) -> None:
        try:
            self._op = self._build()
        except ValueError as exc:
            self._error.setText(str(exc))
            return
        self.accept()

    def _build(self) -> EditOp:
        kind = self._current_kind()
        path = self._path.text().strip() or "/"
        op = EditOp(kind=kind, path=path)
        if kind in ("add_group", "add_array", "rename"):
            op.name = self._name.text().strip()
            if not op.name:
                raise ValueError("name is required")
        if kind == "add_array":
            op.shape = parse_ints(self._shape.text())
            chunk_text = self._chunks.text().strip()
            op.chunks = parse_ints(chunk_text) if chunk_text else None
            op.dtype = self._dtype.currentText()
            op.fill = self._fill.text().strip() or "0"
            op.init = self._init.currentText()
        if kind in ("set_attrs", "replace_attrs"):
            text = self._attrs.toPlainText().strip() or "{}"
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON: {exc.msg}") from exc
            if not isinstance(parsed, dict):
                raise ValueError("attributes must be a JSON object")
            op.attrs = parsed
        if kind == "del_attr_keys":
            op.keys = [k.strip() for k in self._keys.text().split(",") if k.strip()]
            if not op.keys:
                raise ValueError("at least one key is required")
        return op

    def op(self) -> EditOp:
        return self._op
