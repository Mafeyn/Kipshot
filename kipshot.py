# -*- coding: utf-8 -*-
"""
Kipshot — современный менеджер буфера обмена для Windows.

Возможности:
  • история всего, что копируется (текст, ссылки, цвета, картинки, файлы)
  • предпросмотр выбранного элемента
  • закрепление важного (не удаляется при очистке истории)
  • «Мои заметки» — свои шаблоны/тексты для быстрой вставки
  • папки для сортировки элементов
  • быстрая панель по горячей клавише (по умолчанию Ctrl+Alt+V) со вставкой в активное окно
  • значок в трее, автозапуск, пауза записи
"""
import sys
import os
import re
import time
import sqlite3
import hashlib
import datetime
import ctypes
import shutil
import json
import math
import subprocess
import asyncio
import threading

from PySide6.QtCore import (Qt, QTimer, QSize, QRect, QRectF, QPoint, QPointF, QBuffer, QIODevice, QUrl,
                            QMimeData, QStandardPaths, QByteArray, QPropertyAnimation, QVariantAnimation,
                            QEasingCurve,
                            Signal, QObject, QEvent, QAbstractNativeEventFilter)
from PySide6.QtGui import (QGuiApplication, QImage, QPixmap, QIcon, QPainter, QColor, QFont, QAction,
                           QCursor, QDesktopServices, QKeySequence, QShortcut, QPainterPath,
                           QFontMetrics, QPen, QPolygonF, QPainterPathStroker, QFontDatabase,
                           QLinearGradient)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QApplication, QWidget, QMainWindow, QListWidget, QListWidgetItem,
                               QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QToolButton, QLabel,
                               QPlainTextEdit, QStackedWidget, QSplitter, QStyledItemDelegate, QStyle,
                               QMenu, QSystemTrayIcon, QFrame, QInputDialog, QMessageBox, QDialog,
                               QComboBox, QSpinBox, QCheckBox, QFormLayout, QDialogButtonBox,
                               QFileDialog, QAbstractItemView, QButtonGroup, QGraphicsDropShadowEffect,
                               QGraphicsOpacityEffect)
from PySide6.QtNetwork import (QLocalServer, QLocalSocket, QNetworkAccessManager, QNetworkRequest,
                               QHttpMultiPart, QHttpPart)

APP = "Kipshot"
OLD_APP = "ClipNest"  # прежнее название: оттуда забираем историю и автозапуск
APP_VERSION = "1.2.0"
IS_WIN = sys.platform == "win32"

# ───────────────────────────── Цвета и стиль ─────────────────────────────
BG = "#0d0e12"
PANEL = "#111217"
CARD = "#17181e"
CARD_HOVER = "#1e1f27"
CARD_SEL = "#24204a"
ACCENT = "#7b6cff"
ACCENT_HI = "#a196ff"
TEXT = "#f1f1f4"
MUTED = "#8b8c99"
FAINT = "#5e5f6c"
BORDER = "#25262e"
LINE = "#1b1c22"
PIN = "#fbbf24"
DANGER = "#f87171"
MONO = "'Cascadia Mono', Consolas, monospace"
KIND_COLOR = {"text": "#8b7cff", "note": "#34d399", "link": "#60a5fa", "files": "#fbbf24",
              "image": "#f472b6", "color": "#a3a3ad"}
KIND_ICON = {"text": "type", "note": "note", "link": "link", "files": "file", "image": "image", "color": "drop"}

_CORNERS = '<path d="M4 8.5V6a2 2 0 0 1 2-2h2.5M15.5 4H18a2 2 0 0 1 2 2v2.5M20 15.5V18a2 2 0 0 1-2 2h-2.5M8.5 20H6a2 2 0 0 1-2-2v-2.5"/>'
_CLOUD = '<path d="M7 18.5a4.5 4.5 0 0 1-.6-8.96 6 6 0 0 1 11.47 1.49A3.75 3.75 0 0 1 17.25 18.5z"/>'
_FOLDER = '<path d="M3.5 7.5a2 2 0 0 1 2-2h3.6l2 2h7.4a2 2 0 0 1 2 2v7.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>'
_PIN = '<path d="M9 3.5h6M10 3.5V9l-3 3.5V14h10v-1.5L14 9V3.5M12 14v6.5"/>'
_FILE = '<path d="M14 3.5H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8.5z"/><path d="M14 3.5v5h5"/>'
ICON_SVG = {  # линейные иконки 24×24, рисуются цветом обводки
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "pin": _PIN,
    "unpin": _PIN + '<path d="M4 4l16 16"/>',
    "note": _FILE + '<path d="M9 13h6M9 16.5h4"/>',
    "file": _FILE,
    "type": '<path d="M5 7V5h14v2M12 5v14M9 19h6"/>',
    "text": '<path d="M5 7V5h14v2M12 5v14M9 19h6"/>',
    "image": '<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/><circle cx="9" cy="10" r="1.6"/>'
             '<path d="M20.5 15.5l-4.5-4.5-9 8.5"/>',
    "link": '<path d="M10 13.5a4 4 0 0 0 5.66.34l2.83-2.83a4 4 0 0 0-5.66-5.66l-1.4 1.4"/>'
            '<path d="M14 10.5a4 4 0 0 0-5.66-.34l-2.83 2.83a4 4 0 0 0 5.66 5.66l1.4-1.4"/>',
    "cloud": _CLOUD,
    "upload": _CLOUD + '<path d="M12 16v-5M9.75 13.25 12 11l2.25 2.25"/>',
    "folder": _FOLDER,
    "folder_plus": _FOLDER + '<path d="M12 10.5v5M9.5 13h5"/>',
    "shot": _CORNERS + '<rect x="8.5" y="8.5" width="7" height="7" rx="1.5"/>',
    "scan": _CORNERS + '<path d="M8 10h8M8 14h5"/>',
    "settings": '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "trash": '<path d="M4.5 7h15M9.5 7V4.5h5V7M6.5 7l.8 11.5a2 2 0 0 0 2 1.5h5.4a2 2 0 0 0 2-1.5L17.5 7M10 11v5M14 11v5"/>',
    "copy": '<rect x="8.5" y="8.5" width="11.5" height="11.5" rx="2.5"/>'
            '<path d="M15.5 8.5V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7.5a2 2 0 0 0 2 2h2.5"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "x": '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
    "save": '<path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M5 20h14"/>',
    "external": '<path d="M14 4h6v6M20 4l-8.5 8.5M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4"/>',
    "chev_down": '<path d="M6.5 9.5 12 15l5.5-5.5"/>',
    "chev_up": '<path d="M6.5 14.5 12 9l5.5 5.5"/>',
    "drop": '<path d="M12 3.5s6 6.2 6 10.5a6 6 0 0 1-12 0c0-4.3 6-10.5 6-10.5z"/>',
    "play": '<path d="M8 5.5v13l10.5-6.5z"/>',
    "pen": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
    "marker": '<path d="M15 4.5l4.5 4.5-8 8H7v-4.5z"/><path d="M4 20.5h16"/>',
    "line": '<path d="M5 19 19 5"/>',
    "arrow": '<path d="M5 19 19 5M10 5h9v9"/>',
    "rect": '<rect x="4" y="5.5" width="16" height="13" rx="1.5"/>',
    "ellipse": '<ellipse cx="12" cy="12" rx="8.5" ry="6.5"/>',
    "step": '<circle cx="12" cy="12" r="8.5"/><path d="M10.5 9.5l2-1.5v8"/>',
    "pixel": '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 9.33h16M4 14.67h16M9.33 4v16M14.67 4v16"/>',
    "eraser": '<path d="M7 20h13M5 15l9-9.5a1.5 1.5 0 0 1 2.1 0l3.4 3.4a1.5 1.5 0 0 1 0 2.1L12 20H9z"/><path d="M9.5 10.5l5 5"/>',
    "undo": '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
    "redo": '<path d="M15 14l5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/>',
}
_SVG_CACHE = {}


def draw_icon(p, name, rect, color=MUTED, stroke=1.75):
    key = (name, QColor(color).name(), stroke)
    r = _SVG_CACHE.get(key)
    if r is None:
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{key[1]}" '
               f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{ICON_SVG[name]}</svg>')
        r = _SVG_CACHE[key] = QSvgRenderer(QByteArray(svg.encode()))
    r.render(p, QRectF(rect))


def icon(name, color=MUTED, on=None, size=18, stroke=1.75):
    """QIcon из векторной иконки — с картинками под любой масштаб экрана."""
    ic = QIcon()
    states = [(QIcon.Normal, QIcon.Off, color), (QIcon.Disabled, QIcon.Off, FAINT)]
    if on:
        states.append((QIcon.Normal, QIcon.On, on))
    for dpr in (1, 1.25, 1.5, 1.75, 2, 2.5, 3):
        px = int(round(size * dpr))
        for mode, state, c in states:
            pm = QPixmap(px, px)
            pm.fill(Qt.transparent)
            pp = QPainter(pm)
            pp.setRenderHint(QPainter.Antialiasing)
            draw_icon(pp, name, QRectF(0, 0, px, px), c, stroke)
            pp.end()
            ic.addPixmap(pm, mode, state)
    return ic


def set_icon(btn, name, color=MUTED, size=16, on=None):
    btn.setIcon(icon(name, color, on))
    btn.setIconSize(QSize(size, size))
    return btn


QSS = f"""
* {{ color: {TEXT}; font-size: 10pt; }}
QMainWindow, QDialog {{ background: {BG}; }}
QWidget#side {{ background: {PANEL}; border-right: 1px solid {LINE}; }}
QWidget#center {{ background: {BG}; }}
QWidget#preview {{ background: {PANEL}; border-left: 1px solid {LINE}; }}
QLabel#logo {{ font-size: 12.5pt; font-weight: 600; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#hint {{ color: {FAINT}; font-size: 8.5pt; }}
QLabel#section {{ color: {FAINT}; font-size: 8pt; font-weight: 700; padding-top: 12px; }}
QLabel#badge {{ background: rgba(123, 108, 255, 36); color: #b9b0ff; border: 1px solid rgba(123, 108, 255, 77);
    border-radius: 6px; padding: 2px 8px; font-size: 8.5pt; font-weight: 600; }}
QLabel#empty {{ color: {FAINT}; font-size: 10.5pt; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 7px 10px;
    selection-background-color: {ACCENT}; selection-color: white;
}}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{ border-color: #30313b; }}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {ACCENT}; }}
QLineEdit:read-only {{ color: {MUTED}; }}
QLineEdit#title {{ background: transparent; border: 1px solid transparent; font-size: 14pt; font-weight: 600;
    padding: 4px 6px; }}
QLineEdit#title:hover {{ border-color: {BORDER}; }}
QLineEdit#title:focus {{ background: {CARD}; border-color: {ACCENT}; }}
QPlainTextEdit {{ padding: 10px 12px; border-radius: 10px; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{ background: #18191f; border: 1px solid #2b2c35; padding: 4px; outline: none;
    selection-background-color: rgba(123, 108, 255, 56); }}
QSpinBox::up-button, QSpinBox::down-button {{ background: transparent; border: none; width: 20px; }}
QPushButton, QToolButton {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 6px 12px;
}}
QToolButton::menu-indicator {{ image: none; width: 0; }}
QPushButton:hover, QToolButton:hover {{ background: {CARD_HOVER}; border-color: #30313b; }}
QPushButton:pressed, QToolButton:pressed {{ background: #15161c; }}
QPushButton:disabled, QToolButton:disabled {{ color: {FAINT}; }}
QPushButton#primary {{ border: 1px solid #8f82ff; color: white; font-weight: 600;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8a7cff, stop:1 #6b5bf2); }}
QPushButton#primary:hover {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #998dff, stop:1 #7767ff); }}
QPushButton#primary:pressed {{ background: #6252e6; }}
QPushButton#primary:disabled {{ background: #2a2747; border-color: #2a2747; color: #8580b0; }}
QPushButton#ghost, QPushButton#danger, QPushButton#flat {{
    background: transparent; border: 1px solid transparent; color: {MUTED}; }}
QPushButton#ghost:hover, QPushButton#flat:hover {{ background: rgba(255, 255, 255, 13); color: {TEXT}; }}
QPushButton#danger:hover {{ background: rgba(248, 113, 113, 26); color: {DANGER}; }}
QPushButton#flat {{ text-align: left; padding: 7px 10px; }}
QPushButton#tab {{ border-radius: 7px; padding: 5px 12px; background: transparent; border: 1px solid transparent;
    color: {MUTED}; }}
QPushButton#tab:hover {{ color: {TEXT}; }}
QPushButton#tab:checked {{ background: {CARD_HOVER}; border-color: #30313b; color: {TEXT}; }}
QFrame#quick, QFrame#compact {{ background: #14151a; border: 1px solid #2a2b34; border-radius: 14px; }}
QFrame#bubble {{ background: #16171c; border: 1px solid #2a2b34; border-radius: 12px; }}
QWidget#toast {{ background: #15161b; border: 1px solid #2a2b34; border-radius: 14px; }}
QLineEdit#compactSearch {{ border-radius: 9px; padding: 7px 10px; }}
QPushButton#chip {{ background: transparent; border: none; border-radius: 6px; padding: 3px 9px;
    color: {MUTED}; font-size: 8.5pt; }}
QPushButton#chip:hover {{ color: {TEXT}; background: rgba(255, 255, 255, 13); }}
QPushButton#chip:checked {{ background: transparent; color: white; }}
QFrame#chipPill {{ background: rgba(123, 108, 255, 56); border: 1px solid rgba(123, 108, 255, 90); border-radius: 6px; }}
QLabel#quickPrev {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; padding: 8px; color: #c8c8d2; }}
QMenu {{ background: #17181e; border: 1px solid #2b2c35; border-radius: 10px; padding: 5px; }}
QMenu::item {{ padding: 7px 22px 7px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: rgba(123, 108, 255, 51); }}
QMenu::item:disabled {{ color: {FAINT}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 5px 8px; }}
QToolTip {{ background: #1c1d24; color: {TEXT}; border: 1px solid #2e2f39; padding: 5px 8px; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: rgba(255, 255, 255, 26); border-radius: 3px; min-height: 36px; }}
QScrollBar::handle:vertical:hover {{ background: rgba(255, 255, 255, 51); }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QScrollBar:horizontal {{ height: 0; }}
QStatusBar {{ background: {BG}; color: {MUTED}; border-top: 1px solid {LINE}; }}
QSplitter::handle {{ background: {LINE}; }}
QCheckBox {{ spacing: 10px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px; border: 1px solid #3a3b46; background: {CARD}; }}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QCheckBox:disabled {{ color: {FAINT}; }}
"""


def app_qss():
    """QSS плюс картинки для галочек и стрелок (их нельзя нарисовать стилями — пишем в PNG)."""
    d = os.path.join(data_dir(), "ui")
    os.makedirs(d, exist_ok=True)

    def png(name, color):
        path = os.path.join(d, f"{name}_{color.lstrip('#')}.png")
        img = QImage(40, 40, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        draw_icon(p, name, QRectF(0, 0, 40, 40), color, 2.6)
        p.end()
        img.save(path)
        return path.replace("\\", "/")

    return QSS + f"""
QCheckBox::indicator:checked {{ image: url("{png('check', '#ffffff')}"); }}
QComboBox::down-arrow {{ image: url("{png('chev_down', MUTED)}"); width: 12px; height: 12px; }}
QSpinBox::up-arrow {{ image: url("{png('chev_up', MUTED)}"); width: 10px; height: 10px; }}
QSpinBox::down-arrow {{ image: url("{png('chev_down', MUTED)}"); width: 10px; height: 10px; }}
"""


def style_window(w):
    """Тёмный заголовок окна Windows 10/11 в цвет приложения."""
    if not IS_WIN:
        return
    try:
        hwnd = ctypes.c_void_p(int(w.winId()))

        def ref(h):
            c = QColor(h)
            return c.red() | c.green() << 8 | c.blue() << 16

        for attr, val in ((20, 1), (35, ref(PANEL)), (34, ref(BORDER))):
            v = ctypes.c_int(val)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))
    except Exception:
        pass


KIND_LABEL = {"text": "Текст", "link": "Ссылка", "color": "Цвет", "image": "Картинка", "files": "Файлы"}

HOTKEYS = {  # название: (модификаторы, виртуальная клавиша)
    "Ctrl+CapsLock": (0x2, 0x14),  # через хук клавиатуры, чтобы Caps Lock при этом не переключался
    "Win+V": (0x8, 0x56),  # занято журналом буфера Windows — перехватываем хуком клавиатуры
    "Ctrl+Alt+V": (0x2 | 0x1, 0x56),
    "Ctrl+Shift+V": (0x2 | 0x4, 0x56),
    "Alt+V": (0x1, 0x56),
    "Win+Shift+V": (0x8 | 0x4, 0x56),
    "Ctrl+`": (0x2, 0xC0),
    "Ctrl+Shift+Space": (0x2 | 0x4, 0x20),
}
DEFAULT_HOTKEY = "Ctrl+CapsLock"
HOOK_KEYS = {0x14}  # клавиши, которые всегда ловим хуком, а не RegisterHotKey

SHOT_HOTKEYS = {  # None — выключено
    "Alt+X": (0x1, 0x58),
    "Ctrl+Alt+X": (0x2 | 0x1, 0x58),
    "Ctrl+Shift+X": (0x2 | 0x4, 0x58),
    "Print Screen": (0, 0x2C),
    "Ctrl+Print Screen": (0x2, 0x2C),
    "Shift+Print Screen": (0x4, 0x2C),
    "Выключена": None,
}
DEFAULT_SHOT_HOTKEY = "Alt+X"
PANEL_HOTKEY_ID = 0xC11B
SHOT_HOTKEY_ID = 0xC11C

# ───────────────────────────── WinAPI ─────────────────────────────
if IS_WIN:
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    kernel32 = ctypes.windll.kernel32
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    WH_KEYBOARD_LL, LLKHF_INJECTED = 13, 0x10
    WM_KEYDOWN, WM_SYSKEYDOWN = 0x100, 0x104
    LRESULT = ctypes.c_ssize_t
    HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    user32.SetWindowsHookExW.restype = wintypes.HHOOK
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HMODULE, wintypes.DWORD]
    user32.CallNextHookEx.restype = LRESULT
    user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
    user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
    WM_TIMER, WM_QUIT = 0x113, 0x12
    user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p]
    user32.SetTimer.restype = ctypes.c_size_t
    user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
    user32.GetMessageW.restype = wintypes.BOOL
    user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    user32.GetAsyncKeyState.restype = ctypes.c_short
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    WM_HOTKEY = 0x0312
    MOD_NOREPEAT = 0x4000

    def send_ctrl_v():
        KEYUP = 0x2
        for vk in (0x12, 0x10, 0x5B):  # отпустить Alt/Shift/Win, если ещё зажаты
            if user32.GetAsyncKeyState(vk) & 0x8000:
                user32.keybd_event(vk, 0, KEYUP, 0)
        user32.keybd_event(0x11, 0, 0, 0)
        user32.keybd_event(0x56, 0, 0, 0)
        user32.keybd_event(0x56, 0, KEYUP, 0)
        user32.keybd_event(0x11, 0, KEYUP, 0)
    dwmapi = ctypes.windll.dwmapi
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]

    def visible_windows():
        """Прямоугольники видимых окон в физических пикселях, сверху вниз — для подсветки окна под курсором."""
        rects = []

        def cb(h, _):
            if not user32.IsWindowVisible(h) or user32.IsIconic(h):
                return True
            if user32.GetWindowLongW(h, -20) & (0x20 | 0x08000000):  # невидимые оверлеи (NVIDIA и т.п.)
                return True
            cloaked = ctypes.c_int(0)
            dwmapi.DwmGetWindowAttribute(h, 14, ctypes.byref(cloaked), 4)
            if cloaked.value:
                return True
            cls = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(h, cls, 64)
            if cls.value in ("Progman", "WorkerW"):
                return True
            r = wintypes.RECT()
            if dwmapi.DwmGetWindowAttribute(h, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
                user32.GetWindowRect(h, ctypes.byref(r))
            if r.right - r.left >= 20 and r.bottom - r.top >= 20:
                rects.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
            return True
        user32.EnumWindows(WNDENUMPROC(cb), 0)
        return rects
else:
    user32 = None

    def send_ctrl_v():
        pass

    def visible_windows():
        return []


class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback, hid):
        super().__init__()
        self.callback = callback
        self.hid = hid

    def nativeEventFilter(self, eventType, message):
        if IS_WIN:
            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY and msg.wParam == self.hid:
                    QTimer.singleShot(0, self.callback)
                    return True, 0
            except Exception:
                pass
        return False, 0


