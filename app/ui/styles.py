from __future__ import annotations

from app.core.config import AppConfig
from app.utils.helpers import resource_path


def application_stylesheet() -> str:
    check_icon = resource_path("assets/check-white.svg").as_posix()
    spin_up_icon = resource_path("assets/spin-up.svg").as_posix()
    spin_down_icon = resource_path("assets/spin-down.svg").as_posix()
    stylesheet = """
    QWidget { background: #18181b; color: #f4f4f5; font-family: 'Segoe UI'; }
    QLineEdit, QSpinBox, QComboBox, QListWidget, QTabWidget::pane {
        background: #27272a; border: 1px solid #3f3f46; border-radius: 5px; padding: 6px;
    }
    QSpinBox { padding-right: 34px; }
    QSpinBox::up-button, QSpinBox::down-button {
        subcontrol-origin: border;
        width: 28px;
        background-color: #3f3f46;
        border-left: 1px solid #52525b;
    }
    QSpinBox::up-button {
        subcontrol-position: top right;
        border-top-right-radius: 5px;
        border-bottom: 1px solid #52525b;
    }
    QSpinBox::down-button {
        subcontrol-position: bottom right;
        border-bottom-right-radius: 5px;
    }
    QSpinBox::up-button:hover, QSpinBox::down-button:hover { background-color: #7c3aed; }
    QSpinBox::up-button:pressed, QSpinBox::down-button:pressed { background-color: #6d28d9; }
    QSpinBox::up-arrow { image: url("__SPIN_UP_ICON__"); width: 10px; height: 6px; }
    QSpinBox::down-arrow { image: url("__SPIN_DOWN_ICON__"); width: 10px; height: 6px; }
    QPushButton { background: #7c3aed; border: 0; border-radius: 5px; padding: 7px 13px; font-weight: 600; }
    QPushButton:hover { background: #8b5cf6; }
    QPushButton:disabled { background: #3f3f46; color: #a1a1aa; }
    QTabBar::tab { padding: 8px 14px; background: #27272a; font-weight: 700; }
    QTabBar::tab:selected { background: #7c3aed; font-weight: 800; }
    QGroupBox { border: 1px solid #3f3f46; border-radius: 6px; margin-top: 12px; padding-top: 10px; }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
    QCheckBox { spacing: 9px; background: transparent; }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border: 1px solid #71717a;
        border-radius: 5px;
        background-color: #27272a;
    }
    QCheckBox::indicator:unchecked:hover {
        border: 1px solid #a78bfa;
        background-color: #3f3f46;
    }
    QCheckBox::indicator:checked {
        border: 1px solid #8b5cf6;
        background-color: #7c3aed;
        image: url("__CHECK_ICON__");
    }
    QCheckBox::indicator:checked:hover {
        border: 1px solid #c4b5fd;
        background-color: #8b5cf6;
    }
    QCheckBox::indicator:disabled {
        border-color: #52525b;
        background-color: #3f3f46;
    }
    QToolTip {
        background-color: #27272a;
        color: #f4f4f5;
        border: 1px solid #8b5cf6;
        border-radius: 5px;
        padding: 7px;
    }
    """
    return (
        stylesheet
        .replace("__CHECK_ICON__", check_icon)
        .replace("__SPIN_UP_ICON__", spin_up_icon)
        .replace("__SPIN_DOWN_ICON__", spin_down_icon)
    )


def message_style(config: AppConfig, platform_color: str) -> str:
    alpha = max(0, min(100, config.background_opacity)) / 100
    return f"""
    QFrame#messageCard {{
        background-color: rgba(18, 18, 22, {alpha:.2f});
        border: none;
        border-radius: 7px;
    }}
    QLabel {{ background: transparent; color: {config.text_color}; }}
    """
