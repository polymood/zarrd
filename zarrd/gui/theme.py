from __future__ import annotations

FONT_STACK = '"Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'

LIGHT_QSS = f"""
QWidget {{
    background-color: #f7f7f8;
    color: #1f2329;
    font-family: {FONT_STACK};
    font-size: 13px;
    selection-background-color: #cfe2ff;
    selection-color: #11151c;
}}
QMainWindow, QDialog {{
    background-color: #f1f1f3;
}}
QMenuBar, QMenu {{
    background-color: #ffffff;
    color: #1f2329;
}}
QMenuBar::item:selected, QMenu::item:selected {{
    background-color: #e4ecff;
}}
QToolBar {{
    background-color: #ffffff;
    border-bottom: 1px solid #d9dadf;
    spacing: 4px;
    padding: 3px;
}}
QSplitter::handle {{
    background-color: #d9dadf;
}}
QTreeView, QTableView, QListView, QPlainTextEdit, QTextEdit, QLineEdit {{
    background-color: #ffffff;
    border: 1px solid #d9dadf;
    border-radius: 4px;
}}
QTreeView::item:selected, QTableView::item:selected, QListView::item:selected {{
    background-color: #cfe2ff;
    color: #11151c;
}}
QHeaderView::section {{
    background-color: #eef0f3;
    color: #3a3f47;
    border: none;
    border-right: 1px solid #d9dadf;
    border-bottom: 1px solid #d9dadf;
    padding: 4px 6px;
}}
QTabWidget::pane {{
    border: 1px solid #d9dadf;
    border-radius: 4px;
    background-color: #ffffff;
}}
QTabBar::tab {{
    background-color: #e9eaee;
    color: #3a3f47;
    padding: 6px 14px;
    border: 1px solid #d9dadf;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{
    background-color: #ffffff;
    color: #11151c;
}}
QPushButton {{
    background-color: #ffffff;
    border: 1px solid #c6c8cd;
    border-radius: 4px;
    padding: 5px 12px;
}}
QPushButton:hover {{
    background-color: #f0f4ff;
    border-color: #9db8ff;
}}
QPushButton:pressed {{
    background-color: #e2ebff;
}}
QPushButton:disabled {{
    color: #9aa0a6;
    background-color: #f3f3f5;
}}
QPushButton#primary {{
    background-color: #2563eb;
    color: #ffffff;
    border-color: #1d4ed8;
}}
QPushButton#primary:hover {{
    background-color: #1d4ed8;
}}
QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: #ffffff;
    border: 1px solid #c6c8cd;
    border-radius: 4px;
    padding: 3px 6px;
}}
QComboBox QAbstractItemView {{
    background-color: #ffffff;
    selection-background-color: #cfe2ff;
}}
QGroupBox {{
    border: 1px solid #d9dadf;
    border-radius: 4px;
    margin-top: 10px;
    background-color: #fbfbfc;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    padding: 0 4px;
    color: #3a3f47;
}}
QStatusBar {{
    background-color: #ffffff;
    border-top: 1px solid #d9dadf;
}}
QStatusBar QLabel {{
    padding: 0 6px;
}}
QProgressBar {{
    border: 1px solid #c6c8cd;
    border-radius: 4px;
    text-align: center;
    background-color: #ffffff;
}}
QProgressBar::chunk {{
    background-color: #2563eb;
    border-radius: 3px;
}}
"""

DARK_QSS = f"""
QWidget {{
    background-color: #1e1f22;
    color: #d6d7da;
    font-family: {FONT_STACK};
    font-size: 13px;
    selection-background-color: #2f4b73;
    selection-color: #f2f4f8;
}}
QMainWindow, QDialog {{
    background-color: #1a1b1e;
}}
QMenuBar, QMenu {{
    background-color: #26282c;
    color: #d6d7da;
}}
QMenuBar::item:selected, QMenu::item:selected {{
    background-color: #2f4b73;
}}
QToolBar {{
    background-color: #26282c;
    border-bottom: 1px solid #3a3d41;
    spacing: 4px;
    padding: 3px;
}}
QToolButton {{
    color: #d6d7da;
    padding: 4px 8px;
    border-radius: 4px;
}}
QToolButton:hover {{
    background-color: #33363b;
}}
QSplitter::handle {{
    background-color: #3a3d41;
}}
QTreeView, QTableView, QListView, QPlainTextEdit, QTextEdit, QLineEdit {{
    background-color: #232427;
    color: #d6d7da;
    border: 1px solid #3a3d41;
    border-radius: 4px;
}}
QTreeView::item:selected, QTableView::item:selected, QListView::item:selected {{
    background-color: #2f4b73;
    color: #f2f4f8;
}}
QTableView {{
    gridline-color: #34373c;
    alternate-background-color: #26282c;
}}
QHeaderView::section {{
    background-color: #2b2d31;
    color: #b6b8bd;
    border: none;
    border-right: 1px solid #3a3d41;
    border-bottom: 1px solid #3a3d41;
    padding: 4px 6px;
}}
QTabWidget::pane {{
    border: 1px solid #3a3d41;
    border-radius: 4px;
    background-color: #232427;
}}
QTabBar::tab {{
    background-color: #26282c;
    color: #9a9da3;
    padding: 6px 14px;
    border: 1px solid #3a3d41;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{
    background-color: #232427;
    color: #f2f4f8;
}}
QPushButton {{
    background-color: #2d2f33;
    color: #d6d7da;
    border: 1px solid #45484d;
    border-radius: 4px;
    padding: 5px 12px;
}}
QPushButton:hover {{
    background-color: #36393e;
    border-color: #5a6470;
}}
QPushButton:pressed {{
    background-color: #2a2c30;
}}
QPushButton:disabled {{
    color: #6b6e74;
    background-color: #26282c;
    border-color: #34373c;
}}
QPushButton#primary {{
    background-color: #3b82f6;
    color: #ffffff;
    border-color: #2f6fe0;
}}
QPushButton#primary:hover {{
    background-color: #2f6fe0;
}}
QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: #2d2f33;
    color: #d6d7da;
    border: 1px solid #45484d;
    border-radius: 4px;
    padding: 3px 6px;
}}
QComboBox QAbstractItemView {{
    background-color: #2d2f33;
    color: #d6d7da;
    selection-background-color: #2f4b73;
}}
QGroupBox {{
    border: 1px solid #3a3d41;
    border-radius: 4px;
    margin-top: 10px;
    background-color: #212327;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    padding: 0 4px;
    color: #b6b8bd;
}}
QStatusBar {{
    background-color: #26282c;
    border-top: 1px solid #3a3d41;
}}
QStatusBar QLabel {{
    padding: 0 6px;
}}
QProgressBar {{
    border: 1px solid #45484d;
    border-radius: 4px;
    text-align: center;
    background-color: #232427;
    color: #d6d7da;
}}
QProgressBar::chunk {{
    background-color: #3b82f6;
    border-radius: 3px;
}}
QRadioButton, QCheckBox {{
    color: #d6d7da;
}}
"""

THEMES = {"dark": DARK_QSS, "light": LIGHT_QSS}
DEFAULT_THEME = "dark"