class WinKeyHook(QObject):
    """Сочетание Win+клавиша, которое держит сама Windows (Win+V — её журнал буфера).
    RegisterHotKey его не получит, поэтому ловим нажатие низкоуровневым хуком и не пускаем дальше.

    Хук живёт в своём потоке: если бы он ждал занятый главный поток (запуск, скриншот, сохранение),
    Windows молча сняла бы его по таймауту и Win+V снова открывал бы системный журнал.
    Для надёжности хук ещё и переустанавливается каждые 5 секунд."""
    fired = Signal()

    def __init__(self, vk, callback, mods=0x8):
        super().__init__()
        self.vk, self.mods = vk, mods
        self.held = False
        self.handle = None
        self.tid = 0
        self.fired.connect(callback)  # сигнал из потока хука придёт в главный поток очередью
        self.proc = HOOKPROC(self._proc)  # держим ссылку, иначе сборщик мусора уронит процесс
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._run, name="WinKeyHook", daemon=True)
        self.thread.start()
        self.ready.wait(3)

    def _install(self):
        return user32.SetWindowsHookExW(WH_KEYBOARD_LL, self.proc, kernel32.GetModuleHandleW(None), 0)

    def _run(self):
        self.tid = kernel32.GetCurrentThreadId()
        self.handle = self._install()
        self.ready.set()
        if not self.handle:
            return
        user32.SetTimer(None, 0, 5000, None)
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_TIMER:
                new = self._install()
                if new:
                    old, self.handle = self.handle, new
                    user32.UnhookWindowsHookEx(old)
        if self.handle:
            user32.UnhookWindowsHookEx(self.handle)
            self.handle = None

    def _mods_ok(self):
        """Зажаты ровно нужные модификаторы (Alt 1, Ctrl 2, Shift 4, Win 8)."""
        down = lambda vk: bool(user32.GetAsyncKeyState(vk) & 0x8000)
        held = (down(0x12) and 0x1) | (down(0x11) and 0x2) | (down(0x10) and 0x4) |                ((down(0x5B) or down(0x5C)) and 0x8)
        return held == self.mods

    def _proc(self, code, wparam, lparam):
        try:
            if code == 0:
                k = KBDLLHOOKSTRUCT.from_address(lparam)
                if k.vkCode == self.vk:
                    if wparam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                        if self.held or self._mods_ok():
                            if not self.held:
                                self.held = True
                                # «пустая» клавиша: после Win не откроется меню Пуск, а Windows разрешит
                                # нашему окну забрать фокус (последний ввод — от нас)
                                user32.keybd_event(0xE8, 0, 0, 0)
                                user32.keybd_event(0xE8, 0, 2, 0)
                                self.fired.emit()
                            return 1
                    elif self.held:
                        self.held = False
                        return 1
        except Exception:
            pass
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def release(self):
        if self.tid and self.thread.is_alive():
            user32.PostThreadMessageW(self.tid, WM_QUIT, 0, 0)
            self.thread.join(2)


class Hotkey:
    def __init__(self, callback, hid=PANEL_HOTKEY_ID, table=HOTKEYS, default=DEFAULT_HOTKEY):
        self.hid, self.table, self.default = hid, table, default
        self.callback = callback
        self.filter = HotkeyFilter(callback, hid)
        QApplication.instance().installNativeEventFilter(self.filter)
        self.registered = False
        self.hook = None

    def set(self, name):
        if not IS_WIN:
            return False
        self.release()
        combo = self.table[name] if name in self.table else self.table[self.default]
        if combo is None:  # выключена
            return True
        mods, vk = combo
        if vk in HOOK_KEYS:
            self.hook = WinKeyHook(vk, self.callback, mods)
            if not self.hook.handle:
                self.hook = None
            # запасной путь для окон «от администратора»: туда хук обычной программы не дотягивается,
            # а зарегистрированное сочетание срабатывает (только Caps Lock там заодно переключится)
            self.registered = bool(user32.RegisterHotKey(None, self.hid, mods | MOD_NOREPEAT, vk))
            return self.hook is not None or self.registered
        self.registered = bool(user32.RegisterHotKey(None, self.hid, mods | MOD_NOREPEAT, vk))
        if not self.registered and mods == 0x8:  # Win+клавиша занята системой
            self.hook = WinKeyHook(vk, self.callback, mods)
            if not self.hook.handle:
                self.hook = None
            return self.hook is not None
        return self.registered

    def release(self):
        if IS_WIN and self.registered:
            user32.UnregisterHotKey(None, self.hid)
            self.registered = False
        if self.hook:
            self.hook.release()
            self.hook = None


# ───────────────────────────── Автозапуск ─────────────────────────────
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --hidden'
    exe = sys.executable
    w = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(w):
        exe = w
    return f'"{exe}" "{os.path.abspath(__file__)}" --hidden'


def get_autostart():
    if not IS_WIN:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP)
            return True
    except OSError:
        return False


def set_autostart(on):
    if not IS_WIN:
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, APP)
            except OSError:
                pass


# ───────────────────────────── Утилиты ─────────────────────────────
def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for p in (os.path.join(base, name), os.path.join(base, "assets", name)):
        if os.path.exists(p):
            return p
    return None


def data_dir():
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base, APP)
    os.makedirs(d, exist_ok=True)
    return d


def migrate_from_old_name():
    """Программа раньше называлась Kipshot: при первом запуске копируем её историю и настройки,
    а автозапуск переводим на новое имя (старые файлы не трогаем)."""
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    old_db = os.path.join(base, OLD_APP, "clipnest.db")
    new_db = os.path.join(data_dir(), "kipshot.db")
    if not os.path.exists(new_db) and os.path.exists(old_db):
        try:
            shutil.copy2(old_db, new_db)
        except OSError as e:
            print("migrate error:", e, file=sys.stderr)
    if IS_WIN:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                                winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as k:
                winreg.QueryValueEx(k, OLD_APP)
                winreg.DeleteValue(k, OLD_APP)
                winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, autostart_command())
        except OSError:
            pass


HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
RGB_RE = re.compile(r"^rgba?\(\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*(?:[,/]\s*([\d.]+%?)\s*)?\)$", re.I)
URL_RE = re.compile(r"^(?:https?://|www\.)\S+$", re.I)


def parse_color(s):
    s = (s or "").strip()
    if HEX_RE.match(s):
        h = s[1:]
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h)
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        a = int(h[6:8], 16) if len(h) == 8 else 255
        return QColor(r, g, b, a)
    m = RGB_RE.match(s)
    if m:
        r, g, b = (min(255, int(x)) for x in m.groups()[:3])
        return QColor(r, g, b)
    return None


def classify_text(t):
    s = t.strip()
    if len(s) < 40 and parse_color(s) is not None:
        return "color"
    if "\n" not in s and URL_RE.match(s):
        return "link"
    return "text"


def make_hash(kind, text, image=None):
    h = hashlib.sha1(kind.encode())
    if image:
        h.update(image)
    else:
        h.update((text or "").encode("utf-8", "replace"))
    return h.hexdigest()


# ───────────────────────────── Звук ─────────────────────────────
SOUNDS = {"pop": "Мягкий щелчок", "drop": "Капля", "chime": "Колокольчик", "off": "Без звука"}


def make_wav(kind, volume):
    """Генерирует короткий приятный звук (WAV, 44.1 кГц, 16 бит)."""
    import math, struct, io, wave
    sr = 44100
    if kind == "drop":
        dur, parts = 0.16, None
    elif kind == "chime":
        dur, parts = 0.35, [(1318.5, 1.0), (1975.5, 0.5), (2637.0, 0.25)]
    else:
        dur, parts = 0.07, [(1400.0, 1.0), (2800.0, 0.2)]
    n = int(sr * dur)
    amp = 0.55 * max(0.0, min(1.0, volume / 100))
    frames = bytearray()
    phase = 0.0
    for i in range(n):
        t = i / sr
        attack = min(1.0, t / 0.004)
        if kind == "drop":
            f = 1700 * math.exp(-t * 9) + 500  # «бульк»: частота падает
            phase += 2 * math.pi * f / sr
            v = math.sin(phase) * math.exp(-t * 22)
        elif kind == "chime":
            v = sum(a * math.sin(2 * math.pi * f * t) * math.exp(-t * (9 + k * 4))
                    for k, (f, a) in enumerate(parts)) / 1.75
        else:
            v = sum(a * math.sin(2 * math.pi * f * t) for f, a in parts) / 1.2 * math.exp(-t * 60)
        frames += struct.pack("<h", int(max(-1, min(1, v * attack * amp)) * 32767))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))
    return buf.getvalue()


