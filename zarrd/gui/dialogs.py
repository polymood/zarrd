from __future__ import annotations

from typing import Literal

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from zarrd.convert import ConvertResult, convert_store
from zarrd.ops import DTYPES, INITS, make_init_data

__all__ = [
    "ConvertDialog",
    "NewArrayDialog",
    "NewStoreDialog",
    "make_init_data",
    "parse_ints",
    "DTYPES",
    "INITS",
]


def parse_ints(text: str) -> tuple[int, ...]:
    parts = [p.strip() for p in text.replace("x", ",").split(",") if p.strip()]
    return tuple(int(p) for p in parts)


_parse_ints = parse_ints


class NewStoreDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New store")
        self.path = ""
        self.zarr_format: Literal[2, 3] = 3

        form = QFormLayout(self)
        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit, 1)
        path_row.addWidget(browse)
        form.addRow("Path:", _wrap(path_row))

        self._fmt = QComboBox()
        self._fmt.addItems(["zarr v3", "zarr v2"])
        form.addRow("Format:", self._fmt)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "New store", "new.zarr")
        if path:
            self._path_edit.setText(path)

    def _accept(self) -> None:
        self.path = self._path_edit.text().strip()
        self.zarr_format = 3 if self._fmt.currentIndex() == 0 else 2
        if self.path:
            self.accept()


class NewArrayDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New array")

        form = QFormLayout(self)
        self._name = QLineEdit("array")
        self._shape = QLineEdit("100, 100")
        self._chunks = QLineEdit("50, 50")
        self._dtype = QComboBox()
        self._dtype.addItems(DTYPES)
        self._dtype.setCurrentText("float64")
        self._fill = QLineEdit("0")
        self._init = QComboBox()
        self._init.addItems(INITS)
        form.addRow("Name:", self._name)
        form.addRow("Shape:", self._shape)
        form.addRow("Chunks:", self._chunks)
        form.addRow("Dtype:", self._dtype)
        form.addRow("Fill value:", self._fill)
        form.addRow("Initialize:", self._init)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict[str, object]:
        return {
            "name": self._name.text().strip(),
            "shape": _parse_ints(self._shape.text()),
            "chunks": _parse_ints(self._chunks.text()),
            "dtype": self._dtype.currentText(),
            "fill": self._fill.text().strip(),
            "init": self._init.currentText(),
        }


class _ConvertWorker(QThread):
    progress = Signal(str, int, int)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        source: str,
        dest: str,
        target_format: Literal[2, 3],
        overwrite: bool,
    ) -> None:
        super().__init__()
        self._source = source
        self._dest = dest
        self._target_format = target_format
        self._overwrite = overwrite

    def run(self) -> None:
        try:
            result = convert_store(
                self._source,
                self._dest,
                target_format=self._target_format,
                overwrite=self._overwrite,
                progress=lambda p, d, t: self.progress.emit(p, d, t),
            )
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class ConvertDialog(QDialog):
    def __init__(self, source: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Convert store")
        self.resize(520, 360)
        self._worker: _ConvertWorker | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        src_row = QHBoxLayout()
        self._src = QLineEdit(source)
        src_browse = QPushButton("...")
        src_browse.clicked.connect(self._browse_src)
        src_row.addWidget(self._src, 1)
        src_row.addWidget(src_browse)
        form.addRow("Source:", _wrap(src_row))

        dst_row = QHBoxLayout()
        self._dst = QLineEdit()
        dst_browse = QPushButton("...")
        dst_browse.clicked.connect(self._browse_dst)
        dst_row.addWidget(self._dst, 1)
        dst_row.addWidget(dst_browse)
        form.addRow("Destination:", _wrap(dst_row))

        self._fmt = QComboBox()
        self._fmt.addItems(["zarr v3", "zarr v2"])
        form.addRow("Target format:", self._fmt)

        self._overwrite = QComboBox()
        self._overwrite.addItems(["no", "yes"])
        form.addRow("Overwrite:", self._overwrite)
        layout.addLayout(form)

        self._progress = QProgressBar()
        self._progress.setValue(0)
        layout.addWidget(self._progress)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        layout.addWidget(self._log, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._run_btn = QPushButton("Convert")
        self._run_btn.setObjectName("primary")
        self._run_btn.clicked.connect(self._run)
        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._run_btn)
        btn_row.addWidget(self._close_btn)
        layout.addLayout(btn_row)

    def _browse_src(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Source store")
        if path:
            self._src.setText(path)

    def _browse_dst(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Destination store", "out.zarr")
        if path:
            self._dst.setText(path)

    def _run(self) -> None:
        source = self._src.text().strip()
        dest = self._dst.text().strip()
        if not source or not dest:
            self._log.appendPlainText("source and destination required")
            return
        target: Literal[2, 3] = 3 if self._fmt.currentIndex() == 0 else 2
        overwrite = self._overwrite.currentIndex() == 1
        self._run_btn.setEnabled(False)
        self._progress.setValue(0)
        self._log.appendPlainText(f"converting {source} -> {dest} (v{target})")
        self._worker = _ConvertWorker(source, dest, target, overwrite)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, path: str, done: int, total: int) -> None:
        self._progress.setMaximum(total)
        self._progress.setValue(done)
        self._log.appendPlainText(f"[{done}/{total}] {path}")

    def _on_done(self, result: ConvertResult) -> None:
        self._run_btn.setEnabled(True)
        status = "OK" if result.ok else "completed with errors"
        self._log.appendPlainText(
            f"{status}: arrays={result.arrays_converted} "
            f"groups={result.groups_converted} bytes={result.bytes_copied}"
        )
        for err in result.errors:
            self._log.appendPlainText(f"error: {err}")

    def _on_failed(self, message: str) -> None:
        self._run_btn.setEnabled(True)
        self._log.appendPlainText(f"failed: {message}")


def _wrap(layout: QHBoxLayout) -> QWidget:
    w = QWidget()
    w.setLayout(layout)
    return w
