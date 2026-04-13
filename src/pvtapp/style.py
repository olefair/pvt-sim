"""Application-wide styling for the PVT Simulator GUI.

This module keeps QSS (Qt stylesheet) centralized so the main window can
apply a consistent, Cato-like theme and scalable spacing.
"""

from __future__ import annotations

from typing import Final

MIN_UI_SCALE = 0.8
MAX_UI_SCALE = 1.6
DEFAULT_UI_SCALE = 1.10
UI_SCALE_STEP = 0.10

THEME_DARK: Final[str] = "dark"
THEME_SLATE: Final[str] = "slate"
DEFAULT_THEME: Final[str] = THEME_DARK

_THEME_PALETTES: Final[dict[str, dict[str, str]]] = {
    THEME_DARK: {
        "window_bg": "#0b1220",
        "surface_bg": "#0f1a2b",
        "surface_alt_bg": "#0c1524",
        "surface_elevated_bg": "#121f34",
        "surface_hover_bg": "#162844",
        "surface_pressed_bg": "#1b3356",
        "surface_disabled_bg": "#0c1524",
        "border": "#223044",
        "border_soft": "#1f2a3a",
        "text": "#e5e7eb",
        "text_muted": "#9ca3af",
        "text_disabled": "#64748b",
        "selection_bg": "#2b6cb0",
        "splitter": "#1f2a3a",
        "run_bg": "#1f6f3a",
        "run_border": "#2d8a4a",
        "run_hover_bg": "#248244",
        "cancel_bg": "#7a1f1f",
        "cancel_border": "#a02a2a",
        "cancel_hover_bg": "#8d2424",
    },
    THEME_SLATE: {
        "window_bg": "#141c28",
        "surface_bg": "#1a2433",
        "surface_alt_bg": "#16202d",
        "surface_elevated_bg": "#223043",
        "surface_hover_bg": "#2a3a50",
        "surface_pressed_bg": "#314660",
        "surface_disabled_bg": "#131c28",
        "border": "#36506a",
        "border_soft": "#2d4358",
        "text": "#edf2f7",
        "text_muted": "#b6c2d0",
        "text_disabled": "#8192a5",
        "selection_bg": "#4b88c8",
        "splitter": "#2c4258",
        "run_bg": "#2d8250",
        "run_border": "#38a169",
        "run_hover_bg": "#34955c",
        "cancel_bg": "#8b3232",
        "cancel_border": "#b24a4a",
        "cancel_hover_bg": "#a43e3e",
    },
}


def clamp_ui_scale(scale: float) -> float:
    """Clamp UI scale into the supported desktop range."""
    return max(MIN_UI_SCALE, min(MAX_UI_SCALE, float(scale)))


def scale_metric(value: float, scale: float, *, reference_scale: float = 1.0) -> int:
    """Scale a pixel metric against a reference scale."""
    clamped = clamp_ui_scale(scale)
    return max(1, int(round(value * clamped / reference_scale)))


def get_theme_palette(theme: str = DEFAULT_THEME) -> dict[str, str]:
    """Return the requested UI palette, defaulting to the canonical dark theme."""
    return dict(_THEME_PALETTES.get(theme, _THEME_PALETTES[DEFAULT_THEME]))