class Sound:
    def __init__(self, kind="pop", volume=60, filename="copy_sound.wav"):
        self.path = os.path.join(data_dir(), filename)
        self.kind = kind
        self.volume = volume
        self.last = 0.0
        self.prepare()

    def configure(self, kind, volume):
        self.kind, self.volume = kind, volume
        self.prepare()

    def prepare(self):
        if self.kind != "off":
            try:
                with open(self.path, "wb") as f:
                    f.write(make_wav(self.kind, self.volume))
            except OSError:
                pass

    def play(self):
        if self.kind == "off" or time.time() - self.last < 0.12:
            return
        self.last = time.time()
        if IS_WIN:
            import winsound
            try:
                winsound.PlaySound(self.path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            except RuntimeError:
                pass
        else:
            QApplication.beep()


def hidpi_pixmap(img, w, h, dpr):
    """Масштабирует картинку под физические пиксели экрана, чтобы она не мылилась при 125–200%."""
    pm = QPixmap.fromImage(img)
    if pm.width() > w * dpr or pm.height() > h * dpr:
        pm = pm.scaled(round(w * dpr), round(h * dpr), Qt.KeepAspectRatio, Qt.SmoothTransformation)
    pm.setDevicePixelRatio(dpr)
    return pm


# ── распознавание текста (встроенный OCR Windows, работает без интернета)
CYR = re.compile(r"[а-яё]", re.I)
LAT = re.compile(r"[a-z]", re.I)


def _is_russian_word(w):
    c, l = len(CYR.findall(w)), len(LAT.findall(w))
    return c >= 2 and c > l * 3


async def _ocr_async(png):
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
    st = InMemoryRandomAccessStream()
    wr = DataWriter(st)
    wr.write_bytes(png)
    await wr.store_async()
    wr.detach_stream()
    st.seek(0)
    bmp = await (await BitmapDecoder.create_async(st)).get_software_bitmap_async()
    res = {}
    for tag in ("ru", "en-US"):
        if OcrEngine.is_language_supported(Language(tag)):
            res[tag] = await OcrEngine.try_create_from_language(Language(tag)).recognize_async(bmp)
    if not res:
        eng = OcrEngine.try_create_from_user_profile_languages()
        if eng is None:
            raise RuntimeError("В Windows не установлен ни один язык распознавания текста")
        res["user"] = await eng.recognize_async(bmp)
    return res


def _rect_overlap(a, b):
    w = min(a.x + a.width, b.x + b.width) - max(a.x, b.x)
    h = min(a.y + a.height, b.y + b.height) - max(a.y, b.y)
    if w <= 0 or h <= 0:
        return 0
    return w * h / max(1, min(a.width * a.height, b.width * b.height))


def _merge_ocr(ru, en):
    """Русские слова берём у русского движка, латиницу и цифры — у английского (он их читает точнее)."""
    ru_words = [w.text for l in ru.lines for w in l.words]
    share = sum(map(_is_russian_word, ru_words)) / max(1, len(ru_words))
    if share < 0.35:  # на картинке в основном не русский текст
        return "\n".join(l.text for l in en.lines)
    en_words = [w for l in en.lines for w in l.words]
    lines = []
    for line in ru.lines:
        out = []
        for w in line.words:
            t = w.text
            if not (CYR.search(t) and not LAT.search(t)):
                best = max(en_words, key=lambda e: _rect_overlap(w.bounding_rect, e.bounding_rect), default=None)
                if best is not None and _rect_overlap(w.bounding_rect, best.bounding_rect) > 0.5:
                    t = best.text
            out.append(t)
        lines.append(" ".join(out))
    return "\n".join(lines)


def ocr_image(data):
    img = QImage.fromData(data)
    if img.isNull():
        raise RuntimeError("Не удалось открыть картинку")
    # мелкий текст на скринах распознаётся заметно лучше после увеличения в 2 раза
    if max(img.width(), img.height()) * 2 <= 10000:
        img = img.scaled(img.width() * 2, img.height() * 2, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    res = asyncio.run(_ocr_async(qimage_to_png(img)))
    if "ru" in res and "en-US" in res:
        text = _merge_ocr(res["ru"], res["en-US"])
    else:
        text = "\n".join(l.text for l in next(iter(res.values())).lines)
    return text.replace("Ø", "0").strip()  # перечёркнутый ноль моноширинных шрифтов


def qimage_to_png(img):
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


def reltime(ts):
    if not ts:
        return ""
    d = time.time() - ts
    if d < 60:
        return "только что"
    if d < 3600:
        return f"{int(d // 60)} мин назад"
    dt = datetime.datetime.fromtimestamp(ts)
    today = datetime.date.today()
    if dt.date() == today:
        return dt.strftime("сегодня %H:%M")
    if dt.date() == today - datetime.timedelta(days=1):
        return dt.strftime("вчера %H:%M")
    return dt.strftime("%d.%m.%Y %H:%M")


def item_title(d):
    if d["title"]:
        return d["title"]
    kind, text = d["kind"], d["text"] or ""
    if kind == "image":
        return f"Картинка {text}"
    if kind == "files":
        paths = [p for p in text.splitlines() if p]
        if len(paths) == 1:
            return os.path.basename(paths[0].rstrip("/\\")) or paths[0]
        return f"{len(paths)} файлов: " + ", ".join(os.path.basename(p) for p in paths[:3])
    for line in text.splitlines():
        if line.strip():
            return " ".join(line.split())[:300]
    return "(пробелы)"


def item_meta(d, with_time=True):
    parts = ["Заметка" if d["is_note"] else KIND_LABEL.get(d["kind"], d["kind"]),
             reltime(d["used"]) if with_time else ""]
    if d["kind"] in ("text",):
        parts.append(f"{len(d['text'] or '')} симв.")
    if d["kind"] == "image" and d["isize"]:
        parts.append(f"{d['isize'] // 1024} КБ")
    return " · ".join(p for p in parts if p)


def make_app_icon(size=64):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 64
    path = QPainterPath()
    path.addRoundedRect(QRectF(4 * s, 4 * s, 56 * s, 56 * s), 14 * s, 14 * s)
    g = QLinearGradient(0, 0, 0, size)
    g.setColorAt(0, QColor("#9083ff"))
    g.setColorAt(1, QColor("#5a49e6"))
    p.fillPath(path, g)
    p.setBrush(QColor("white"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(18 * s, 16 * s, 28 * s, 34 * s), 4 * s, 4 * s)
    p.setBrush(QColor("#6a5af0"))
    p.drawRoundedRect(QRectF(25 * s, 12 * s, 14 * s, 8 * s), 3 * s, 3 * s)
    p.setBrush(QColor("#c9c2ff"))
    for i, w in enumerate((18, 14, 16)):
        p.drawRoundedRect(QRectF(23 * s, (26 + i * 7) * s, w * s, 3 * s), 1.5 * s, 1.5 * s)
    p.end()
    return QIcon(pm)


# ───────────────────────────── Хранилище ─────────────────────────────
class Store:
    COLS = "id, kind, text, hash, pinned, is_note, folder_id, title, created, used, url, length(image) AS isize"

    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.create_function("pylower", 1, lambda s: s.lower() if isinstance(s, str) else s)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS items(
                id INTEGER PRIMARY KEY, kind TEXT, text TEXT, image BLOB, hash TEXT,
                pinned INTEGER DEFAULT 0, is_note INTEGER DEFAULT 0, folder_id INTEGER,
                title TEXT, created REAL, used REAL);
            CREATE INDEX IF NOT EXISTS ix_hash ON items(hash);
            CREATE INDEX IF NOT EXISTS ix_used ON items(used);
            CREATE TABLE IF NOT EXISTS folders(id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        """)
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(items)")}
        for c in ("url", "del_url"):  # ссылки на хостинг (добавлены в 1.1)
            if c not in cols:
                self.db.execute(f"ALTER TABLE items ADD COLUMN {c} TEXT")
        self.db.commit()

    # настройки
    def get_setting(self, key, default=None):
        r = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r[0] if r else default

    def set_setting(self, key, value):
        self.db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)", (key, str(value)))
        self.db.commit()

    # элементы
    def find_hash(self, h):
        r = self.db.execute("SELECT id FROM items WHERE hash=? ORDER BY is_note DESC LIMIT 1", (h,)).fetchone()
        return r[0] if r else None

    def add(self, kind, text, image=None, is_note=0, title=None, h=None):
        now = time.time()
        h = h or make_hash(kind, text, image)
        cur = self.db.execute(
            "INSERT INTO items(kind, text, image, hash, is_note, title, created, used) VALUES(?,?,?,?,?,?,?,?)",
            (kind, text, image, h, is_note, title, now, now))
        self.db.commit()
        return cur.lastrowid

    def set_url(self, iid, url, del_url=""):
        self.db.execute("UPDATE items SET url=?, del_url=? WHERE id=?", (url, del_url or None, iid))
        self.db.commit()

    def touch(self, iid):
        self.db.execute("UPDATE items SET used=? WHERE id=?", (time.time(), iid))
        self.db.commit()

    def get(self, iid):
        return self.db.execute("SELECT *, length(image) AS isize FROM items WHERE id=?", (iid,)).fetchone()

    def update(self, iid, **fields):
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        self.db.execute(f"UPDATE items SET {sets} WHERE id=?", (*fields.values(), iid))
        self.db.commit()

    def delete(self, iid):
        self.db.execute("DELETE FROM items WHERE id=?", (iid,))
        self.db.commit()

    def query(self, view, search="", limit=1000):
        where, args, order = [], [], "used DESC"
        v = view[0]
        if v == "all":
            where.append("is_note=0")
            order = "pinned DESC, used DESC"
        elif v == "pinned":
            where.append("pinned=1")
        elif v == "notes":
            where.append("is_note=1")
            order = "pinned DESC, used DESC"
        elif v == "images":
            where.append("kind='image'")
        elif v == "links":
            where.append("kind='link'")
        elif v == "uploads":
            where.append("url IS NOT NULL AND url<>''")
        elif v == "folder":
            where.append("folder_id=?")
            args.append(view[1])
            order = "pinned DESC, used DESC"
        if search:
            s = f"%{search.lower()}%"
            where.append("(pylower(text) LIKE ? OR pylower(title) LIKE ? OR pylower(url) LIKE ?)")
            args += [s, s, s]
        sql = f"SELECT {self.COLS} FROM items"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY {order} LIMIT {int(limit)}"
        return self.db.execute(sql, args).fetchall()

    def counts(self):
        r = self.db.execute("""SELECT SUM(is_note=0), SUM(pinned=1), SUM(is_note=1), SUM(kind='image'),
            SUM(kind='link'), SUM(url IS NOT NULL AND url<>'') FROM items""").fetchone()
        views = [("all",), ("pinned",), ("notes",), ("images",), ("links",), ("uploads",)]
        out = {v: r[i] or 0 for i, v in enumerate(views)}
        for row in self.db.execute("SELECT folder_id, COUNT(*) FROM items WHERE folder_id IS NOT NULL GROUP BY folder_id"):
            out[("folder", row[0])] = row[1]
        return out

    def trim(self, max_items):
        self.db.execute("""DELETE FROM items WHERE id IN (
            SELECT id FROM items WHERE pinned=0 AND is_note=0 AND folder_id IS NULL
            ORDER BY used DESC LIMIT -1 OFFSET ?)""", (int(max_items),))
        self.db.commit()

    def clear_history(self):
        self.db.execute("DELETE FROM items WHERE pinned=0 AND is_note=0 AND folder_id IS NULL")
        self.db.commit()
        self.db.execute("VACUUM")

    # папки
    def folders(self):
        return self.db.execute("SELECT id, name FROM folders ORDER BY name COLLATE NOCASE").fetchall()

    def add_folder(self, name):
        cur = self.db.execute("INSERT INTO folders(name) VALUES(?)", (name,))
        self.db.commit()
        return cur.lastrowid

    def rename_folder(self, fid, name):
        self.db.execute("UPDATE folders SET name=? WHERE id=?", (name, fid))
        self.db.commit()

    def delete_folder(self, fid):
        self.db.execute("UPDATE items SET folder_id=NULL WHERE folder_id=?", (fid,))
        self.db.execute("DELETE FROM folders WHERE id=?", (fid,))
        self.db.commit()


# ───────────────────────────── Отрисовка карточек ─────────────────────────────
ROLE = Qt.UserRole + 1


class ItemDelegate(QStyledItemDelegate):
    def __init__(self, ctl, height=64, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.h = height

    def sizeHint(self, option, index):
        return QSize(200, self.h)

    def paint(self, p, opt, index):
        d = index.data(ROLE)
        if not d:
            return
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRectF(opt.rect.adjusted(6, 2, -6, -2))
        sel = bool(opt.state & QStyle.StateFlag.State_Selected)
        hov = bool(opt.state & QStyle.StateFlag.State_MouseOver)
        card = QPainterPath()
        card.addRoundedRect(r, 10, 10)
        if sel:
            p.fillPath(card, QColor(123, 108, 255, 34))
            p.setPen(QPen(QColor(123, 108, 255, 115), 1))
            p.drawPath(card)
        elif hov:
            p.fillPath(card, QColor(255, 255, 255, 10))

        s = self.h - 24
        ir = QRectF(r.left() + 10, r.center().y() - s / 2, s, s)
        draw_item_icon(p, self.ctl, d, ir, 9, opt.font)

        f1 = QFont(opt.font)
        f1.setPointSizeF(10)
        f1.setWeight(QFont.Medium)
        fm1 = QFontMetrics(f1)
        f2 = QFont(opt.font)
        f2.setPointSizeF(8.5)
        fm2 = QFontMetrics(f2)
        when = short_time(d["used"])
        ww = fm2.horizontalAdvance(when) + 2
        pinned = bool(d["pinned"])
        tx = ir.right() + 12
        top = r.center().y() - (fm1.height() + fm2.height() + 3) / 2
        tw = r.right() - tx - ww - 22
        p.setFont(f1)
        p.setPen(QColor(TEXT))
        p.drawText(QRectF(tx, top, tw, fm1.height()), Qt.AlignLeft | Qt.AlignVCenter,
                   fm1.elidedText(item_title(d), Qt.ElideRight, int(tw)))
        mw = r.right() - tx - (34 if pinned else 14)
        p.setFont(f2)
        p.setPen(QColor(MUTED))
        p.drawText(QRectF(tx, top + fm1.height() + 3, mw, fm2.height()), Qt.AlignLeft | Qt.AlignVCenter,
                   fm2.elidedText(item_meta(d, False), Qt.ElideRight, int(mw)))
        p.setPen(QColor(FAINT))
        p.drawText(QRectF(r.right() - ww - 12, top, ww, fm1.height()), Qt.AlignRight | Qt.AlignVCenter, when)
        if pinned:
            draw_icon(p, "pin", QRectF(r.right() - 27, top + fm1.height() + 3 + (fm2.height() - 14) / 2, 14, 14), PIN)
        p.restore()


def fill_list(lw, rows, keep_id=None):
    lw.blockSignals(True)
    lw.clear()
    sel_row = 0
    for i, row in enumerate(rows):
        it = QListWidgetItem()
        d = dict(row)
        it.setData(ROLE, d)
        it.setData(Qt.UserRole, d["id"])
        lw.addItem(it)
        if keep_id is not None and d["id"] == keep_id:
            sel_row = i
    lw.blockSignals(False)
    if rows:
        lw.setCurrentRow(sel_row)
    else:
        lw.currentItemChanged.emit(None, None)


def current_id(lw):
    it = lw.currentItem()
    return it.data(Qt.UserRole) if it else None


# ───────────────────────────── Виджеты предпросмотра ─────────────────────────────
class ImageView(QWidget):
    def __init__(self):
        super().__init__()
        self.pm = None
        self.cache = None
        self.setMinimumHeight(120)

    def set_pixmap(self, pm):
        self.pm = pm
        self.cache = None
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 12, 12)
        p.fillPath(path, QColor("#0a0b0e"))
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawPath(path)
        if not self.pm or self.pm.isNull():
            return
        avail = self.rect().adjusted(10, 10, -10, -10).size()
        dpr = self.devicePixelRatioF()
        key = (avail.width(), avail.height(), dpr)
        if not self.cache or self.cache[0] != key:
            self.cache = (key, hidpi_pixmap(self.pm.toImage(), avail.width(), avail.height(), dpr))
        pm = self.cache[1]
        w, h = pm.width() / dpr, pm.height() / dpr
        x = (self.width() - w) / 2
        y = (self.height() - h) / 2
        p.drawPixmap(QRectF(x, y, w, h), pm, QRectF(pm.rect()))


class ColorView(QWidget):
    def __init__(self):
        super().__init__()
        self.c = QColor("black")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.swatch = QWidget()
        self.swatch.setMinimumHeight(160)
        self.info = QLabel()
        self.info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.info.setStyleSheet(f"font-family: {MONO}; font-size: 10.5pt; color: {MUTED};")
        lay.addWidget(self.swatch, 1)
        lay.addWidget(self.info)

    def set_color(self, c):
        self.c = c
        self.swatch.setStyleSheet(f"background: {c.name(QColor.HexArgb if c.alpha() < 255 else QColor.HexRgb)};"
                                  f" border-radius: 14px; border: 1px solid {BORDER};")
        h, s, l, _ = c.getHsl()
        self.info.setText(f"HEX   {c.name().upper()}\nRGB   {c.red()}, {c.green()}, {c.blue()}\n"
                          f"HSL   {max(h, 0)}°, {round(s / 2.55)}%, {round(l / 2.55)}%")


class Preview(QWidget):
    def __init__(self, ctl):
        super().__init__()
        self.setObjectName("preview")
        self.setAttribute(Qt.WA_StyledBackground)
        self.ctl = ctl
        self.iid = None
        self.row = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 18)
        lay.setSpacing(12)

        top = QHBoxLayout()
        self.badge = QLabel()
        self.badge.setObjectName("badge")
        self.meta = QLabel()
        self.meta.setObjectName("muted")
        top.addWidget(self.badge)
        top.addWidget(self.meta)
        top.addStretch()
        lay.addLayout(top)

        self.title = QLineEdit()
        self.title.setObjectName("title")
        self.title.setPlaceholderText("Без названия")
        lay.addWidget(self.title)

        self.stack = QStackedWidget()
        self.empty = QLabel("Выберите элемент,\nчтобы увидеть предпросмотр")
        self.empty.setObjectName("empty")
        self.empty.setAlignment(Qt.AlignCenter)
        self.text = QPlainTextEdit()
        self.text.setStyleSheet(f"font-family: {MONO}; font-size: 10pt;")
        self.image = ImageView()
        self.color = ColorView()
        for w in (self.empty, self.text, self.image, self.color):
            self.stack.addWidget(w)
        lay.addWidget(self.stack, 1)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        self.copy_btn = set_icon(QPushButton("  Копировать"), "copy", "#ffffff")
        self.copy_btn.setObjectName("primary")
        self.pin_btn = set_icon(QPushButton("  Закрепить"), "pin")
        self.folder_btn = set_icon(QToolButton(), "folder")
        self.folder_btn.setText("  В папку")
        self.folder_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.folder_btn.setPopupMode(QToolButton.InstantPopup)
        self.folder_menu = QMenu(self)
        self.folder_menu.aboutToShow.connect(self.build_folder_menu)
        self.folder_btn.setMenu(self.folder_menu)
        row1.addWidget(self.copy_btn, 1)
        row1.addWidget(self.pin_btn)
        row1.addWidget(self.folder_btn)
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(2)
        self.note_btn = set_icon(QPushButton(" В заметки"), "note")
        self.open_btn = set_icon(QPushButton(" Открыть"), "external")
        self.ocr_btn = set_icon(QPushButton(" Текст"), "scan")
        self.ocr_btn.setToolTip("Распознать текст с картинки")
        self.up_btn = set_icon(QPushButton(" Загрузить"), "upload")
        self.save_btn = set_icon(QPushButton("  Сохранить"), "check", "#ffffff")
        self.save_btn.setObjectName("primary")
        self.del_btn = set_icon(QPushButton(), "trash")
        self.del_btn.setToolTip("Удалить  [Del]")
        self.del_btn.setObjectName("danger")
        for b in (self.note_btn, self.open_btn, self.ocr_btn, self.up_btn):
            b.setObjectName("ghost")
        for b in (self.copy_btn, self.pin_btn, self.folder_btn, self.note_btn, self.open_btn, self.ocr_btn,
                  self.up_btn, self.save_btn, self.del_btn):
            b.setCursor(Qt.PointingHandCursor)
        row2.addWidget(self.note_btn)
        row2.addWidget(self.open_btn)
        row2.addWidget(self.ocr_btn)
        row2.addWidget(self.up_btn)
        row2.addStretch()
        row2.addWidget(self.save_btn)
        row2.addWidget(self.del_btn)
        lay.addLayout(row2)

        self.copy_btn.clicked.connect(lambda: self.iid and self.ctl.copy_item(self.iid, notify=True))
        self.pin_btn.clicked.connect(lambda: self.iid and self.ctl.toggle_pin(self.iid))
        self.note_btn.clicked.connect(lambda: self.iid and self.ctl.toggle_note(self.iid))
        self.del_btn.clicked.connect(lambda: self.iid and self.ctl.delete_item(self.iid))
        self.open_btn.clicked.connect(self.open_item)
        self.ocr_btn.clicked.connect(lambda: self.iid and self.ctl.recognize_text(self.iid))
        self.up_btn.clicked.connect(self.on_up_btn)
        self.save_btn.clicked.connect(self.save)
        self.text.textChanged.connect(self.on_edit)
        self.title.textChanged.connect(self.on_edit)
        self.show_item(None)

    def on_up_btn(self):
        if not self.row:
            return
        if self.row["url"]:
            self.ctl.copy_link(self.iid)
        else:
            self.ctl.upload_item(self.iid)

    def build_folder_menu(self):
        m = self.folder_menu
        m.clear()
        if not self.row:
            return
        cur = self.row["folder_id"]
        a = m.addAction(("✓ " if cur is None else "   ") + "Без папки")
        a.triggered.connect(lambda: self.ctl.set_folder(self.iid, None))
        for f in self.ctl.store.folders():
            a = m.addAction(("✓ " if cur == f["id"] else "   ") + f["name"])
            a.triggered.connect(lambda _=False, fid=f["id"]: self.ctl.set_folder(self.iid, fid))
        m.addSeparator()
        m.addAction("＋ Новая папка…").triggered.connect(self.new_folder_and_move)

    def new_folder_and_move(self):
        fid = self.ctl.ask_new_folder(self)
        if fid:
            self.ctl.set_folder(self.iid, fid)

    def show_item(self, iid):
        if iid is not None and iid == self.iid and self.save_btn.isVisible():
            return  # не затирать несохранённые правки при обновлении списка
        self.iid = iid
        self.row = self.ctl.store.get(iid) if iid else None
        r = self.row
        has = r is not None
        for w in (self.copy_btn, self.pin_btn, self.folder_btn, self.note_btn, self.del_btn, self.title):
            w.setEnabled(has)
        self.title.blockSignals(True)
        self.text.blockSignals(True)
        if not has:
            self.badge.hide()
            self.meta.setText("")
            self.title.setText("")
            self.stack.setCurrentWidget(self.empty)
            self.open_btn.hide()
            self.ocr_btn.hide()
            self.up_btn.hide()
            self.save_btn.hide()
        else:
            self.badge.show()
            self.badge.setText("Заметка" if r["is_note"] else KIND_LABEL.get(r["kind"], r["kind"]))
            meta = [f"создано {reltime(r['created'])}"]
            if r["folder_id"]:
                names = {f["id"]: f["name"] for f in self.ctl.store.folders()}
                meta.append("📁 " + names.get(r["folder_id"], ""))
            self.meta.setText(" · ".join(meta))
            self.title.setText(r["title"] or "")
            self.pin_btn.setText("  Открепить" if r["pinned"] else "  Закрепить")
            set_icon(self.pin_btn, "unpin" if r["pinned"] else "pin")
            self.note_btn.setText(" Из заметок" if r["is_note"] else " В заметки")
            self.note_btn.setVisible(r["kind"] != "image" or bool(r["is_note"]))
            kind = r["kind"]
            self.ocr_btn.setVisible(kind == "image")
            self.up_btn.setVisible(kind == "image")
            self.up_btn.setText(" Ссылка" if r["url"] else
                               " Загружаю…" if r["id"] in self.ctl.uploading else " Загрузить")
            set_icon(self.up_btn, "link" if r["url"] else "upload")
            self.up_btn.setEnabled(r["id"] not in self.ctl.uploading)
            self.up_btn.setToolTip(r["url"] or "Залить на хостинг и скопировать ссылку")
            if kind == "image":
                img = QImage.fromData(r["image"])
                self.image.set_pixmap(QPixmap.fromImage(img))
                self.stack.setCurrentWidget(self.image)
                self.meta.setText(self.meta.text() + f" · {r['text']} · {(r['isize'] or 0) // 1024} КБ"
                                  + (" · загружено" if r["url"] else ""))
                self.open_btn.setText(" Сохранить как…")
                set_icon(self.open_btn, "save")
                self.open_btn.show()
            elif kind == "color":
                self.color.set_color(parse_color(r["text"]) or QColor("black"))
                self.stack.setCurrentWidget(self.color)
                self.open_btn.hide()
            else:
                self.text.setPlainText(r["text"] or "")
                self.text.setReadOnly(kind == "files")
                self.stack.setCurrentWidget(self.text)
                self.open_btn.setText({"link": " Открыть ссылку", "files": " Показать в папке"}.get(kind, ""))
                set_icon(self.open_btn, "external" if kind == "link" else "folder")
                self.open_btn.setVisible(kind in ("link", "files"))
            self.save_btn.hide()
        self.title.blockSignals(False)
        self.text.blockSignals(False)

    def on_edit(self):
        if self.row:
            self.save_btn.show()

    def save(self):
        if not self.row:
            return
        text = self.text.toPlainText() if self.stack.currentWidget() is self.text else None
        self.ctl.save_item(self.iid, self.title.text().strip() or None, text)

    def open_item(self):
        r = self.row
        if not r:
            return
        if r["kind"] == "link":
            url = r["text"].strip()
            if url.lower().startswith("www."):
                url = "https://" + url
            QDesktopServices.openUrl(QUrl(url))
        elif r["kind"] == "files":
            first = next((p for p in r["text"].splitlines() if p), "")
            folder = first if os.path.isdir(first) else os.path.dirname(first)
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        elif r["kind"] == "image":
            path, _ = QFileDialog.getSaveFileName(self, "Сохранить картинку",
                                                  os.path.join(os.path.expanduser("~"), "clip.png"),
                                                  "PNG (*.png)")
            if path:
                with open(path, "wb") as f:
                    f.write(r["image"])


# ───────────────────────────── Главное окно ─────────────────────────────
FIXED_VIEWS = [
    ("История", ("all",), "clock"),
    ("Закреплённые", ("pinned",), "pin"),
    ("Мои заметки", ("notes",), "note"),
    ("Картинки", ("images",), "image"),
    ("Ссылки", ("links",), "link"),
    ("Загруженные", ("uploads",), "cloud"),
]
SIDE_ICON, SIDE_COUNT, SIDE_HDR = Qt.UserRole + 2, Qt.UserRole + 3, Qt.UserRole + 4


class SideDelegate(QStyledItemDelegate):
    """Пункт боковой панели: иконка, название, счётчик справа."""

    def sizeHint(self, option, index):
        return QSize(150, 32 if index.data(SIDE_HDR) else 34)

    def paint(self, p, opt, index):
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(opt.rect)
        text = index.data(Qt.DisplayRole) or ""
        if index.data(SIDE_HDR):
            f = QFont(opt.font)
            f.setPointSizeF(7.5)
            f.setBold(True)
            f.setLetterSpacing(QFont.AbsoluteSpacing, 0.8)
            p.setFont(f)
            p.setPen(QColor(FAINT))
            p.drawText(r.adjusted(12, 0, -8, -5), Qt.AlignLeft | Qt.AlignBottom, text)
            p.restore()
            return
        enabled = bool(index.flags() & Qt.ItemIsEnabled)
        sel = bool(opt.state & QStyle.StateFlag.State_Selected)
        hov = bool(opt.state & QStyle.StateFlag.State_MouseOver) and enabled
        rr = r.adjusted(0, 1, 0, -1)
        path = QPainterPath()
        path.addRoundedRect(rr, 8, 8)
        if sel:
            p.fillPath(path, QColor(255, 255, 255, 15))
        elif hov:
            p.fillPath(path, QColor(255, 255, 255, 8))
        x = rr.left() + 12
        ic = index.data(SIDE_ICON)
        if ic:
            draw_icon(p, ic, QRectF(x, rr.center().y() - 8, 16, 16), ACCENT_HI if sel else MUTED)
            x += 27
        cnt = index.data(SIDE_COUNT)
        ctext = str(cnt) if cnt else ""
        f2 = QFont(opt.font)
        f2.setPointSizeF(8.5)
        cw = QFontMetrics(f2).horizontalAdvance(ctext)
        f = QFont(opt.font)
        f.setPointSizeF(9.5)
        if sel:
            f.setWeight(QFont.Medium)
        fm = QFontMetrics(f)
        tw = rr.right() - x - cw - 18
        p.setFont(f)
        p.setPen(QColor(TEXT if sel else "#c4c5cf" if enabled else FAINT))
        p.drawText(QRectF(x, rr.top(), tw, rr.height()), Qt.AlignLeft | Qt.AlignVCenter,
                   fm.elidedText(text, Qt.ElideRight, int(tw)))
        if ctext:
            p.setFont(f2)
            p.setPen(QColor(MUTED if sel else FAINT))
            p.drawText(QRectF(rr.right() - cw - 12, rr.top(), cw, rr.height()), Qt.AlignRight | Qt.AlignVCenter, ctext)
        p.restore()


class MainWindow(QMainWindow):
    def __init__(self, ctl):
        super().__init__()
        self.ctl = ctl
        self.setWindowTitle(APP)
        self.setWindowIcon(ctl.icon)
        self.resize(1120, 700)
        self.view = ("all",)

        split = QSplitter()
        split.setHandleWidth(1)
        self.setCentralWidget(split)

        # ── боковая панель
        side = QWidget()
        side.setObjectName("side")
        side.setAttribute(Qt.WA_StyledBackground)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(10, 18, 10, 12)
        sl.setSpacing(2)
        brand = QHBoxLayout()
        brand.setContentsMargins(8, 0, 0, 14)
        brand.setSpacing(10)
        mark = QLabel()
        mark.setPixmap(ctl.icon.pixmap(QSize(26, 26), self.devicePixelRatioF()))
        logo = QLabel(APP)
        logo.setObjectName("logo")
        brand.addWidget(mark)
        brand.addWidget(logo)
        brand.addStretch()
        sl.addLayout(brand)
        self.side = QListWidget()
        self.side.setObjectName("sideList")
        self.side.setItemDelegate(SideDelegate(self.side))
        self.side.setMouseTracking(True)
        self.side.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.side.currentItemChanged.connect(self.on_view_changed)
        self.side.setContextMenuPolicy(Qt.CustomContextMenu)
        self.side.customContextMenuRequested.connect(self.side_menu)
        sl.addWidget(self.side, 1)
        shot = set_icon(QPushButton("   Скриншот"), "shot")
        shot.clicked.connect(lambda: QTimer.singleShot(250, self.ctl.take_screenshot))  # дать кнопке отрисоваться
        add_folder = set_icon(QPushButton("   Новая папка"), "folder_plus")
        add_folder.clicked.connect(lambda: self.ctl.ask_new_folder(self))
        settings = set_icon(QPushButton("   Настройки"), "settings")
        settings.clicked.connect(self.ctl.open_settings)
        for b in (shot, add_folder, settings):
            b.setObjectName("flat")
            b.setCursor(Qt.PointingHandCursor)
            sl.addWidget(b)
        self.hotkey_hint = QLabel()
        self.hotkey_hint.setObjectName("hint")
        self.hotkey_hint.setWordWrap(True)
        self.hotkey_hint.setContentsMargins(10, 8, 6, 0)
        sl.addWidget(self.hotkey_hint)

        # ── список
        center = QWidget()
        center.setObjectName("center")
        center.setAttribute(Qt.WA_StyledBackground)
        cl = QVBoxLayout(center)
        cl.setContentsMargins(14, 16, 14, 10)
        cl.setSpacing(10)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск…   Ctrl+F")
        self.search.addAction(icon("search", FAINT), QLineEdit.LeadingPosition)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda: self.search_timer.start())
        self.search_timer = QTimer(self, singleShot=True, interval=150)
        self.search_timer.timeout.connect(self.refresh)
        new_note = set_icon(QPushButton(" Заметка"), "plus", "#ffffff")
        new_note.setObjectName("primary")
        new_note.setCursor(Qt.PointingHandCursor)
        new_note.clicked.connect(self.new_note)
        clear_btn = set_icon(QPushButton(), "trash")
        clear_btn.setObjectName("danger")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setToolTip("Очистить историю (закреплённое, заметки и папки останутся)")
        clear_btn.clicked.connect(lambda: self.ctl.clear_history(self))
        top.addWidget(self.search, 1)
        top.addWidget(new_note)
        top.addWidget(clear_btn)
        cl.addLayout(top)
        self.list = QListWidget()
        self.list.setItemDelegate(ItemDelegate(ctl, 64, self.list))
        self.list.setMouseTracking(True)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list.setUniformItemSizes(True)
        self.list.currentItemChanged.connect(self.on_item_changed)
        self.list.itemDoubleClicked.connect(lambda it: self.ctl.copy_item(it.data(Qt.UserRole), notify=True))
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.item_menu)
        cl.addWidget(self.list, 1)
        self.count = QLabel()
        self.count.setObjectName("hint")
        cl.addWidget(self.count)

        # ── предпросмотр
        self.preview = Preview(ctl)

        split.addWidget(side)
        split.addWidget(center)
        split.addWidget(self.preview)
        split.setSizes([220, 430, 470])
        split.setCollapsible(1, False)

        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: (self.search.setFocus(), self.search.selectAll()))
        QShortcut(QKeySequence(Qt.Key_Delete), self.list, activated=self.delete_current)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=lambda: current_id(self.list) and
                  self.ctl.toggle_pin(current_id(self.list)))
        QShortcut(QKeySequence(Qt.Key_Return), self.list,
                  activated=lambda: current_id(self.list) and self.ctl.copy_item(current_id(self.list), notify=True))
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.new_note)

        self.build_side()
        self.refresh()
        style_window(self)

    # боковая панель
    def build_side(self):
        cur = self.view
        self.side.blockSignals(True)
        self.side.clear()
        target = None
        for label, view, ic in FIXED_VIEWS:
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, view)
            it.setData(SIDE_ICON, ic)
            self.side.addItem(it)
            if view == cur:
                target = it
        folders = self.ctl.store.folders()
        hdr = QListWidgetItem("ПАПКИ")
        hdr.setFlags(Qt.NoItemFlags)
        hdr.setData(SIDE_HDR, True)
        self.side.addItem(hdr)
        if not folders:
            e = QListWidgetItem("Пока нет папок")
            e.setFlags(Qt.NoItemFlags)
            self.side.addItem(e)
        for fo in folders:
            it = QListWidgetItem(fo["name"])
            view = ("folder", fo["id"])
            it.setData(Qt.UserRole, view)
            it.setData(SIDE_ICON, "folder")
            self.side.addItem(it)
            if view == cur:
                target = it
        if target is None:
            target = self.side.item(0)
            self.view = ("all",)
        self.side.setCurrentItem(target)
        self.side.blockSignals(False)
        self.update_counts()

    def update_counts(self):
        c = self.ctl.store.counts()
        for i in range(self.side.count()):
            it = self.side.item(i)
            v = it.data(Qt.UserRole)
            if v:
                it.setData(SIDE_COUNT, c.get(tuple(v), 0))

    def on_view_changed(self, it, _prev=None):
        if it and it.data(Qt.UserRole):
            self.view = tuple(it.data(Qt.UserRole))
            self.refresh()

    def side_menu(self, pos):
        it = self.side.itemAt(pos)
        if not it or not it.data(Qt.UserRole) or it.data(Qt.UserRole)[0] != "folder":
            return
        fid = it.data(Qt.UserRole)[1]
        m = QMenu(self)
        m.addAction("Переименовать").triggered.connect(lambda: self.ctl.rename_folder(fid, self))
        m.addAction("Удалить папку").triggered.connect(lambda: self.ctl.delete_folder(fid, self))
        m.exec(self.side.mapToGlobal(pos))

    # список
    def refresh(self):
        keep = current_id(self.list)
        rows = self.ctl.store.query(self.view, self.search.text().strip())
        fill_list(self.list, rows, keep)
        n = len(rows)
        self.count.setText(f"{n} элем." + ("   ·   запись на паузе" if self.ctl.paused else ""))
        self.update_counts()

    def on_item_changed(self, it, _prev=None):
        self.preview.show_item(it.data(Qt.UserRole) if it else None)

    def item_menu(self, pos):
        it = self.list.itemAt(pos)
        if not it:
            return
        self.ctl.item_context_menu(it.data(Qt.UserRole), self, self.list.mapToGlobal(pos))

    def delete_current(self):
        iid = current_id(self.list)
        if iid:
            row = self.list.currentRow()
            self.ctl.delete_item(iid)
            if self.list.count():
                self.list.setCurrentRow(min(row, self.list.count() - 1))

    def new_note(self):
        if self.view != ("notes",):
            for i in range(self.side.count()):
                if self.side.item(i).data(Qt.UserRole) == ("notes",):
                    self.side.setCurrentRow(i)
                    break
        iid = self.ctl.store.add("text", "", is_note=1, title="Новая заметка", h=make_hash("note", str(time.time())))
        self.ctl.changed.emit()
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == iid:
                self.list.setCurrentRow(i)
        self.preview.title.setFocus()
        self.preview.title.selectAll()

    def closeEvent(self, e):
        if QSystemTrayIcon.isSystemTrayAvailable():
            e.ignore()
            self.hide()
            self.ctl.tray_hint_once()
        else:
            e.accept()
            QApplication.quit()


# ───────────────────────────── Быстрая панель ─────────────────────────────
class QuickPanel(QWidget):
    def __init__(self, ctl):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.ctl = ctl
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(460, 600)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        frame = QFrame()
        frame.setObjectName("quick")
        sh = QGraphicsDropShadowEffect(blurRadius=28, xOffset=0, yOffset=6)
        sh.setColor(QColor(0, 0, 0, 160))
        frame.setGraphicsEffect(sh)
        outer.addWidget(frame)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 12, 12, 10)
        lay.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по буферу…")
        self.search.addAction(icon("search", FAINT), QLineEdit.LeadingPosition)
        lay.addWidget(self.search)

        tabs = QHBoxLayout()
        self.group = QButtonGroup(self)
        for i, name in enumerate(("Все", "Закреплённые", "Заметки")):
            b = QPushButton(name)
            b.setObjectName("tab")
            b.setCheckable(True)
            b.setFocusPolicy(Qt.NoFocus)
            self.group.addButton(b, i)
            tabs.addWidget(b)
        tabs.addStretch()
        self.group.button(0).setChecked(True)
        self.group.idClicked.connect(lambda _: self.refresh())
        lay.addLayout(tabs)

        self.list = QListWidget()
        self.list.setItemDelegate(ItemDelegate(ctl, 56, self.list))
        self.list.setMouseTracking(True)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list.setUniformItemSizes(True)
        self.list.itemActivated.connect(lambda it: self.ctl.paste_item(it.data(Qt.UserRole)))
        self.list.itemDoubleClicked.connect(lambda it: self.ctl.paste_item(it.data(Qt.UserRole)))
        self.list.currentItemChanged.connect(self.update_prev)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.item_menu)
        lay.addWidget(self.list, 1)

        self.prev = QLabel()
        self.prev.setObjectName("quickPrev")
        self.prev.setWordWrap(True)
        self.prev.setTextFormat(Qt.PlainText)
        self.prev.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.prev.setFixedHeight(110)
        lay.addWidget(self.prev)

        hint = QLabel("Enter — вставить  ·  Ctrl+P — закрепить  ·  Tab — вкладки  ·  Esc — закрыть")
        hint.setObjectName("hint")
        hint.setAlignment(Qt.AlignCenter)
        lay.addWidget(hint)

        self.search.textChanged.connect(self.refresh)
        self.search.installEventFilter(self)
        self.list.installEventFilter(self)
        self.menu_open = False

    def refresh(self):
        view = [("all",), ("pinned",), ("notes",)][max(0, self.group.checkedId())]
        rows = self.ctl.store.query(view, self.search.text().strip(), limit=300)
        fill_list(self.list, rows)

    def update_prev(self, it, _prev=None):
        iid = it.data(Qt.UserRole) if it else None
        r = self.ctl.store.get(iid) if iid else None
        self.prev.setPixmap(QPixmap())
        if not r:
            self.prev.setText("Здесь пока пусто — скопируйте что-нибудь (Ctrl+C)")
            return
        if r["kind"] == "image":
            self.prev.setPixmap(hidpi_pixmap(QImage.fromData(r["image"]), self.prev.width() - 16, 94,
                                             self.prev.devicePixelRatioF()))
        elif r["kind"] == "color":
            c = parse_color(r["text"]) or QColor("black")
            pm = QPixmap(self.prev.width() - 16, 94)
            pm.fill(c)
            self.prev.setPixmap(pm)
        else:
            t = (r["text"] or "")[:700]
            self.prev.setText(t if t.strip() else "(пустая заметка)")

    def popup(self):
        self.search.clear()
        self.refresh()
        pos = QCursor.pos()
        scr = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        g = scr.availableGeometry()
        x = max(g.left(), min(pos.x() - 30, g.right() - self.width()))
        y = max(g.top(), min(pos.y() - 30, g.bottom() - self.height()))
        self.move(x, y)
        fade_in_window(self)
        self.raise_()
        self.activateWindow()
        if IS_WIN:
            user32.SetForegroundWindow(int(self.winId()))
        self.search.setFocus()

    def item_menu(self, pos):
        it = self.list.itemAt(pos)
        if not it:
            return
        self.menu_open = True
        self.ctl.item_context_menu(it.data(Qt.UserRole), self, self.list.mapToGlobal(pos), quick=True)
        self.menu_open = False
        self.activateWindow()

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.KeyPress:
            k, mods = ev.key(), ev.modifiers()
            if k == Qt.Key_Escape:
                self.hide()
                return True
            if k in (Qt.Key_Return, Qt.Key_Enter):
                iid = current_id(self.list)
                if iid:
                    self.ctl.paste_item(iid)
                return True
            if k in (Qt.Key_Down, Qt.Key_Up, Qt.Key_PageDown, Qt.Key_PageUp) and obj is self.search:
                step = {Qt.Key_Down: 1, Qt.Key_Up: -1, Qt.Key_PageDown: 8, Qt.Key_PageUp: -8}[k]
                n = self.list.count()
                if n:
                    self.list.setCurrentRow(max(0, min(n - 1, self.list.currentRow() + step)))
                return True
            if k == Qt.Key_P and mods & Qt.ControlModifier:
                iid = current_id(self.list)
                if iid:
                    self.ctl.toggle_pin(iid)
                return True
            if k in (Qt.Key_Tab, Qt.Key_Backtab):
                i = (self.group.checkedId() + (-1 if k == Qt.Key_Backtab else 1)) % 3
                self.group.button(i).setChecked(True)
                self.refresh()
                return True
            if k == Qt.Key_Delete and obj is self.list:
                iid = current_id(self.list)
                if iid:
                    self.ctl.delete_item(iid)
                return True
        return super().eventFilter(obj, ev)

    def changeEvent(self, e):
        if e.type() == QEvent.ActivationChange and not self.isActiveWindow():
            QTimer.singleShot(150, self._maybe_hide)
        super().changeEvent(e)

    def _maybe_hide(self):
        if self.isVisible() and not self.isActiveWindow() and not self.menu_open \
                and QApplication.activeModalWidget() is None:
            self.hide()


def fade_in_window(w, ms=140):
    """Показать всплывающее окно с плавным проявлением."""
    old = getattr(w, "_fade", None)
    if old:
        old.stop()
    w.setWindowOpacity(0.0)
    w.show()
    a = QPropertyAnimation(w, b"windowOpacity", w)
    a.setDuration(ms)
    a.setEasingCurve(QEasingCurve.OutCubic)
    a.setStartValue(0.0)
    a.setEndValue(1.0)
    a.start()
    w._fade = a


# ───────────────────────────── Компактное меню (как Ditto) ─────────────────────────────
def short_time(ts):
    if not ts:
        return ""
    d = time.time() - ts
    if d < 60:
        return "сейчас"
    if d < 3600:
        return f"{int(d // 60)} мин"
    dt = datetime.datetime.fromtimestamp(ts)
    today = datetime.date.today()
    if dt.date() == today:
        return dt.strftime("%H:%M")
    if dt.date() == today - datetime.timedelta(days=1):
        return "вчера"
    return dt.strftime("%d.%m")


def draw_item_icon(p, ctl, d, ir, radius, base_font=None):
    ipath = QPainterPath()
    ipath.addRoundedRect(ir, radius, radius)
    kind = d["kind"]
    if kind == "color":
        p.fillPath(ipath, parse_color(d["text"]) or QColor("black"))
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawPath(ipath)
    elif kind == "image":
        p.fillPath(ipath, QColor("#0a0b0e"))
        pm = ctl.thumb(d["id"])
        if pm is not None and not pm.isNull():
            sw, sh, ar = pm.width(), pm.height(), ir.width() / ir.height()
            if sw / sh > ar:  # обрезать по центру, без растягивания
                src = QRectF((sw - sh * ar) / 2, 0, sh * ar, sh)
            else:
                src = QRectF(0, (sh - sw / ar) / 2, sw, sw / ar)
            p.save()
            p.setClipPath(ipath)
            p.drawPixmap(ir, pm, src)
            p.restore()
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(ipath)
    else:
        k = "note" if d["is_note"] else kind
        c = QColor(KIND_COLOR.get(k, MUTED))
        bg = QColor(c)
        bg.setAlpha(30)
        p.fillPath(ipath, bg)
        sz = ir.height() * 0.5
        draw_icon(p, KIND_ICON.get(k, "type"), QRectF(ir.center().x() - sz / 2, ir.center().y() - sz / 2, sz, sz),
                  c.name(), 1.9)


class CompactDelegate(QStyledItemDelegate):
    H = 38

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl

    def sizeHint(self, option, index):
        return QSize(200, self.H)

    def paint(self, p, opt, index):
        d = index.data(ROLE)
        if not d:
            return
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(opt.rect.adjusted(4, 1, -4, -1))
        sel = bool(opt.state & QStyle.StateFlag.State_Selected)
        hov = bool(opt.state & QStyle.StateFlag.State_MouseOver)
        if sel or hov:
            bg = QPainterPath()
            bg.addRoundedRect(r, 8, 8)
            p.fillPath(bg, QColor(123, 108, 255, 38) if sel else QColor(255, 255, 255, 10))
        if sel:
            bar = QPainterPath()
            bar.addRoundedRect(QRectF(r.left() + 1, r.top() + 9, 3, r.height() - 18), 1.5, 1.5)
            p.fillPath(bar, QColor(ACCENT))

        row = index.row()
        nr = QRectF(r.left() + 8, r.center().y() - 10, 18, 20)
        if row < 10:
            f = QFont(opt.font)
            f.setPointSizeF(8.5)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor(ACCENT_HI if sel else FAINT))
            p.drawText(nr, Qt.AlignCenter, str((row + 1) % 10))

        ir = QRectF(nr.right() + 6, r.center().y() - 12, 24, 24)
        draw_item_icon(p, self.ctl, d, ir, 6, opt.font)

        f2 = QFont(opt.font)
        f2.setPointSizeF(8)
        fm2 = QFontMetrics(f2)
        right = short_time(d["used"])
        rw = fm2.horizontalAdvance(right) + 4
        p.setFont(f2)
        p.setPen(QColor(FAINT))
        p.drawText(QRectF(r.right() - rw - 10, r.top(), rw, r.height()), Qt.AlignRight | Qt.AlignVCenter, right)
        if d["pinned"]:
            rw += 18
            draw_icon(p, "pin", QRectF(r.right() - rw - 8, r.center().y() - 7, 14, 14), PIN)

        tx = ir.right() + 10
        tw = r.right() - rw - 18 - tx
        f1 = QFont(opt.font)
        f1.setPointSizeF(9.5)
        fm1 = QFontMetrics(f1)
        p.setFont(f1)
        p.setPen(QColor("white" if sel else TEXT))
        p.drawText(QRectF(tx, r.top(), tw, r.height()), Qt.AlignLeft | Qt.AlignVCenter,
                   fm1.elidedText(item_title(d), Qt.ElideRight, int(tw)))
        p.restore()


class PreviewBubble(QWidget):
    """Всплывающий предпросмотр рядом с меню — не забирает фокус."""
    MAXW = 380

    def __init__(self, ctl):
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.ctl = ctl
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        frame = QFrame()
        frame.setObjectName("bubble")
        sh = QGraphicsDropShadowEffect(blurRadius=24, xOffset=0, yOffset=5)
        sh.setColor(QColor(0, 0, 0, 150))
        frame.setGraphicsEffect(sh)
        outer.addWidget(frame)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)
        self.head = QLabel()
        self.head.setObjectName("hint")
        self.body = QLabel()
        self.body.setWordWrap(True)
        self.body.setTextFormat(Qt.PlainText)
        self.body.setStyleSheet(f"font-family: {MONO}; font-size: 9pt; color: #d6d6de;")
        self.body.setMaximumWidth(self.MAXW)
        self.pic = QLabel()
        lay.addWidget(self.head)
        lay.addWidget(self.body)
        lay.addWidget(self.pic)
        outer.setSizeConstraint(QVBoxLayout.SetFixedSize)

    def set_item(self, r):
        self.body.setText("")
        self.pic.setPixmap(QPixmap())
        kind = r["kind"]
        self.body.setVisible(kind not in ("image", "color"))
        self.pic.setVisible(kind in ("image", "color"))
        head = ["Заметка" if r["is_note"] else KIND_LABEL.get(kind, kind), reltime(r["used"])]
        if kind == "image":
            self.pic.setPixmap(hidpi_pixmap(QImage.fromData(r["image"]), self.MAXW, 280,
                                            self.pic.devicePixelRatioF()))
            head.append(f"{r['text']} · {(r['isize'] or 0) // 1024} КБ")
        elif kind == "color":
            c = parse_color(r["text"]) or QColor("black")
            pm = QPixmap(220, 90)
            pm.fill(Qt.transparent)
            pp = QPainter(pm)
            pp.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, 220, 90), 10, 10)
            pp.fillPath(path, c)
            pp.end()
            self.pic.setPixmap(pm)
            head.append(f"{c.name().upper()}  ·  rgb({c.red()}, {c.green()}, {c.blue()})")
        else:
            text = r["text"] or ""
            lines = text.splitlines()
            shown = "\n".join(lines[:18])[:1200]
            if len(lines) > 18 or len(text) > 1200:
                shown += "\n…"
            self.body.setText(shown if shown.strip() else "(пусто)")
            head.append(f"{len(text)} симв.")
        if r["title"]:
            head.insert(0, r["title"])
        self.head.setText("  ·  ".join(head))
        self.layout().activate()


class CompactMenu(QWidget):
    VIEWS = [("all",), ("pinned",), ("notes",)]
    MAX_ROWS = 12

    def __init__(self, ctl):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.ctl = ctl
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(440)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        frame = QFrame()
        frame.setObjectName("compact")
        sh = QGraphicsDropShadowEffect(blurRadius=26, xOffset=0, yOffset=6)
        sh.setColor(QColor(0, 0, 0, 170))
        frame.setGraphicsEffect(sh)
        outer.addWidget(frame)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(8, 8, 8, 6)
        lay.setSpacing(6)

        self.search = QLineEdit()
        self.search.setObjectName("compactSearch")
        self.search.setPlaceholderText("Поиск клипов…")
        self.search.addAction(icon("search", FAINT), QLineEdit.LeadingPosition)
        lay.addWidget(self.search)

        self.list = QListWidget()
        self.list.setItemDelegate(CompactDelegate(ctl, self.list))
        self.list.setMouseTracking(True)
        self.list.setUniformItemSizes(True)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.itemClicked.connect(lambda it: self.ctl.paste_item(it.data(Qt.UserRole)))
        self.list.itemEntered.connect(lambda it: self.list.setCurrentItem(it))
        self.list.currentItemChanged.connect(lambda *_: self.prev_timer.start())
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.item_menu)
        lay.addWidget(self.list)

        self.empty = QLabel("Пока пусто — скопируйте что-нибудь")
        self.empty.setObjectName("hint")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setMinimumHeight(60)
        lay.addWidget(self.empty)

        foot = QHBoxLayout()
        foot.setSpacing(2)
        chips = QWidget()
        chips_lay = QHBoxLayout(chips)
        chips_lay.setContentsMargins(0, 0, 0, 0)
        chips_lay.setSpacing(2)
        self.pill = QFrame(chips)  # подсветка выбранной вкладки, плавно переезжает под кнопками
        self.pill.setObjectName("chipPill")
        self.pill.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.pill_anim = QPropertyAnimation(self.pill, b"geometry", self)
        self.pill_anim.setDuration(220)
        self.pill_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.group = QButtonGroup(self)
        for i, name in enumerate(("Все", "Закреплённые", "Заметки")):
            b = QPushButton(name)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setFocusPolicy(Qt.NoFocus)
            b.setCursor(Qt.PointingHandCursor)
            self.group.addButton(b, i)
            chips_lay.addWidget(b)
        foot.addWidget(chips)
        self.group.button(0).setChecked(True)
        self.group.idClicked.connect(lambda _: self.refresh(tab=True))

        # высота списка меняется плавно, а не скачком
        self.h_anim = QVariantAnimation(self)
        self.h_anim.setDuration(200)
        self.h_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.h_anim.valueChanged.connect(lambda v: (self.list.setFixedHeight(int(v)), self.fit()))
        self.fade_anim = None
        foot.addStretch()
        hint = QLabel("1–0 вставить · Tab режим · Esc")
        hint.setObjectName("hint")
        foot.addWidget(hint)
        lay.addLayout(foot)

        self.bubble = PreviewBubble(ctl)
        self.prev_timer = QTimer(self, singleShot=True, interval=220)
        self.prev_timer.timeout.connect(self.show_bubble)

        self.search.textChanged.connect(self.refresh)
        self.search.installEventFilter(self)
        self.list.installEventFilter(self)
        self.menu_open = False

    def view(self):
        return self.VIEWS[max(0, self.group.checkedId())]

    def refresh(self, keep=None, tab=False):
        rows = self.ctl.store.query(self.view(), self.search.text().strip(), limit=300)
        was_shown = self.isVisible() and self.list.isVisible()
        fill_list(self.list, rows, keep)
        n = len(rows)
        self.empty.setVisible(n == 0)
        self.list.setVisible(n > 0)
        target = min(n, self.MAX_ROWS) * CompactDelegate.H + 4
        self.h_anim.stop()
        if was_shown and n and self.list.height() != target:
            self.h_anim.setStartValue(self.list.height())
            self.h_anim.setEndValue(target)
            self.h_anim.start()
        else:
            self.list.setFixedHeight(target)
            self.fit()
        if tab and n and self.isVisible():
            self.fade_in_list()
        self.move_pill(self.isVisible())
        if not n:
            self.bubble.hide()

    def move_pill(self, animate):
        b = self.group.checkedButton()
        if not b:
            return
        g = b.geometry()
        if not animate or not self.pill.isVisible() or self.pill.width() < 2:
            self.pill_anim.stop()
            self.pill.setGeometry(g)
            self.pill.show()
            self.pill.lower()
        elif g != self.pill_anim.endValue() or self.pill_anim.state() != QPropertyAnimation.Running:
            self.pill_anim.stop()
            self.pill_anim.setStartValue(self.pill.geometry())
            self.pill_anim.setEndValue(g)
            self.pill_anim.start()

    def fade_in_list(self):
        """Строки новой вкладки плавно проявляются."""
        if self.fade_anim:
            self.fade_anim.stop()
        eff = QGraphicsOpacityEffect(self.list)
        eff.setOpacity(0.0)
        self.list.setGraphicsEffect(eff)
        a = QVariantAnimation(self)
        a.setDuration(220)
        a.setEasingCurve(QEasingCurve.OutCubic)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.valueChanged.connect(eff.setOpacity)
        a.finished.connect(lambda: self.list.graphicsEffect() is eff and self.list.setGraphicsEffect(None))
        self.fade_anim = a
        a.start()

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, lambda: self.move_pill(False))

    def fit(self):
        """Сразу подогнать высоту под список: пересчитать раскладку, а не ждать её отложенного обновления."""
        for lay in (self.list.parentWidget().layout(), self.layout()):
            lay.invalidate()
            lay.activate()
        h = self.sizeHint().height()
        if self.height() != h:
            self.resize(self.width(), h)
        if self.isVisible():  # не вылезать за низ экрана, когда список вырос
            g = self.screen().availableGeometry()
            if self.geometry().bottom() > g.bottom():
                self.move(self.x(), max(g.top(), g.bottom() - h))
        if self.bubble.isVisible():
            self.prev_timer.start()

    def popup(self):
        self.search.clear()
        self.group.button(0).setChecked(True)
        self.refresh()
        pos = QCursor.pos()
        scr = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        g = scr.availableGeometry()
        h = self.sizeHint().height()
        x = max(g.left(), min(pos.x() - 12, g.right() - self.width()))
        y = max(g.top(), min(pos.y() - 12, g.bottom() - h))
        self.move(x, y)
        fade_in_window(self)
        self.raise_()
        self.activateWindow()
        if IS_WIN:
            user32.SetForegroundWindow(int(self.winId()))
        self.search.setFocus()

    def show_bubble(self):
        it = self.list.currentItem()
        if not self.isVisible() or not it:
            self.bubble.hide()
            return
        r = self.ctl.store.get(it.data(Qt.UserRole))
        if not r:
            self.bubble.hide()
            return
        self.bubble.set_item(r)
        rect = self.list.visualItemRect(it)
        top = self.list.viewport().mapToGlobal(rect.topLeft()).y() - 14
        scr = self.screen().availableGeometry()
        bw, bh = self.bubble.width(), self.bubble.height()
        x = self.geometry().right() - 10
        if x + bw > scr.right():
            x = self.geometry().left() - bw + 10
        y = max(scr.top(), min(top, scr.bottom() - bh))
        self.bubble.move(x, y)
        self.bubble.show()

    def item_menu(self, pos):
        it = self.list.itemAt(pos)
        if not it:
            return
        self.menu_open = True
        self.bubble.hide()
        self.ctl.item_context_menu(it.data(Qt.UserRole), self, self.list.mapToGlobal(pos), quick=True)
        self.menu_open = False
        if self.isVisible():
            self.activateWindow()
            self.search.setFocus()

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.KeyPress:
            k, mods = ev.key(), ev.modifiers()
            if k == Qt.Key_Escape:
                self.hide()
                return True
            if Qt.Key_0 <= k <= Qt.Key_9 and (not self.search.text() or mods & Qt.ControlModifier):
                idx = 9 if k == Qt.Key_0 else k - Qt.Key_1
                if idx < self.list.count():
                    self.ctl.paste_item(self.list.item(idx).data(Qt.UserRole))
                return True
            if k in (Qt.Key_Return, Qt.Key_Enter):
                iid = current_id(self.list)
                if iid:
                    self.ctl.paste_item(iid)
                return True
            if k in (Qt.Key_Down, Qt.Key_Up, Qt.Key_PageDown, Qt.Key_PageUp, Qt.Key_Home, Qt.Key_End) \
                    and obj is self.search:
                n = self.list.count()
                if n:
                    cur = self.list.currentRow()
                    new = {Qt.Key_Down: cur + 1, Qt.Key_Up: cur - 1, Qt.Key_PageDown: cur + 10,
                           Qt.Key_PageUp: cur - 10, Qt.Key_Home: 0, Qt.Key_End: n - 1}[k]
                    if k == Qt.Key_Down and cur == n - 1:
                        new = 0
                    if k == Qt.Key_Up and cur == 0:
                        new = n - 1
                    self.list.setCurrentRow(max(0, min(n - 1, new)))
                return True
            if k == Qt.Key_P and mods & Qt.ControlModifier:
                iid = current_id(self.list)
                if iid:
                    self.ctl.toggle_pin(iid)
                return True
            if k in (Qt.Key_Tab, Qt.Key_Backtab):
                i = (self.group.checkedId() + (-1 if k == Qt.Key_Backtab else 1)) % 3
                self.group.button(i).setChecked(True)
                self.refresh(tab=True)
                return True
            if k == Qt.Key_Delete and (obj is self.list or not self.search.text()):
                iid = current_id(self.list)
                if iid:
                    row = self.list.currentRow()
                    self.ctl.delete_item(iid)
                    if self.list.count():
                        self.list.setCurrentRow(min(row, self.list.count() - 1))
                return True
        return super().eventFilter(obj, ev)

    def hideEvent(self, e):
        self.prev_timer.stop()
        self.bubble.hide()
        super().hideEvent(e)

    def changeEvent(self, e):
        if e.type() == QEvent.ActivationChange and not self.isActiveWindow():
            QTimer.singleShot(150, self._maybe_hide)
        super().changeEvent(e)

    def _maybe_hide(self):
        if self.isVisible() and not self.isActiveWindow() and not self.menu_open \
                and QApplication.activeModalWidget() is None:
            self.hide()


# ───────────────────────────── Настройки ─────────────────────────────
class OcrDialog(QDialog):
    def __init__(self, ctl, iid, text, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.iid = iid
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("Текст с картинки")
        self.resize(560, 420)
        style_window(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)
        hint = QLabel("Выделите нужный кусок и нажмите Ctrl+C — или скопируйте всё сразу. Текст можно поправить.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.text = QPlainTextEdit(text)
        self.text.setStyleSheet(f"font-family: {MONO}; font-size: 10pt;")
        lay.addWidget(self.text, 1)
        row = QHBoxLayout()
        copy = set_icon(QPushButton("  Копировать всё"), "copy", "#ffffff")
        copy.setObjectName("primary")
        note = set_icon(QPushButton("  В мои заметки"), "note")
        close = QPushButton("Закрыть")
        close.setObjectName("ghost")
        row.addWidget(copy)
        row.addWidget(note)
        row.addStretch()
        row.addWidget(close)
        lay.addLayout(row)
        copy.clicked.connect(self.copy_all)
        note.clicked.connect(self.to_note)
        close.clicked.connect(self.close)

    def copy_all(self):
        QGuiApplication.clipboard().setText(self.text.toPlainText())
        self.close()

    def to_note(self):
        t = self.text.toPlainText()
        if t.strip():
            r = self.ctl.store.get(self.iid)
            title = f"Текст с картинки {r['text']}" if r else "Текст с картинки"
            self.ctl.store.add("text", t, is_note=1, title=title)
            self.ctl.changed.emit()
        self.close()


# ───────────────────────────── Скриншоты ─────────────────────────────
def default_shot_dir():
    pics = QStandardPaths.writableLocation(QStandardPaths.PicturesLocation) or os.path.expanduser("~")
    return os.path.join(pics, APP)


UPLOADERS = {  # ключ: (название, подсказка для поля ключа или None)
    "pixhost": ("pixhost.to — без регистрации", None),
    "freeimage": ("freeimage.host — без регистрации", None),
    "catbox": ("catbox.moe — без регистрации", None),
    "imgur": ("Imgur", "Client-ID с api.imgur.com/oauth2/addclient"),
    "imgbb": ("ImgBB", "API-ключ с api.imgbb.com"),
}


def log_upload_error(host, msg, code=None):
    """Ошибки загрузки — в upload.log рядом с базой, чтобы потом было видно, что ответил сайт."""
    try:
        path = os.path.join(data_dir(), "upload.log")
        if os.path.exists(path) and os.path.getsize(path) > 200_000:
            os.replace(path, path + ".old")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {host}  HTTP {code}  {msg}\n")
    except OSError:
        pass


FREEIMAGE_KEY = "6d207e02198a847aa98d0a2a901485a5"  # общий публичный ключ из документации freeimage.host
DEFAULT_UPLOADER = "pixhost"


class Uploader(QObject):
    """Заливает картинку на хостинг и возвращает прямую ссылку — как ShareX."""
    done = Signal(int, str, str, str)  # id, ссылка, ссылка для удаления, ошибка

    def __init__(self, store):
        super().__init__()
        self.store = store
        self.nam = QNetworkAccessManager(self)

    def host(self):
        h = self.store.get_setting("up_host", DEFAULT_UPLOADER)
        return h if h in UPLOADERS else DEFAULT_UPLOADER

    def upload(self, iid, png, name, host=None, errors=None):
        host = host or self.host()
        errors = errors if errors is not None else []
        key = (self.store.get_setting(f"up_key_{host}", "") or "").strip()
        if UPLOADERS[host][1] and not key:
            QTimer.singleShot(0, lambda: self.done.emit(
                iid, "", "", f"Для {UPLOADERS[host][0]} нужен ключ — укажите его в настройках"))
            return
        mp = QHttpMultiPart(QHttpMultiPart.FormDataType)

        def field(n, v):
            part = QHttpPart()
            part.setHeader(QNetworkRequest.ContentDispositionHeader, f'form-data; name="{n}"')
            part.setBody(v.encode())
            mp.append(part)

        def file(n):
            part = QHttpPart()
            part.setHeader(QNetworkRequest.ContentTypeHeader, "image/png")
            part.setHeader(QNetworkRequest.ContentDispositionHeader, f'form-data; name="{n}"; filename="{name}"')
            part.setBody(png)
            mp.append(part)

        if host == "imgur":
            req = QNetworkRequest(QUrl("https://api.imgur.com/3/image"))
            req.setRawHeader(b"Authorization", f"Client-ID {key}".encode())
            field("type", "file")
            file("image")
        elif host == "imgbb":
            req = QNetworkRequest(QUrl("https://api.imgbb.com/1/upload?key=" + key))
            file("image")
        elif host == "freeimage":
            req = QNetworkRequest(QUrl(f"https://freeimage.host/api/1/upload?key={FREEIMAGE_KEY}&format=json"))
            field("action", "upload")
            file("source")
        elif host == "pixhost":
            req = QNetworkRequest(QUrl("https://api.pixhost.to/images"))
            req.setRawHeader(b"Accept", b"application/json")
            file("img")
            field("content_type", "0")
            field("include_manage_url", "1")
        else:
            req = QNetworkRequest(QUrl("https://catbox.moe/user/api.php"))
            field("reqtype", "fileupload")
            file("fileToUpload")
        req.setHeader(QNetworkRequest.UserAgentHeader, f"{APP}/{APP_VERSION}")
        req.setTransferTimeout(90000)
        reply = self.nam.post(req, mp)
        mp.setParent(reply)
        reply.finished.connect(lambda: self.finished(reply, iid, host, png, name, errors))

    def finished(self, reply, iid, host, png=b"", name="", errors=None):
        body = bytes(reply.readAll()).decode("utf-8", "replace").strip()
        net_err = reply.errorString() if reply.error() else ""
        try:
            reply_code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        except Exception:
            reply_code = None
        reply.deleteLater()
        try:
            if host == "catbox":
                if not body.startswith("https://"):
                    raise RuntimeError(body[:200] or net_err)
                url, dele = body, ""
            elif host == "freeimage":
                d = json.loads(body) if body.startswith("{") else {}
                img = d.get("image") or {}
                url = img.get("url") or ""
                if not url.startswith("https://"):
                    e = d.get("error")
                    raise RuntimeError(str((e.get("message") if isinstance(e, dict) else e) or net_err or body[:200]))
                dele = img.get("delete_url", "")
            elif host == "pixhost":
                d = json.loads(body) if body.startswith("{") else {}
                th, show = d.get("th_url") or "", d.get("show_url") or ""
                if not show.startswith("https://"):
                    raise RuntimeError(str(d.get("error") or d.get("message") or net_err or body[:200]))
                # прямая ссылка на картинку: t1.pixhost.to/thumbs/… → img1.pixhost.to/images/…
                m = re.match(r"https://t(\d+)\.([^/]+)/thumbs/(.+)$", th)
                url = f"https://img{m.group(1)}.{m.group(2)}/images/{m.group(3)}" if m else show
                dele = d.get("manage_url", "")
            else:
                d = json.loads(body) if body.startswith("{") else {}
                if not d.get("success"):
                    e = (d.get("data") or {}).get("error") if host == "imgur" else (d.get("error") or {}).get("message")
                    raise RuntimeError(str((e or {}).get("message", e) if isinstance(e, dict) else e or net_err or body[:200]))
                data = d["data"]
                url = data.get("link") or data.get("url")
                dele = f"https://imgur.com/delete/{data['deletehash']}" if host == "imgur" else data.get("delete_url", "")
        except Exception as e:
            errors = (errors or []) + [(host, str(e) or "нет ответа от сервера")]
            log_upload_error(host, errors[-1][1], reply_code)
            tried = {h for h, _ in errors}
            spare = next((h for h, (_, need_key) in UPLOADERS.items() if need_key is None and h not in tried), None)
            if spare and png:  # хостинг лёг — молча пробуем другой без регистрации
                self.upload(iid, png, name, spare, errors)
                return
            msg = errors[0][1] if len(errors) == 1 else \
                "; ".join(f"{UPLOADERS[h][0].split(' ')[0]}: {m}" for h, m in errors)
            self.done.emit(iid, "", "", msg)
            return
        self.done.emit(iid, url, dele or "", "")


# ── инструменты рисования на скриншоте (как в ShareX / Lightshot)
SHOT_COLORS = ["#ff3b30", "#ff9500", "#ffcc00", "#34c759", "#0a84ff", "#af52de", "#ffffff", "#111111"]
SHOT_SIZES = {"S": 3, "M": 5, "L": 9}  # толщина линии в логических пикселях
SHOT_FONT = {"S": 16, "M": 24, "L": 36}  # размер текста
SHOT_TOOLS = [  # ключ, значок, подсказка, клавиша
    ("pen", "✏", "Карандаш", Qt.Key_P),
    ("marker", "🖍", "Маркер-выделитель", Qt.Key_M),
    ("line", "╱", "Линия", Qt.Key_L),
    ("arrow", "➜", "Стрелка", Qt.Key_A),
    ("rect", "▭", "Прямоугольник", Qt.Key_R),
    ("ellipse", "◯", "Эллипс", Qt.Key_E),
    ("text", "T", "Текст", Qt.Key_T),
    ("step", "①", "Нумерация шагов", Qt.Key_N),
    ("pixel", "░", "Скрыть (пикселизация)", Qt.Key_B),
    ("eraser", "⌫", "Ластик — стереть нарисованное", Qt.Key_X),
]


def shape_rect(sh):
    return QRectF(sh["pts"][0], sh["pts"][-1]).normalized()


def shape_path(sh):
    pts = sh["pts"]
    path = QPainterPath(pts[0])
    for q in pts[1:] or pts:
        path.lineTo(q)
    return path


def pixelate(img, rf):
    r = rf.toAlignedRect().intersected(img.rect())
    if r.width() < 2 or r.height() < 2:
        return None, r
    k = max(10, min(r.width(), r.height()) // 8)  # крупные блоки, чтобы текст точно не читался
    small = img.copy(r).scaled(max(1, r.width() // k), max(1, r.height() // k),
                               Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return small.scaled(r.width(), r.height(), Qt.IgnoreAspectRatio, Qt.FastTransformation), r


def text_font(sh):
    f = QFont("Segoe UI")
    f.setPixelSize(max(6, round(sh["fs"])))
    f.setBold(True)
    return f


def is_light(c):
    return QColor(c).lightness() > 170


def draw_shape(p, sh, base):
    """Рисует одну пометку в физических пикселях стоп-кадра."""
    t, c, w, pts = sh["t"], QColor(sh["c"]), sh["w"], sh["pts"]
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(Qt.NoBrush)
    if t == "pixel":
        img, r = sh.get("cache") or pixelate(base, shape_rect(sh))
        if img is not None:
            p.drawImage(r, img)
    elif t in ("pen", "marker"):
        if t == "marker":  # полупрозрачный «выделитель», не закрашивает текст
            p.setCompositionMode(QPainter.CompositionMode_Multiply)
            w *= 4
        p.setPen(QPen(c, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(shape_path(sh))
    elif t in ("line", "arrow"):
        a, b = pts[0], pts[-1]
        p.setPen(QPen(c, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        if t == "arrow":
            ang = math.atan2(b.y() - a.y(), b.x() - a.x())
            head = max(w * 4, 12 * sh["d"])
            left = QPointF(b.x() - head * math.cos(ang - 0.45), b.y() - head * math.sin(ang - 0.45))
            right = QPointF(b.x() - head * math.cos(ang + 0.45), b.y() - head * math.sin(ang + 0.45))
            end = QPointF(b.x() - head * 0.6 * math.cos(ang), b.y() - head * 0.6 * math.sin(ang))
            if math.hypot(b.x() - a.x(), b.y() - a.y()) > head * 0.6:
                p.drawLine(a, end)
            p.setPen(QPen(c, 1))
            p.setBrush(c)
            p.drawPolygon(QPolygonF([b, left, right]))
        else:
            p.drawLine(a, b)
    elif t in ("rect", "ellipse"):
        p.setPen(QPen(c, w, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
        r = shape_rect(sh)
        p.drawRect(r) if t == "rect" else p.drawEllipse(r)
    elif t == "step":
        rad = sh["w"] * 2 + 11 * sh["d"]
        p.setPen(QPen(QColor("white"), 2 * sh["d"]))
        p.setBrush(c)
        p.drawEllipse(pts[0], rad, rad)
        f = QFont("Segoe UI")
        f.setPixelSize(max(6, round(rad * 1.1)))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#111111" if is_light(c) else "white"))
        p.drawText(QRectF(pts[0].x() - rad, pts[0].y() - rad, rad * 2, rad * 2), Qt.AlignCenter, str(sh["n"]))
    elif t == "text":
        f = text_font(sh)
        path = QPainterPath()
        path.addText(pts[0] + QPointF(0, QFontMetrics(f).ascent()), f, sh["text"])
        p.strokePath(path, QPen(QColor(255, 255, 255, 200) if not is_light(c) else QColor(0, 0, 0, 170),
                                max(2.0, sh["fs"] / 9), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.fillPath(path, c)
    p.restore()


def shape_hit(sh, pt, tol):
    t = sh["t"]
    if t in ("pen", "marker", "line", "arrow"):
        st = QPainterPathStroker()
        st.setWidth(sh["w"] * (4 if t == "marker" else 1) + tol * 2)
        path = shape_path(sh) if t in ("pen", "marker") else QPainterPath(sh["pts"][0])
        if t in ("line", "arrow"):
            path.lineTo(sh["pts"][-1])
        return st.createStroke(path).contains(pt)
    if t == "step":
        rad = sh["w"] * 2 + 11 * sh["d"]
        return math.hypot(pt.x() - sh["pts"][0].x(), pt.y() - sh["pts"][0].y()) <= rad + tol
    if t == "text":
        fm = QFontMetrics(text_font(sh))
        return QRectF(sh["pts"][0].x(), sh["pts"][0].y(), fm.horizontalAdvance(sh["text"]),
                      fm.height()).adjusted(-tol, -tol, tol, tol).contains(pt)
    return shape_rect(sh).adjusted(-tol, -tol, tol, tol).contains(pt)


class ShotToolbar(QFrame):
    """Панель инструментов под выделенной областью."""

    def __init__(self, ov):
        super().__init__(ov)
        self.ov = ov
        self.setObjectName("shotbar")
        self.setStyleSheet(f"""
            #shotbar {{ background: #15161b; border: 1px solid #2c2d37; border-radius: 12px; }}
            #shotbar QToolButton {{ background: transparent; border: none; border-radius: 7px; color: {TEXT};
                                   font-size: 12pt; min-width: 32px; min-height: 32px; padding: 0; }}
            #shotbar QToolButton:hover {{ background: rgba(255, 255, 255, 20); }}
            #shotbar QToolButton:checked {{ background: {ACCENT}; }}
            #shotbar QToolButton:disabled {{ color: {FAINT}; }}
            #shotbar QToolButton#done {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8a7cff, stop:1 #6b5bf2); }}
            #shotbar QFrame#sep {{ background: {BORDER}; }}
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 5, 6, 5)
        lay.setSpacing(2)

        def btn(text, tip, slot, checkable=False, name=None):
            b = QToolButton()
            if text in ICON_SVG:
                set_icon(b, text, TEXT if name != "done" else "#ffffff", 18, on="#ffffff")
            else:
                b.setText(text)
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.setFocusPolicy(Qt.NoFocus)
            b.setCursor(Qt.PointingHandCursor)
            if name:
                b.setObjectName(name)
            b.clicked.connect(slot)
            lay.addWidget(b)
            return b

        def sep():
            s = QFrame()
            s.setObjectName("sep")
            s.setFixedSize(1, 24)
            lay.addSpacing(4)
            lay.addWidget(s)
            lay.addSpacing(4)

        self.tool_btns = {}
        for key, _glyph, tip, hk in SHOT_TOOLS:
            self.tool_btns[key] = btn(key if key in ICON_SVG else _glyph, f"{tip}  [{QKeySequence(hk).toString()}]",
                                      lambda _=False, k=key: ov.set_tool(k), True)
        sep()
        self.color_btns = {}
        for c in SHOT_COLORS:
            b = btn("", "Цвет", lambda _=False, c=c: ov.set_color(c), True)
            b.setFixedSize(26, 26)
            b.setStyleSheet(f"QToolButton {{ background: {c}; border: 2px solid #2c2d37; border-radius: 13px;"
                            f" min-width: 0; min-height: 0; }} QToolButton:hover {{ border-color: #6b6c78; }}"
                            f" QToolButton:checked {{ border: 3px solid white; }}")
            self.color_btns[c] = b
        sep()
        self.size_btns = {}
        for k, icon, tip in (("S", "•", "Тонко"), ("M", "●", "Средне"), ("L", "⬤", "Толсто")):
            self.size_btns[k] = btn(icon, tip, lambda _=False, k=k: ov.set_size(k), True)
        sep()
        self.undo_btn = btn("undo", "Отменить  [Ctrl+Z]", ov.undo)
        self.redo_btn = btn("redo", "Вернуть  [Ctrl+Y]", ov.redo)
        sep()
        btn("x", "Отмена  [Esc]", ov.session.cancel)
        btn("check", "Готово — скопировать, сохранить, загрузить  [Enter]", ov.confirm, name="done")
        self.sync()

    def sync(self):
        ov = self.ov
        for k, b in self.tool_btns.items():
            b.setChecked(k == ov.tool)
        for k, b in self.color_btns.items():
            b.setChecked(k == ov.color)
        for k, b in self.size_btns.items():
            b.setChecked(k == ov.size)
        self.undo_btn.setEnabled(bool(ov.history))
        self.redo_btn.setEnabled(bool(ov.redo_stack))

    def place(self, ar):
        self.adjustSize()
        w, h, W, H = self.width(), self.height(), self.parentWidget().width(), self.parentWidget().height()
        x = min(max(8, ar.center().x() - w / 2), W - w - 8)
        y = ar.bottom() + 10
        if y + h > H - 8:
            y = ar.top() - h - 10
        if y < 8:
            y = ar.bottom() - h - 10
        self.move(int(x), int(y))


class ShotOverlay(QWidget):
    """Стоп-кадр одного монитора: тянем мышью область или кликаем по окну — как в ShareX.
    После выделения появляется панель для стрелок, текста, размытия и т.п."""
    LOUPE_PX = 15  # сколько пикселей видно в лупе
    LOUPE_ZOOM = 8

    def __init__(self, session, screen, shot, windows):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.session = session
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        geo = screen.geometry()
        self.dpr = shot.width() / max(1, geo.width())
        shot.setDevicePixelRatio(self.dpr)
        self.shot = shot
        self.img = shot.toImage()
        full = self.img.rect()
        # Qt хранит левый верхний угол экрана в физических пикселях, а размер — в логических
        self.wins = [QRect(x - geo.x(), y - geo.y(), w, h).intersected(full) for x, y, w, h in windows]
        self.wins = [r for r in self.wins if not r.isEmpty()]
        self.start = None  # физический пиксель, где нажали
        self.cur = None
        self.sel = None  # выделение в физических пикселях
        self.mode = "select"
        self.bar = None
        self.shapes, self.history, self.redo_stack = [], [], []
        self.drawing = None  # пометка, которую сейчас рисуем
        self.erasing = False
        self.text_edit = None
        draw = session.ctl.draw
        self.tool, self.color, self.size = draw["tool"], draw["color"], draw["size"]
        self.setScreen(screen)
        self.setGeometry(geo)

    # координаты
    def phys(self, pos):
        return QPoint(min(self.img.width() - 1, max(0, int(pos.x() * self.dpr))),
                      min(self.img.height() - 1, max(0, int(pos.y() * self.dpr))))

    def physf(self, pos):
        return QPointF(pos.x() * self.dpr, pos.y() * self.dpr)

    def logical(self, r):
        return QRectF(r.x() / self.dpr, r.y() / self.dpr, r.width() / self.dpr, r.height() / self.dpr)

    def hovered(self):
        if self.cur is not None:
            for r in self.wins:
                if r.contains(self.cur):
                    return r
        return self.img.rect()

    # режим рисования
    def enter_edit(self, r):
        self.mode = "edit"
        self.sel = r
        self.start = None
        self.bar = ShotToolbar(self)
        self.bar.place(self.logical(r))
        self.bar.show()
        self.update_cursor()
        self.setFocus()
        self.update()

    def leave_edit(self):
        if self.bar:
            self.bar.deleteLater()
            self.bar = None
        self.mode = "select"
        self.sel = None
        self.shapes, self.history, self.redo_stack = [], [], []
        self.setCursor(Qt.CrossCursor)
        self.update()

    def remember(self):
        self.session.ctl.save_draw(self.tool, self.color, self.size)
        if self.bar:
            self.bar.sync()

    def set_tool(self, k):
        self.commit_text()
        self.tool = k
        self.update_cursor()
        self.remember()

    def set_color(self, c):
        self.color = c
        if self.text_edit:
            self.style_text_edit()
        self.remember()

    def set_size(self, k):
        self.size = k
        if self.text_edit:
            self.style_text_edit()
        self.remember()

    def update_cursor(self):
        self.setCursor({"text": Qt.IBeamCursor, "eraser": Qt.PointingHandCursor}.get(self.tool, Qt.CrossCursor))

    def new_shape(self, t, pt):
        return {"t": t, "c": self.color, "w": SHOT_SIZES[self.size] * self.dpr, "d": self.dpr, "pts": [pt]}

    def add_shape(self, sh):
        if sh["t"] == "pixel":
            sh["cache"] = pixelate(self.img, shape_rect(sh))
        self.do(("add", sh, len(self.shapes)))

    # журнал действий: ("add" | "del", пометка, позиция) — так Ctrl+Z возвращает и стёртое ластиком
    def apply(self, act, forward):
        kind, sh, i = act
        if (kind == "add") == forward:
            self.shapes.insert(i, sh)
        else:
            self.shapes.remove(sh)
        self.remember()
        self.update()

    def do(self, act):
        self.history.append(act)
        self.redo_stack.clear()
        self.apply(act, True)

    def undo(self):
        self.commit_text()
        if self.history:
            act = self.history.pop()
            self.redo_stack.append(act)
            self.apply(act, False)

    def redo(self):
        if self.redo_stack:
            act = self.redo_stack.pop()
            self.history.append(act)
            self.apply(act, True)

    def erase_at(self, pt):
        for i in range(len(self.shapes) - 1, -1, -1):
            if shape_hit(self.shapes[i], pt, 6 * self.dpr):
                self.do(("del", self.shapes[i], i))
                return True
        return False

    # текст
    def style_text_edit(self):
        fs = SHOT_FONT[self.size]
        self.text_edit.setStyleSheet(
            f"QLineEdit {{ background: rgba(0,0,0,70); color: {self.color}; border: 1px dashed {ACCENT};"
            f" border-radius: 0; padding: 0; font: bold {fs}px 'Segoe UI'; }}")
        fm = QFontMetrics(self.text_edit.font())
        self.text_edit.resize(max(60, fm.horizontalAdvance(self.text_edit.text()) + fs), fm.height() + 4)

    def start_text(self, pos):
        ed = QLineEdit(self)
        ed.setFrame(False)
        ed.setPlaceholderText("Текст…")
        ed.move(int(pos.x()), int(pos.y() - SHOT_FONT[self.size] * 0.7))
        self.text_edit = ed
        self.style_text_edit()
        ed.textChanged.connect(self.style_text_edit)
        ed.returnPressed.connect(self.commit_text)
        ed.show()
        ed.setFocus()

    def commit_text(self, keep=True):
        ed, self.text_edit = self.text_edit, None
        if ed is None:
            return
        t = ed.text().strip()
        if t and keep:
            sh = self.new_shape("text", QPointF((ed.x() + 2) * self.dpr, (ed.y() + 2) * self.dpr))
            sh.update(text=t, fs=SHOT_FONT[self.size] * self.dpr)
            self.add_shape(sh)
        ed.hide()
        ed.deleteLater()
        self.setFocus()

    # результат
    def render(self):
        out = self.img.copy()
        if self.shapes:
            p = QPainter(out)
            p.setClipRect(self.sel)
            for sh in self.shapes:
                draw_shape(p, sh, self.img)
            p.end()
        return out.copy(self.sel)

    def confirm(self):
        self.commit_text()
        if self.mode == "edit":
            self.session.finish(self.render())
        else:
            self.session.finish(self.img.copy(self.sel if self.sel is not None else self.img.rect()))

    # мышь и клавиатура
    def mousePressEvent(self, e):
        if self.mode == "edit":
            return self.edit_press(e)
        if e.button() == Qt.LeftButton:
            self.start = self.phys(e.position())
            self.sel = None
        elif e.button() == Qt.RightButton:
            if self.start is not None:  # правая кнопка во время выделения — сбросить его
                self.start = self.sel = None
                self.update()
            else:
                self.session.cancel()

    def edit_press(self, e):
        pt = self.physf(e.position())
        if e.button() == Qt.RightButton:
            if self.drawing:
                self.drawing = None
                self.update()
            elif not self.erase_at(pt) and not self.shapes:
                self.commit_text(keep=False)
                self.leave_edit()  # ничего не нарисовано — выделить заново
            return
        if e.button() != Qt.LeftButton:
            return
        had_text = self.text_edit is not None
        self.commit_text()
        if not QRectF(self.sel).contains(pt):
            return
        if self.tool == "eraser":
            self.erasing = True
            self.erase_at(pt)
        elif self.tool == "step":
            sh = self.new_shape("step", pt)
            sh["n"] = 1 + sum(1 for s in self.shapes if s["t"] == "step")
            self.add_shape(sh)
        elif self.tool == "text":
            if not had_text:  # первый клик ставит текст, клик мимо — просто завершает ввод
                self.start_text(e.position())
        else:
            self.drawing = self.new_shape(self.tool, pt)

    def mouseMoveEvent(self, e):
        if self.mode == "edit":
            pt = self.physf(e.position())
            if self.drawing:
                if self.drawing["t"] in ("pen", "marker"):
                    self.drawing["pts"].append(pt)
                else:
                    if e.modifiers() & Qt.ShiftModifier:  # Shift — ровно: 45° для линий, квадрат/круг
                        pt = self.snap(self.drawing["pts"][0], pt, self.drawing["t"])
                    self.drawing["pts"][1:] = [pt]
                self.update()
            elif self.erasing and e.buttons() & Qt.LeftButton:
                self.erase_at(pt)
            return
        self.cur = self.phys(e.position())
        if self.start is not None and (self.cur - self.start).manhattanLength() > 3 * self.dpr:
            self.sel = QRect(QPoint(min(self.start.x(), self.cur.x()), min(self.start.y(), self.cur.y())),
                             QPoint(max(self.start.x(), self.cur.x()), max(self.start.y(), self.cur.y())))
        self.update()

    @staticmethod
    def snap(a, b, t):
        dx, dy = b.x() - a.x(), b.y() - a.y()
        if t in ("rect", "ellipse", "pixel"):
            s = max(abs(dx), abs(dy))
            return QPointF(a.x() + math.copysign(s, dx or 1), a.y() + math.copysign(s, dy or 1))
        ang = round(math.atan2(dy, dx) / (math.pi / 4)) * (math.pi / 4)
        d = math.hypot(dx, dy)
        return QPointF(a.x() + d * math.cos(ang), a.y() + d * math.sin(ang))

    def mouseReleaseEvent(self, e):
        if self.mode == "edit":
            self.erasing = False
            sh, self.drawing = self.drawing, None
            if sh and e.button() == Qt.LeftButton:
                a, b = sh["pts"][0], sh["pts"][-1]
                if sh["t"] in ("pen", "marker") or math.hypot(b.x() - a.x(), b.y() - a.y()) >= 3 * self.dpr:
                    self.add_shape(sh)
            self.update()
            return
        if e.button() != Qt.LeftButton or self.start is None:
            return
        r = self.sel if self.sel is not None else self.hovered()  # простой клик — окно под курсором
        self.start = None
        if self.session.ctl.store.get_setting("shot_editor", "1") == "1":
            self.enter_edit(r)
        else:
            self.session.finish(self.img.copy(r))

    def keyPressEvent(self, e):
        k, mods = e.key(), e.modifiers()
        if k == Qt.Key_Escape:
            if self.text_edit:
                self.commit_text(keep=False)
            else:
                self.session.cancel()
        elif k in (Qt.Key_Return, Qt.Key_Enter):
            self.confirm()
        elif self.mode == "edit":
            if mods & Qt.ControlModifier and k == Qt.Key_Z:
                self.undo()
            elif mods & Qt.ControlModifier and k == Qt.Key_Y:
                self.redo()
            elif mods & Qt.ControlModifier and k == Qt.Key_C:
                self.confirm()
            elif not mods & (Qt.ControlModifier | Qt.AltModifier):
                for key, _, _, hk in SHOT_TOOLS:
                    if k == hk:
                        self.set_tool(key)
                        break
        elif k == Qt.Key_C and self.cur is not None:
            self.session.pick_color(QColor(self.img.pixel(self.cur)))
        elif k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):  # точная наводка стрелками
            d = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0), Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}[k]
            c = QCursor.pos()
            QCursor.setPos(c.x() + d[0], c.y() + d[1])

    def enterEvent(self, e):
        self.activateWindow()

    # рисование
    def paintEvent(self, e):
        p = QPainter(self)
        p.drawPixmap(0, 0, self.shot)
        area = self.sel if self.sel is not None else self.hovered()
        ar = self.logical(area)
        dim = QPainterPath()
        dim.setFillRule(Qt.OddEvenFill)
        dim.addRect(QRectF(self.rect()))
        dim.addRect(ar)
        p.fillPath(dim, QColor(0, 0, 0, 120))

        if self.mode == "edit":
            p.save()
            p.setClipRect(ar)
            p.scale(1 / self.dpr, 1 / self.dpr)
            for sh in self.shapes + ([self.drawing] if self.drawing else []):
                draw_shape(p, sh, self.img)
            p.restore()

        p.setPen(QPen(QColor(ACCENT), 2))
        p.drawRect(ar.adjusted(1, 1, -1, -1))

        f = QFont(self.font())
        f.setPointSizeF(9.5)
        f.setBold(True)
        p.setFont(f)
        label = f"{area.width()} × {area.height()}"
        fm = QFontMetrics(f)
        lw, lh = fm.horizontalAdvance(label) + 16, fm.height() + 8
        lx = min(max(0, ar.left()), self.width() - lw)
        ly = ar.top() - lh - 6 if ar.top() - lh - 6 >= 0 else ar.top() + 6
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(20, 20, 26, 220))
        p.drawRoundedRect(QRectF(lx, ly, lw, lh), 6, 6)
        p.setPen(QColor(TEXT))
        p.drawText(QRectF(lx, ly, lw, lh), Qt.AlignCenter, label)

        if self.mode == "edit":
            return
        if self.cur is not None and self.underMouse():
            self.draw_loupe(p, f)
        elif self.cur is None:
            self.draw_hint(p, f)

    def draw_hint(self, p, f):
        t = "Выделите область или кликните по окну · Enter — весь экран · Esc — отмена"
        fm = QFontMetrics(f)
        w, h = fm.horizontalAdvance(t) + 28, fm.height() + 14
        r = QRectF((self.width() - w) / 2, 24, w, h)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(20, 20, 26, 220))
        p.drawRoundedRect(r, 8, 8)
        p.setPen(QColor(TEXT))
        p.drawText(r, Qt.AlignCenter, t)

    def draw_loupe(self, p, f):
        n, z = self.LOUPE_PX, self.LOUPE_ZOOM
        size = n * z
        cur = QPointF(self.cur.x() / self.dpr, self.cur.y() / self.dpr)
        info_h = 44
        x, y = cur.x() + 24, cur.y() + 24
        if x + size > self.width():
            x = cur.x() - 24 - size
        if y + size + info_h > self.height():
            y = cur.y() - 24 - size - info_h
        box = QRectF(x, y, size, size)
        src = self.img.copy(self.cur.x() - n // 2, self.cur.y() - n // 2, n, n)
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.drawImage(box, src)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        for i in range(1, n):
            p.drawLine(QPointF(x + i * z, y), QPointF(x + i * z, y + size))
            p.drawLine(QPointF(x, y + i * z), QPointF(x + size, y + i * z))
        p.setPen(QPen(QColor(ACCENT), 2))
        p.drawRect(QRectF(x + (n // 2) * z, y + (n // 2) * z, z, z))
        p.setPen(QPen(QColor(BORDER), 2))
        p.drawRect(box)
        c = QColor(self.img.pixel(self.cur))
        info = QRectF(x, y + size, size, info_h)
        p.fillRect(info, QColor(20, 20, 26, 235))
        p.fillRect(QRectF(x + 8, y + size + 8, 12, 12), c)
        f2 = QFont(f)
        f2.setPointSizeF(8.5)
        p.setFont(f2)
        p.setPen(QColor(TEXT))
        p.drawText(QRectF(x + 26, y + size + 4, size - 30, 20), Qt.AlignVCenter, c.name().upper())
        f2.setBold(False)
        p.setFont(f2)
        p.setPen(QColor(MUTED))
        p.drawText(QRectF(x + 8, y + size + 22, size - 12, 20), Qt.AlignVCenter,
                   f"{self.cur.x()}, {self.cur.y()} · C — цвет")


class ShotSession(QObject):
    """Один заход «сделать скриншот»: стоп-кадры всех мониторов и оверлей на каждом."""

    def __init__(self, ctl):
        super().__init__()
        self.ctl = ctl
        wins = visible_windows()
        self.overlays = []
        for scr in QGuiApplication.screens():
            shot = scr.grabWindow(0)
            if not shot.isNull():
                self.overlays.append(ShotOverlay(self, scr, shot, wins))
        if not self.overlays:
            QTimer.singleShot(0, self.cancel)
            return
        here = QGuiApplication.screenAt(QCursor.pos())
        for o in self.overlays:
            o.show()
        for o in self.overlays:
            if o.screen() is here:
                o.raise_()
                o.activateWindow()
                if IS_WIN:
                    user32.SetForegroundWindow(int(o.winId()))

    def close_all(self):
        for o in self.overlays:
            o.close()
        self.overlays = []

    def cancel(self):
        self.close_all()
        self.ctl.shot = None

    def finish(self, img):
        self.close_all()
        img.setDevicePixelRatio(1)
        QTimer.singleShot(0, lambda: self.ctl.on_screenshot(img))

    def pick_color(self, c):
        self.close_all()
        QTimer.singleShot(0, lambda: self.ctl.on_color_picked(c))


class ShotToast(QWidget):
    """Уведомление в углу экрана после скриншота: превью и быстрые действия."""

    def __init__(self, ctl, iid, img, path):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.ctl, self.iid, self.path = ctl, iid, path
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_StyledBackground)
        self.setObjectName("toast")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 12, 14)
        lay.setSpacing(10)
        top = QHBoxLayout()
        top.setSpacing(8)
        ok = QLabel()
        ok.setPixmap(icon("check", "#34d399", size=16).pixmap(QSize(16, 16), self.devicePixelRatioF()))
        title = QLabel("Скриншот скопирован")
        title.setStyleSheet("font-weight: 600;")
        dims = QLabel(f"{img.width()} × {img.height()}")
        dims.setObjectName("hint")
        x = set_icon(QPushButton(), "x", MUTED, 14)
        x.setObjectName("ghost")
        x.setFixedSize(28, 28)
        x.clicked.connect(self.close)
        top.addWidget(ok)
        top.addWidget(title)
        top.addWidget(dims)
        top.addStretch()
        top.addWidget(x)
        lay.addLayout(top)
        pic = QLabel()
        pic.setAlignment(Qt.AlignCenter)
        pic.setCursor(Qt.PointingHandCursor)
        pic.setToolTip("Открыть Kipshot")
        pic.setPixmap(hidpi_pixmap(img, 300, 170, self.devicePixelRatioF()))
        pic.mousePressEvent = lambda e: (self.ctl.show_main(), self.close())
        lay.addWidget(pic)
        if path:
            where = QLabel(os.path.join(os.path.basename(os.path.dirname(path)), os.path.basename(path)))
            where.setObjectName("hint")
            lay.addWidget(where)
        self.link = QLabel()
        self.link.setOpenExternalLinks(True)
        self.link.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.link.setWordWrap(True)
        self.link.hide()
        lay.addWidget(self.link)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.up_btn = set_icon(QPushButton(" Загрузить"), "upload")
        self.up_btn.clicked.connect(self.on_up_btn)
        row.addWidget(self.up_btn)
        ocr = set_icon(QPushButton(" Текст"), "scan")
        ocr.clicked.connect(lambda: (self.ctl.recognize_text(self.iid, quick=True), self.close()))
        row.addWidget(ocr)
        if path:
            folder = set_icon(QPushButton(" Папка"), "folder")
            folder.clicked.connect(self.open_folder)
            row.addWidget(folder)
        row.addStretch()
        lay.addLayout(row)
        self.timer = QTimer(self, singleShot=True, interval=6000)
        self.timer.timeout.connect(self.close)
        self.url = ""
        self.busy = False

    def on_up_btn(self):
        if self.url:
            self.ctl.copy_link(self.iid)
            self.up_btn.setText(" Скопировано")
            set_icon(self.up_btn, "check", "#34d399")
        else:
            self.ctl.upload_item(self.iid)

    def set_uploading(self):
        self.busy = True
        self.timer.stop()
        self.link.setText("Загружаю на " + UPLOADERS[self.ctl.uploader.host()][0].split(" ")[0] + "…")
        self.link.show()
        self.up_btn.setEnabled(False)
        self.adjust()

    def set_result(self, url, err):
        self.busy = False
        self.up_btn.setEnabled(True)
        if err:
            self.link.setText(f'<span style="color:{DANGER}">Не загрузилось: {err}</span>')
            self.up_btn.setText(" Ещё раз")
        else:
            self.url = url
            copied = self.ctl.store.get_setting("up_copy", "1") == "1"
            self.link.setText(f'<a href="{url}" style="color:{ACCENT_HI}; text-decoration:none">{url}</a>'
                              + (f'<br><span style="color:{FAINT}">ссылка скопирована</span>' if copied else ""))
            self.up_btn.setText(" Копировать ссылку")
            set_icon(self.up_btn, "link")
        self.link.show()
        self.adjust()
        if not self.underMouse():
            self.timer.start(8000)

    def adjust(self):
        bottom = self.geometry().bottom()
        self.adjustSize()
        self.move(self.x(), bottom - self.height())

    def open_folder(self):
        if IS_WIN:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(self.path)])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self.path)))
        self.close()

    def popup(self):
        self.adjustSize()
        scr = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        ag = scr.availableGeometry()
        self.move(ag.right() - self.width() - 16, ag.bottom() - self.height() - 16)
        self.show()
        self.timer.start()

    def enterEvent(self, e):
        self.timer.stop()

    def leaveEvent(self, e):
        if not self.busy:
            self.timer.start(3000)


class SettingsDialog(QDialog):
    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(520)
        style_window(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 14, 24, 18)
        lay.setSpacing(12)
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        def section(t):
            lb = QLabel(t.upper())
            lb.setObjectName("section")
            form.addRow(lb)

        section("Горячие клавиши")
        self.hk = QComboBox()
        self.hk.addItems(list(HOTKEYS))
        self.hk.setCurrentText(ctl.store.get_setting("hotkey", DEFAULT_HOTKEY))
        form.addRow("Горячая клавиша панели:", self.hk)
        self.shot_hk = QComboBox()
        self.shot_hk.addItems(list(SHOT_HOTKEYS))
        self.shot_hk.setCurrentText(ctl.store.get_setting("shot_hotkey", DEFAULT_SHOT_HOTKEY))
        form.addRow("Скриншот области:", self.shot_hk)
        section("Скриншоты")
        self.shot_editor = QCheckBox("После выделения показывать инструменты (стрелки, текст, размытие…)")
        self.shot_editor.setChecked(ctl.store.get_setting("shot_editor", "1") == "1")
        form.addRow("", self.shot_editor)
        self.shot_save = QCheckBox("Сохранять скриншоты в папку")
        self.shot_save.setChecked(ctl.store.get_setting("shot_save", "1") == "1")
        form.addRow("", self.shot_save)
        dir_row = QHBoxLayout()
        self.shot_dir = QLineEdit(ctl.store.get_setting("shot_dir", default_shot_dir()))
        self.shot_dir.setReadOnly(True)
        pick = set_icon(QPushButton(), "folder")
        pick.setFixedWidth(40)
        pick.setToolTip("Выбрать папку")
        pick.clicked.connect(self.pick_shot_dir)
        dir_row.addWidget(self.shot_dir, 1)
        dir_row.addWidget(pick)
        form.addRow("Папка скриншотов:", dir_row)
        self.shot_month = QCheckBox("Раскладывать по папкам месяцев (2026-11, 2026-12 …)")
        self.shot_month.setChecked(ctl.store.get_setting("shot_month", "1") == "1")
        form.addRow("", self.shot_month)
        section("Загрузка на хостинг")
        self.up_auto = QCheckBox("Загружать скриншоты на хостинг автоматически")
        self.up_auto.setChecked(ctl.store.get_setting("up_auto", "1") == "1")
        form.addRow("", self.up_auto)
        self.up_copy = QCheckBox("После загрузки копировать ссылку в буфер")
        self.up_copy.setChecked(ctl.store.get_setting("up_copy", "1") == "1")
        form.addRow("", self.up_copy)
        self.up_host = QComboBox()
        for k, (name, _) in UPLOADERS.items():
            self.up_host.addItem(name, k)
        self.up_host.setCurrentIndex(list(UPLOADERS).index(ctl.uploader.host()))
        form.addRow("Хостинг картинок:", self.up_host)
        self.up_keys = {k: ctl.store.get_setting(f"up_key_{k}", "") for k in UPLOADERS}
        self.up_key = QLineEdit()
        self.up_key_label = QLabel("Ключ:")
        form.addRow(self.up_key_label, self.up_key)
        self.up_note = QLabel()
        self.up_note.setObjectName("hint")
        self.up_note.setWordWrap(True)
        form.addRow("", self.up_note)
        self._host = None
        self.up_host.currentIndexChanged.connect(self.on_host)
        self.on_host()
        section("Общее")
        self.style_box = QComboBox()
        self.style_box.addItem("Компактное меню с номерами", "compact")
        self.style_box.addItem("Большая панель с предпросмотром", "large")
        self.style_box.setCurrentIndex(0 if ctl.panel_style == "compact" else 1)
        form.addRow("Вид всплывающего окна:", self.style_box)
        self.limit = QSpinBox()
        self.limit.setRange(20, 10000)
        self.limit.setSingleStep(50)
        self.limit.setValue(ctl.max_items)
        form.addRow("Хранить в истории (шт.):", self.limit)
        self.auto = QCheckBox("Запускать вместе с Windows")
        self.auto.setChecked(get_autostart())
        self.auto.setEnabled(IS_WIN)
        form.addRow("", self.auto)
        self.paste = QCheckBox("Сразу вставлять в активное окно (из быстрой панели)")
        self.paste.setChecked(ctl.auto_paste)
        form.addRow("", self.paste)
        snd = QHBoxLayout()
        self.sound_box = QComboBox()
        for key, name in SOUNDS.items():
            self.sound_box.addItem(name, key)
        self.sound_box.setCurrentIndex(list(SOUNDS).index(ctl.sound.kind) if ctl.sound.kind in SOUNDS else 0)
        self.vol = QSpinBox()
        self.vol.setRange(5, 100)
        self.vol.setSingleStep(10)
        self.vol.setSuffix(" %")
        self.vol.setValue(ctl.sound.volume)
        test = set_icon(QPushButton(), "play")
        test.setFixedWidth(40)
        test.setToolTip("Прослушать")
        test.clicked.connect(self.test_sound)
        snd.addWidget(self.sound_box, 1)
        snd.addWidget(self.vol)
        snd.addWidget(test)
        form.addRow("Звук при копировании:", snd)
        lay.addLayout(form)
        note = QLabel(f"{APP} {APP_VERSION}\n\nЗакреплённые элементы, заметки и элементы в папках\nне удаляются при очистке и по лимиту.")
        note.setObjectName("hint")
        lay.addWidget(note)
        clear = set_icon(QPushButton("  Очистить историю"), "trash")
        clear.setObjectName("danger")
        clear.clicked.connect(self.clear)
        lay.addWidget(clear)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Сохранить")
        bb.button(QDialogButtonBox.Ok).setObjectName("primary")
        bb.button(QDialogButtonBox.Cancel).setText("Отмена")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def on_host(self):
        if self._host:
            self.up_keys[self._host] = self.up_key.text().strip()
        self._host = self.up_host.currentData()
        hint = UPLOADERS[self._host][1]
        self.up_key.setText(self.up_keys.get(self._host, ""))
        self.up_key.setPlaceholderText(hint or "")
        self.up_key.setVisible(bool(hint))
        self.up_key_label.setVisible(bool(hint))
        self.up_note.setText({
            "freeimage": "Картинки на freeimage.host хранятся бессрочно, в исходном качестве, доступны всем, "
                         "у кого есть ссылка. Если хостинг не отвечает, Kipshot сам попробует catbox.moe и pixhost.to.",
            "catbox": "Файлы на catbox.moe хранятся бессрочно и доступны всем, у кого есть ссылка. Удалить их нельзя. "
                      "Если catbox не принимает файлы, Kipshot сам попробует другие хостинги.",
            "pixhost": "Картинки на pixhost.to хранятся бессрочно (до 10 МБ) и доступны всем, у кого есть ссылка. "
                       "Если сайт не отвечает, Kipshot сам попробует другие хостинги.",
            "imgur": "Бесплатно: зарегистрируйте приложение на api.imgur.com (тип «без авторизации») и вставьте Client-ID.",
            "imgbb": "Бесплатно: войдите на imgbb.com и получите ключ на api.imgbb.com.",
        }[self._host])

    def pick_shot_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Папка для скриншотов", self.shot_dir.text())
        if d:
            self.shot_dir.setText(os.path.normpath(d))

    def test_sound(self):
        Sound(self.sound_box.currentData(), self.vol.value(), "test_sound.wav").play()

    def clear(self):
        self.ctl.clear_history(self)

    def accept(self):
        s = self.ctl.store
        s.set_setting("max_items", self.limit.value())
        s.set_setting("auto_paste", int(self.paste.isChecked()))
        s.set_setting("sound", self.sound_box.currentData())
        s.set_setting("sound_volume", self.vol.value())
        self.ctl.sound.configure(self.sound_box.currentData(), self.vol.value())
        self.ctl.max_items = self.limit.value()
        self.ctl.auto_paste = self.paste.isChecked()
        self.ctl.panel_style = self.style_box.currentData()
        s.set_setting("panel_style", self.ctl.panel_style)
        s.trim(self.ctl.max_items)
        hk = self.hk.currentText()
        s.set_setting("hotkey", hk)
        s.set_setting("shot_hotkey", self.shot_hk.currentText())
        s.set_setting("shot_save", int(self.shot_save.isChecked()))
        s.set_setting("shot_editor", int(self.shot_editor.isChecked()))
        s.set_setting("shot_dir", self.shot_dir.text())
        s.set_setting("shot_month", int(self.shot_month.isChecked()))
        s.set_setting("up_auto", int(self.up_auto.isChecked()))
        s.set_setting("up_copy", int(self.up_copy.isChecked()))
        self.on_host()  # запомнить ключ из поля
        s.set_setting("up_host", self._host)
        for k, v in self.up_keys.items():
            s.set_setting(f"up_key_{k}", v)
        self.ctl.apply_hotkey()
        try:
            if self.auto.isChecked() != get_autostart():
                set_autostart(self.auto.isChecked())
        except OSError as e:
            QMessageBox.warning(self, "Автозапуск", f"Не удалось изменить автозапуск: {e}")
        self.ctl.changed.emit()
        super().accept()