def build_cato_stylesheet(*, scale: float = DEFAULT_UI_SCALE, theme: str = DEFAULT_THEME) -> str:
    """Return a QSS theme roughly aligned with the Pete/Cato window.

    Args:
        scale: UI scale factor applied to padding/radii/font sizes.
        theme: Named palette variant.
    """

    def px(value: float) -> int:
        return scale_metric(value, scale)

    palette = get_theme_palette(theme)

    return f"""
/* Base */
QMainWindow {{
  background: {palette['window_bg']};
}}

QWidget {{
  background: {palette['window_bg']};
  color: {palette['text']};
  font-size: {px(12)}px;
}}

QLabel {{
  background: transparent;
}}

QToolTip {{
  background: {palette['surface_bg']};
  color: {palette['text']};
  border: 1px solid {palette['border']};
  padding: {px(6)}px;
}}

/* Menu */
QMenuBar {{
  background: {palette['surface_bg']};
  color: {palette['text']};
}}
QMenuBar::item {{
  padding: {px(6)}px {px(10)}px;
  background: transparent;
}}
QMenuBar::item:selected {{
  background: {palette['surface_hover_bg']};
  border-radius: {px(8)}px;
}}

QMenu {{
  background: {palette['surface_bg']};
  border: 1px solid {palette['border']};
  padding: {px(6)}px;
}}
QMenu::item {{
  padding: {px(6)}px {px(10)}px;
  border-radius: {px(8)}px;
}}
QMenu::item:selected {{
  background: {palette['surface_hover_bg']};
}}
QMenu::separator {{
  height: 1px;
  margin: {px(6)}px {px(2)}px;
  background: {palette['border']};
}}

/* Toolbars / status */
QToolBar {{
  background: {palette['surface_bg']};
  border-bottom: 1px solid {palette['border_soft']};
  spacing: {px(6)}px;
  padding: {px(4)}px;
}}

QStatusBar {{
  background: {palette['surface_bg']};
  border-top: 1px solid {palette['border_soft']};
  color: {palette['text_muted']};
}}

/* Cards */
QFrame#PaneCard {{
  background: {palette['surface_bg']};
  border: 1px solid {palette['border_soft']};
  border-radius: {px(10)}px;
}}

QLabel#PaneTitle {{
  background: transparent;
  color: {palette['text_muted']};
  font-size: {px(10)}px;
}}

/* Inputs */
QLineEdit, QTextEdit, QTextBrowser {{
  background: {palette['surface_bg']};
  border: 1px solid {palette['border']};
  border-radius: {px(6)}px;
  padding: {px(5)}px;
  selection-background-color: {palette['selection_bg']};
}}

QComboBox {{
  background: {palette['surface_elevated_bg']};
  border: 1px solid {palette['border']};
  border-radius: {px(6)}px;
  padding: {px(4)}px {px(7)}px;
}}
QComboBox::drop-down {{
  subcontrol-origin: padding;
  subcontrol-position: top right;
  width: {px(22)}px;
  border: none;
  background: transparent;
  border-top-right-radius: {px(6)}px;
  border-bottom-right-radius: {px(6)}px;
}}
QComboBox:hover {{
  background: {palette['surface_hover_bg']};
}}
QComboBox:disabled {{
  color: {palette['text_disabled']};
  background: {palette['surface_disabled_bg']};
}}
QComboBox QAbstractItemView {{
  background: {palette['surface_bg']};
  border: 1px solid {palette['border']};
  selection-background-color: {palette['surface_hover_bg']};
  color: {palette['text']};
}}

/* Buttons */
QPushButton, QToolButton {{
  background: {palette['surface_elevated_bg']};
  border: 1px solid {palette['border']};
  border-radius: {px(8)}px;
  padding: {px(4)}px {px(8)}px;
}}
QPushButton:hover, QToolButton:hover {{
  background: {palette['surface_hover_bg']};
}}
QPushButton:pressed, QToolButton:pressed {{
  background: {palette['surface_pressed_bg']};
}}
QPushButton:checked, QToolButton:checked {{
  background: {palette['surface_hover_bg']};
  border-color: {palette['selection_bg']};
}}
QPushButton:disabled, QToolButton:disabled {{
  color: {palette['text_disabled']};
  background: {palette['surface_disabled_bg']};
}}

QPushButton#RunButton {{
  background: {palette['run_bg']};
  border: 1px solid {palette['run_border']};
}}
QPushButton#RunButton:hover {{
  background: {palette['run_hover_bg']};
}}

QPushButton#CancelButton {{
  background: {palette['cancel_bg']};
  border: 1px solid {palette['cancel_border']};
}}
QPushButton#CancelButton:hover {{
  background: {palette['cancel_hover_bg']};
}}

/* Group boxes */
QGroupBox {{
  background: transparent;
  border: none;
  margin-top: {px(8)}px;
  padding: {px(4)}px 0 0 0;
}}
QGroupBox::title {{
  subcontrol-origin: margin;
  left: 0px;
  padding: 0 {px(3)}px 0 0;
}}
QGroupBox#ResultsSection {{
  background: transparent;
  border: none;
  margin-top: {px(10)}px;
  padding: 0;
}}
QGroupBox#ResultsSection::title {{
  subcontrol-origin: margin;
  left: 0px;
  padding: 0 {px(3)}px {px(4)}px 0;
}}

/* Tables */
QTableWidget {{
  background: {palette['surface_bg']};
  alternate-background-color: {palette['surface_alt_bg']};
  gridline-color: {palette['border']};
  border: 1px solid {palette['border']};
  border-radius: {px(10)}px;
}}
QTableWidget#ResultsSectionTable {{
  border-radius: 0px;
}}
QHeaderView::section {{
  background: {palette['surface_elevated_bg']};
  color: {palette['text']};
  padding: {px(5)}px;
  border: 1px solid {palette['border']};
}}

/* Tabs */
QTabWidget::pane {{
  border: 1px solid {palette['border']};
  border-radius: {px(6)}px;
}}
QTabWidget#HeavyFractionTabs::pane {{
  border: none;
  background: transparent;
  margin-top: 0px;
}}
QTabBar::tab {{
  background: {palette['surface_elevated_bg']};
  padding: {px(5)}px {px(8)}px;
  border-top-left-radius: {px(6)}px;
  border-top-right-radius: {px(6)}px;
  margin-right: {px(2)}px;
}}
QTabBar::tab:selected {{
  background: {palette['surface_hover_bg']};
}}

/* Splitters */
QSplitter::handle {{
  background: {palette['splitter']};
}}
"""


def build_cato_dark_stylesheet(*, scale: float = DEFAULT_UI_SCALE) -> str:
    """Backward-compatible wrapper for the canonical dark palette."""
    return build_cato_stylesheet(scale=scale, theme=THEME_DARK)