# ───────────────────────────── Контроллер ─────────────────────────────
class Controller(QObject):
    changed = Signal()
    ocr_done = Signal(int, str, str, bool)

    def __init__(self, app, db_path=None):
        super().__init__()
        self.app = app
        self.store = Store(db_path or os.path.join(data_dir(), "kipshot.db"))
        ico = resource_path("icon.ico")
        self.icon = QIcon(ico) if ico else make_app_icon()
        app.setWindowIcon(self.icon)
        self.paused = False
        self.max_items = int(self.store.get_setting("max_items", 500))
        self.auto_paste = self.store.get_setting("auto_paste", "1") == "1"
        self.panel_style = self.store.get_setting("panel_style", "compact")
        self.sound = Sound(self.store.get_setting("sound", "pop"), int(self.store.get_setting("sound_volume", 60)))
        self.thumbs = {}
        self.ocr_cache = {}
        self.ocr_running = set()
        self.ocr_done.connect(self.on_ocr_done)
        self.shot = None
        self.toast = None
        self.uploader = Uploader(self.store)
        self.uploader.done.connect(self.on_uploaded)
        self.uploading = set()
        self.draw = {"tool": self.store.get_setting("draw_tool", "arrow"),
                     "color": self.store.get_setting("draw_color", SHOT_COLORS[0]),
                     "size": self.store.get_setting("draw_size", "M")}
        if self.draw["tool"] not in {t[0] for t in SHOT_TOOLS}:
            self.draw["tool"] = "arrow"
        if self.draw["size"] not in SHOT_SIZES:
            self.draw["size"] = "M"
        self.ignore_until = 0.0
        self.prev_hwnd = None
        self._tray_hinted = self.store.get_setting("tray_hinted", "0") == "1"

        self.clip = QGuiApplication.clipboard()
        self.clip.dataChanged.connect(self.on_clipboard)
        self.capture_timer = QTimer(self, singleShot=True, interval=80)
        self.capture_timer.timeout.connect(self.capture)

        self.main = MainWindow(self)
        self.quick = QuickPanel(self)
        self.compact = CompactMenu(self)
        self.changed.connect(self.on_changed)

        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self.icon, self)
            self.tray.setToolTip(APP)
            m = QMenu()
            m.addAction("📸 Скриншот области").triggered.connect(lambda: QTimer.singleShot(250, self.take_screenshot))
            m.addAction("Быстрая панель").triggered.connect(self.show_quick)
            m.addAction("Открыть окно").triggered.connect(self.show_main)
            self.pause_action = m.addAction("Пауза записи")
            self.pause_action.setCheckable(True)
            self.pause_action.toggled.connect(self.set_paused)
            m.addAction("Очистить историю").triggered.connect(lambda: self.clear_history(None))
            m.addSeparator()
            m.addAction("Выход").triggered.connect(self.quit)
            self.tray.setContextMenu(m)
            self.tray_menu = m
            self.tray.activated.connect(
                lambda r: self.show_main() if r in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
            self.tray.show()

        self.hotkey = Hotkey(self.toggle_quick)
        self.shot_hotkey = Hotkey(self.take_screenshot, SHOT_HOTKEY_ID, SHOT_HOTKEYS, DEFAULT_SHOT_HOTKEY)
        self.apply_hotkey()

    # ── буфер обмена
    def on_clipboard(self):
        if not self.paused and time.time() >= self.ignore_until:
            self.capture_timer.start()

    def capture(self):
        if self.paused or time.time() < self.ignore_until:
            return
        try:
            mime = self.clip.mimeData()
            if mime is None:
                return
            kind, text, image = None, None, None
            urls = mime.urls() if mime.hasUrls() else []
            if urls and all(u.isLocalFile() for u in urls):
                kind, text = "files", "\n".join(u.toLocalFile() for u in urls)
            elif mime.hasText() and mime.text().strip():
                text = mime.text()[:2_000_000]
                kind = classify_text(text)
            elif mime.hasImage():
                img = self.clip.image()
                if img.isNull():
                    return
                image = qimage_to_png(img)
                kind, text = "image", f"{img.width()}×{img.height()}"
            else:
                return
        except Exception as e:  # буфер может быть занят другой программой
            print("capture error:", e, file=sys.stderr)
            return
        h = make_hash(kind, text, image)
        existing = self.store.find_hash(h)
        if existing:
            self.store.touch(existing)
        else:
            self.store.add(kind, text, image, h=h)
            self.store.trim(self.max_items)
        self.sound.play()
        self.changed.emit()

    def put_on_clipboard(self, iid):
        r = self.store.get(iid)
        if not r:
            return False
        self.ignore_until = time.time() + 0.6
        if r["kind"] == "image":
            self.clip.setImage(QImage.fromData(r["image"]))
        elif r["kind"] == "files":
            md = QMimeData()
            md.setUrls([QUrl.fromLocalFile(p) for p in r["text"].splitlines() if p])
            md.setText(r["text"])
            self.clip.setMimeData(md)
        else:
            self.clip.setText(r["text"] or "")
        self.store.touch(iid)
        return True

    def copy_item(self, iid, notify=False):
        if self.put_on_clipboard(iid):
            self.changed.emit()
            if notify:
                self.main.statusBar().showMessage("Скопировано в буфер ✓", 1500)

    def paste_item(self, iid):
        if not self.put_on_clipboard(iid):
            return
        self.quick.hide()
        self.compact.hide()
        self.changed.emit()
        if IS_WIN and self.auto_paste and self.prev_hwnd:
            user32.SetForegroundWindow(self.prev_hwnd)
            QTimer.singleShot(120, send_ctrl_v)

    # ── действия с элементами
    def toggle_pin(self, iid):
        r = self.store.get(iid)
        if r:
            self.store.update(iid, pinned=0 if r["pinned"] else 1)
            self.changed.emit()

    def toggle_note(self, iid):
        r = self.store.get(iid)
        if r:
            self.store.update(iid, is_note=0 if r["is_note"] else 1)
            self.changed.emit()

    def set_folder(self, iid, fid):
        self.store.update(iid, folder_id=fid)
        self.changed.emit()

    def delete_item(self, iid):
        self.store.delete(iid)
        self.thumbs.pop(iid, None)
        self.ocr_cache.pop(iid, None)
        self.changed.emit()

    def save_item(self, iid, title, text):
        r = self.store.get(iid)
        if not r:
            return
        fields = {"title": title}
        if text is not None and r["kind"] in ("text", "link", "color"):
            kind = classify_text(text) if text.strip() else "text"
            fields.update(text=text, kind=kind, hash=make_hash(kind, text))
        self.store.update(iid, **fields)
        self.changed.emit()
        self.main.statusBar().showMessage("Сохранено ✓", 1500)

    # ── распознавание текста
    def recognize_text(self, iid, quick=False):
        if iid in self.ocr_cache:
            self.show_ocr(iid, self.ocr_cache[iid], "", quick)
            return
        if iid in self.ocr_running:
            return
        r = self.store.get(iid)
        if not r or r["kind"] != "image" or not r["image"]:
            return
        self.ocr_running.add(iid)
        QApplication.setOverrideCursor(Qt.BusyCursor)
        self.main.statusBar().showMessage("Распознаю текст…")

        def work(data=r["image"]):
            try:
                self.ocr_done.emit(iid, ocr_image(data), "", quick)
            except Exception as e:
                self.ocr_done.emit(iid, "", str(e) or type(e).__name__, quick)
        threading.Thread(target=work, daemon=True).start()

    def on_ocr_done(self, iid, text, err, quick):
        self.ocr_running.discard(iid)
        QApplication.restoreOverrideCursor()
        self.main.statusBar().clearMessage()
        if not err:
            self.ocr_cache[iid] = text
        self.show_ocr(iid, text, err, quick)

    def show_ocr(self, iid, text, err, quick):
        parent = None if quick or not self.main.isVisible() else self.main
        if err:
            QMessageBox.warning(parent, "Текст с картинки", f"Не получилось распознать текст:\n{err}")
            return
        if not text:
            QMessageBox.information(parent, "Текст с картинки", "На картинке не найдено текста.")
            return
        dlg = OcrDialog(self, iid, text, parent)
        dlg.setWindowIcon(make_app_icon())
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def item_context_menu(self, iid, parent, gpos, quick=False):
        r = self.store.get(iid)
        if not r:
            return
        m = QMenu(parent)
        if quick:
            m.addAction("Вставить").triggered.connect(lambda: self.paste_item(iid))
        m.addAction("Копировать").triggered.connect(lambda: self.copy_item(iid, notify=not quick))
        m.addAction("Открепить" if r["pinned"] else "📌 Закрепить").triggered.connect(lambda: self.toggle_pin(iid))
        if r["kind"] == "image":
            m.addAction("🔤 Текст с картинки").triggered.connect(lambda: self.recognize_text(iid, quick))
            if r["url"]:
                m.addAction("🔗 Копировать ссылку").triggered.connect(lambda: self.copy_link(iid))
                m.addAction("🌐 Открыть ссылку").triggered.connect(
                    lambda: QDesktopServices.openUrl(QUrl(r["url"])))
                if r["del_url"]:
                    m.addAction("🗑 Удалить с хостинга…").triggered.connect(
                        lambda: QDesktopServices.openUrl(QUrl(r["del_url"])))
            else:
                m.addAction("☁ Загрузить и скопировать ссылку").triggered.connect(lambda: self.upload_item(iid))
        else:
            m.addAction("Убрать из заметок" if r["is_note"] else "📝 В мои заметки").triggered.connect(
                lambda: self.toggle_note(iid))
        fm = m.addMenu("📁 В папку")
        fm.addAction("Без папки").triggered.connect(lambda: self.set_folder(iid, None))
        for f in self.store.folders():
            fm.addAction(("✓ " if r["folder_id"] == f["id"] else "") + f["name"]).triggered.connect(
                lambda _=False, fid=f["id"]: self.set_folder(iid, fid))
        if not quick:
            fm.addSeparator()
            fm.addAction("＋ Новая папка…").triggered.connect(
                lambda: (lambda fid: fid and self.set_folder(iid, fid))(self.ask_new_folder(parent)))
        m.addSeparator()
        m.addAction("Удалить").triggered.connect(lambda: self.delete_item(iid))
        m.exec(gpos)

    def clear_history(self, parent=None):
        n = len(self.store.query(("all",), limit=100000)) - len(
            [r for r in self.store.query(("all",), limit=100000) if r["pinned"] or r["folder_id"]])
        if n <= 0:
            QMessageBox.information(parent, "Очистить историю", "История уже пуста.")
            return
        if QMessageBox.question(parent, "Очистить историю",
                                f"Удалить {n} элем. из истории?\n\n"
                                "Закреплённое, заметки и элементы в папках останутся.") == QMessageBox.Yes:
            self.store.clear_history()
            self.thumbs.clear()
            self.ocr_cache.clear()
            self.changed.emit()
            self.main.statusBar().showMessage("История очищена ✓", 2000)

    # ── папки
    def ask_new_folder(self, parent):
        name, ok = QInputDialog.getText(parent, "Новая папка", "Название папки:")
        if ok and name.strip():
            fid = self.store.add_folder(name.strip())
            self.main.build_side()
            return fid
        return None

    def rename_folder(self, fid, parent):
        cur = {f["id"]: f["name"] for f in self.store.folders()}.get(fid, "")
        name, ok = QInputDialog.getText(parent, "Переименовать папку", "Название:", text=cur)
        if ok and name.strip():
            self.store.rename_folder(fid, name.strip())
            self.main.build_side()

    def delete_folder(self, fid, parent):
        if QMessageBox.question(parent, "Удалить папку",
                                "Удалить папку? Элементы останутся в истории.") == QMessageBox.Yes:
            self.store.delete_folder(fid)
            self.main.build_side()
            self.changed.emit()

    # ── картинки
    def thumb(self, iid):
        if iid in self.thumbs:
            return self.thumbs[iid]
        r = self.store.get(iid)
        pm = None
        if r and r["image"]:
            img = QImage.fromData(r["image"])
            if not img.isNull():
                side = min(img.width(), img.height())
                img = img.copy((img.width() - side) // 2, (img.height() - side) // 2, side, side)
                pm = QPixmap.fromImage(img.scaled(192, 192, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        self.thumbs[iid] = pm
        return pm

    # ── окна
    def on_changed(self):
        self.main.refresh()
        if self.quick.isVisible():
            keep = current_id(self.quick.list)
            view = [("all",), ("pinned",), ("notes",)][max(0, self.quick.group.checkedId())]
            fill_list(self.quick.list, self.store.query(view, self.quick.search.text().strip(), 300), keep)
        if self.compact.isVisible():
            self.compact.refresh(keep=current_id(self.compact.list))

    def show_main(self):
        self.main.showNormal()
        self.main.raise_()
        self.main.activateWindow()

    def show_quick(self):
        if IS_WIN:
            fg = user32.GetForegroundWindow()
            own = {int(self.main.winId()), int(self.quick.winId()), int(self.compact.winId())}
            self.prev_hwnd = fg if fg and int(fg) not in own else None
        (self.compact if self.panel_style == "compact" else self.quick).popup()

    def toggle_quick(self):
        if self.quick.isVisible() or self.compact.isVisible():
            self.quick.hide()
            self.compact.hide()
        else:
            self.show_quick()

    def set_paused(self, on):
        self.paused = bool(on)
        for w in (getattr(self, "pause_action", None),):
            if w is not None and w.isChecked() != self.paused:
                w.blockSignals(True)
                w.setChecked(self.paused)
                w.blockSignals(False)
        if self.tray:
            self.tray.setToolTip(APP + (" — пауза" if self.paused else ""))
        self.main.refresh()

    def apply_hotkey(self):
        name = self.store.get_setting("hotkey", DEFAULT_HOTKEY)
        ok = self.hotkey.set(name)
        shot = self.store.get_setting("shot_hotkey", DEFAULT_SHOT_HOTKEY)
        shot_ok = self.shot_hotkey.set(shot)
        if IS_WIN:
            lines = [f"Быстрая панель: {name}" if ok else
                     f"⚠ {name} занято другой программой — выберите другое в настройках"]
            if SHOT_HOTKEYS.get(shot):
                lines.append(f"Скриншот: {shot}" if shot_ok else
                             f"⚠ {shot} занято другой программой — выберите другое в настройках")
            self.main.hotkey_hint.setText("\n".join(lines))
        else:
            self.main.hotkey_hint.setText("Горячая клавиша работает только в Windows")

    def open_settings(self):
        SettingsDialog(self, self.main).exec()

    def tray_hint_once(self):
        if self.tray and not self._tray_hinted:
            self._tray_hinted = True
            self.store.set_setting("tray_hinted", 1)
            self.tray.showMessage(APP, "Программа продолжает работать в трее. "
                                       "Выход — правой кнопкой по значку.", self.icon, 4000)

    # ── скриншоты
    def take_screenshot(self):
        if self.shot is not None:
            return
        self.quick.hide()
        self.compact.hide()
        if self.toast is not None:
            self.toast.close()
        self.shot = ShotSession(self)

    def save_draw(self, tool, color, size):
        new = {"tool": tool, "color": color, "size": size}
        for k, v in new.items():
            if self.draw.get(k) != v:
                self.store.set_setting(f"draw_{k}", v)
        self.draw = new

    def on_screenshot(self, img):
        self.shot = None
        if img.isNull() or img.width() < 2 or img.height() < 2:
            return
        png = qimage_to_png(img)
        text = f"{img.width()}×{img.height()}"
        h = make_hash("image", text, png)
        iid = self.store.find_hash(h)
        if iid:
            self.store.touch(iid)
        else:
            iid = self.store.add("image", text, png, h=h)
            self.store.trim(self.max_items)
        self.ignore_until = time.time() + 0.6
        self.clip.setImage(img)
        path = None
        if self.store.get_setting("shot_save", "1") == "1":
            folder = self.store.get_setting("shot_dir", default_shot_dir())
            if self.store.get_setting("shot_month", "1") == "1":  # как в ShareX: Screenshots\2026-11
                folder = os.path.join(folder, datetime.datetime.now().strftime("%Y-%m"))
            try:
                os.makedirs(folder, exist_ok=True)
                stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                path = os.path.join(folder, f"{APP}_{stamp}.png")
                n = 2
                while os.path.exists(path):
                    path = os.path.join(folder, f"{APP}_{stamp}_{n}.png")
                    n += 1
                with open(path, "wb") as f:
                    f.write(png)
            except OSError as e:
                print("screenshot save error:", e, file=sys.stderr)
                path = None
        self.sound.play()
        self.changed.emit()
        self.toast = ShotToast(self, iid, img, path)
        self.toast.destroyed.connect(lambda: setattr(self, "toast", None))
        self.toast.popup()
        if self.store.get_setting("up_auto", "1") == "1":
            self.upload_item(iid)

    # ── загрузка на хостинг
    def toast_for(self, iid):
        t = self.toast
        try:
            return t if t is not None and t.iid == iid and t.isVisible() else None
        except RuntimeError:  # окно уже удалено
            return None

    def upload_item(self, iid):
        r = self.store.get(iid)
        if not r or r["kind"] != "image" or not r["image"] or iid in self.uploading:
            return
        if r["url"]:
            self.on_uploaded(iid, r["url"], r["del_url"] or "", "")
            return
        self.uploading.add(iid)
        self.main.statusBar().showMessage("Загружаю на хостинг…")
        if (t := self.toast_for(iid)) is not None:
            t.set_uploading()
        stamp = datetime.datetime.fromtimestamp(r["created"] or time.time()).strftime("%Y-%m-%d_%H-%M-%S")
        self.uploader.upload(iid, r["image"], f"{APP}_{stamp}.png")
        self.main.refresh()

    def on_uploaded(self, iid, url, del_url, err):
        self.uploading.discard(iid)
        if err:
            self.main.statusBar().showMessage(f"Не удалось загрузить: {err}", 6000)
            if self.toast_for(iid) is None and self.tray:
                self.tray.showMessage(APP, f"Не удалось загрузить скриншот: {err}", QSystemTrayIcon.Warning, 5000)
        else:
            self.store.set_url(iid, url, del_url)
            if self.store.get_setting("up_copy", "1") == "1":
                self.clip.setText(url)  # попадёт в историю как ссылка, как в ShareX
            self.main.statusBar().showMessage("Ссылка скопирована ✓ " + url, 4000)
            if self.toast_for(iid) is None and self.tray:
                self.tray.showMessage(APP, "Скриншот загружен, ссылка скопирована:\n" + url, self.icon, 3000)
        if (t := self.toast_for(iid)) is not None:
            t.set_result(url, err)
        self.changed.emit()

    def copy_link(self, iid):
        r = self.store.get(iid)
        if r and r["url"]:
            self.clip.setText(r["url"])
            self.main.statusBar().showMessage("Ссылка скопирована ✓", 1500)

    def on_color_picked(self, c):
        self.shot = None
        self.clip.setText(c.name().upper())  # попадёт в историю как цвет обычным путём
        if self.tray:
            self.tray.showMessage(APP, f"Цвет {c.name().upper()} скопирован", self.icon, 2000)

    def quit(self):
        self.hotkey.release()
        self.shot_hotkey.release()
        if self.tray:
            self.tray.hide()
        QApplication.quit()


# ───────────────────────────── Запуск ─────────────────────────────
def ui_font():
    fams = set(QFontDatabase.families())
    for name in ("Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", "Inter"):
        if name in fams:
            f = QFont(name, 10)
            f.setHintingPreference(QFont.PreferNoHinting)
            return f
    return QFont(QApplication.font().family(), 10)


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    if IS_WIN:
        try:  # своя иконка на панели задач, а не иконка Python
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{APP}.App")
        except Exception:
            pass
    migrate_from_old_name()
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setApplicationVersion(APP_VERSION)
    app.setQuitOnLastWindowClosed(False)

    server_name = f"{APP}-{os.environ.get('USERNAME') or os.environ.get('USER') or 'user'}"
    sock = QLocalSocket()
    sock.connectToServer(server_name)
    if sock.waitForConnected(300):  # уже запущено — показать окно (или снять скриншот) и выйти
        sock.write(b"shot" if "--shot" in sys.argv else b"show")
        sock.flush()
        sock.waitForBytesWritten(300)
        return 0

    app.setStyle("Fusion")
    app.setFont(ui_font())
    app.setStyleSheet(app_qss())

    ctl = Controller(app)

    QLocalServer.removeServer(server_name)
    server = QLocalServer()
    server.listen(server_name)

    def on_conn():
        c = server.nextPendingConnection()
        if not c:
            return
        done = []

        def handle():
            if done:
                return
            done.append(1)
            # "shot" — скриншот по команде извне (NestOS, ярлык с --shot), иначе — показать окно
            if bytes(c.readAll()).strip() == b"shot":
                ctl.take_screenshot()
            else:
                ctl.show_main()

        c.readyRead.connect(handle)
        QTimer.singleShot(150, handle)

    server.newConnection.connect(on_conn)

    if "--shot" in sys.argv:
        QTimer.singleShot(300, ctl.take_screenshot)
    elif "--hidden" not in sys.argv:
        ctl.show_main()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
