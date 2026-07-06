#!/usr/bin/env python3
"""
PC Screenshot Tool / PC截图工具
Multi-function screenshot utility with i18n (zh/en)
====================================================
Modes: Full Screen | Region | Stealth | Timed | Hotkey
Usage:
    python pc_screenshot.py                  # GUI
    python pc_screenshot.py --full           # Full screen
    python pc_screenshot.py --region         # Region select
    python pc_screenshot.py --stealth        # Stealth (anti-cheat)
    python pc_screenshot.py --lang zh|en     # Switch language
"""

import ctypes
import ctypes.wintypes
import os
import sys
import subprocess
import time
import struct
import threading
import json
import logging
from datetime import datetime

# ============================================================
#  Config & Logging
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "pc_screenshot_config.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "pc_screenshot.log")

def load_config():
    """Load config from JSON, fall back to defaults."""
    defaults = {
        "output_dir": os.path.join(os.path.expanduser("~"), "Desktop"),
        "log_enabled": True,
        "log_max_lines": 5000,
        "hotkey_enabled": True,
        "hotkey_require_admin": False,
        "stealth_ps1": os.path.join(SCRIPT_DIR, "educoder_screenshot_enable.ps1"),
        "stealth_dll": os.path.join(SCRIPT_DIR, "StealthCapture.dll"),
    }
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            defaults.update(loaded)
    except Exception:
        pass
    return defaults

CONFIG = load_config()

_log_lines = []
_log_lock = threading.Lock()

def log_event(action, detail=""):
    """Thread-safe event logger. Writes to memory and file."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {action}" + (f" | {detail}" if detail else "")
    with _log_lock:
        _log_lines.append(line)
        if len(_log_lines) > CONFIG.get("log_max_lines", 5000):
            _log_lines.pop(0)
        if CONFIG.get("log_enabled", True):
            try:
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass

_capture_lock = threading.Lock()

class CaptureBusy(Exception):
    pass

# ============================================================
#  i18n — Chinese / English
# ============================================================

T = {
    "zh": {
        "title": "PC 截图工具",
        "subtitle": "多功能屏幕截图",
        "output_dir": "输出目录:",
        "btn_full": "全屏截图",
        "btn_region": "区域截图",
        "btn_stealth": "隐身模式 (反作弊)",
        "btn_clip": "全屏 → 仅剪贴板",
        "timed_label": "定时截图 (秒)",
        "btn_start": "开始定时",
        "btn_stop": "停止",
        "hotkey_toggle": "启用 Ctrl+Shift+S 全局热键",
        "btn_open_folder": "打开输出目录",
        "ready": "就绪",
        "capturing": "截图中…",
        "saved": "已保存",
        "saved_clip": "已保存 + 剪贴板",
        "region_cancelled": "区域选择已取消",
        "region_too_small": "选择区域太小",
        "stealth_failed": "隐身模式失败",
        "interval_stopped": "定时已停止",
        "hotkey_on": "热键已启用: Ctrl+Shift+S",
        "hotkey_off": "热键已关闭",
        "err_no_dir": "输出目录不存在",
        "err_positive": "请输入正整数",
        "err_title": "错误",
        "file_prefix_full": "full",
        "file_prefix_region": "region",
        "file_prefix_clip": "clip",
        "file_prefix_hotkey": "hotkey",
        "file_prefix_interval": "interval",
        "clip_copied": "已复制到剪贴板",
        "select_region": "[*] 用鼠标框选区域…",
        "cancelled": "已取消",
        "hotkey_start": "[*] 热键监听已启动 (Ctrl+Shift+S). 按 Ctrl+C 停止.",
        "hotkey_stop": "\n[*] 已停止.",
        "interval_start": "[*] 每 {sec} 秒截图一次. Ctrl+C 停止.",
        "interval_stop": "\n[*] 已停止. 共 {count} 张截图.",
        "interval_usage": "用法: --interval <秒数>",
        "lang_switched": "语言已切换为: {lang_name}",
        "lang_zh": "中文",
        "lang_en": "English",
    },
    "en": {
        "title": "PC Screenshot Tool",
        "subtitle": "Multi-mode capture utility",
        "output_dir": "Output:",
        "btn_full": "Full Screen",
        "btn_region": "Region Select",
        "btn_stealth": "Stealth Mode (Anti-Cheat)",
        "btn_clip": "Full → Clipboard Only",
        "timed_label": "Timed interval (sec)",
        "btn_start": "Start Interval",
        "btn_stop": "Stop",
        "hotkey_toggle": "Enable Ctrl+Shift+S hotkey",
        "btn_open_folder": "Open Output Folder",
        "ready": "Ready",
        "capturing": "Capturing…",
        "saved": "Saved",
        "saved_clip": "Saved + Clipboard",
        "region_cancelled": "Region cancelled",
        "region_too_small": "Region too small",
        "stealth_failed": "Stealth failed",
        "interval_stopped": "Interval stopped",
        "hotkey_on": "Hotkey ON: Ctrl+Shift+S",
        "hotkey_off": "Hotkey OFF",
        "err_no_dir": "Output directory does not exist",
        "err_positive": "Enter a positive number",
        "err_title": "Error",
        "file_prefix_full": "full",
        "file_prefix_region": "region",
        "file_prefix_clip": "clip",
        "file_prefix_hotkey": "hotkey",
        "file_prefix_interval": "interval",
        "clip_copied": "Copied to clipboard",
        "select_region": "[*] Select region with mouse…",
        "cancelled": "Cancelled",
        "hotkey_start": "[*] Hotkey listener started (Ctrl+Shift+S). Press Ctrl+C to stop.",
        "hotkey_stop": "\n[*] Stopped.",
        "interval_start": "[*] Capturing every {sec}s. Ctrl+C to stop.",
        "interval_stop": "\n[*] Stopped. {count} screenshots saved.",
        "interval_usage": "Usage: --interval <seconds>",
        "lang_switched": "Language switched to: {lang_name}",
        "lang_zh": "中文",
        "lang_en": "English",
    },
}

_current_lang = "zh"

log_event("session_start", f"pid={os.getpid()}")

def _(key, **fmt):
    """Translate key, optionally format with kwargs."""
    s = T.get(_current_lang, T["en"]).get(key, T["en"].get(key, key))
    if fmt:
        s = s.format(**fmt)
    return s

def set_lang(lang):
    """Set current language. Returns True if valid."""
    global _current_lang
    if lang in T:
        _current_lang = lang
        return True
    return False

def detect_lang():
    """Detect system language, default zh."""
    try:
        import locale
        loc = locale.getlocale()[0] or locale.getdefaultlocale()[0] or ""
        return "zh" if loc.lower().startswith("zh") else "en"
    except Exception:
        return "zh"

# Auto-detect on import if not explicitly set via CLI
_AUTO_DETECTED = False

# ============================================================
#  GDI32 Screen Capture (via ctypes, zero dependencies)
# ============================================================

user32 = ctypes.windll.user32
gdi32  = ctypes.windll.gdi32

SRCCOPY = 0x00CC0020
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize",          ctypes.c_uint32),
        ("biWidth",         ctypes.c_int32),
        ("biHeight",        ctypes.c_int32),
        ("biPlanes",        ctypes.c_uint16),
        ("biBitCount",      ctypes.c_uint16),
        ("biCompression",   ctypes.c_uint32),
        ("biSizeImage",     ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed",       ctypes.c_uint32),
        ("biClrImportant",  ctypes.c_uint32),
    ]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER)]


def capture_fullscreen():
    """Capture entire virtual screen (all monitors). Returns (width, height, bytes_bgra)."""
    if not _capture_lock.acquire(blocking=False):
        raise CaptureBusy("Another capture is in progress")
    try:
        x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

        hdc_screen = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
        gdi32.SelectObject(hdc_mem, hbmp)
        gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, x, y, SRCCOPY)

        bi = BITMAPINFO()
        bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bi.bmiHeader.biWidth = w
        bi.bmiHeader.biHeight = -h
        bi.bmiHeader.biPlanes = 1
        bi.bmiHeader.biBitCount = 32
        bi.bmiHeader.biCompression = 0

        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, ctypes.byref(bi), 0)

        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)

        return w, h, buf.raw
    finally:
        _capture_lock.release()


def capture_region(left, top, width, height):
    """Capture a specific screen region."""
    if not _capture_lock.acquire(blocking=False):
        raise CaptureBusy("Another capture is in progress")
    try:
        w = max(1, width)
        h = max(1, height)

        hdc_screen = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
        gdi32.SelectObject(hdc_mem, hbmp)
        gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, left, top, SRCCOPY)

        bi = BITMAPINFO()
        bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bi.bmiHeader.biWidth = w
        bi.bmiHeader.biHeight = -h
        bi.bmiHeader.biPlanes = 1
        bi.bmiHeader.biBitCount = 32
        bi.bmiHeader.biCompression = 0

        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, ctypes.byref(bi), 0)

        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)

        return w, h, buf.raw
    finally:
        _capture_lock.release()


# ============================================================
#  BMP → PNG (minimal, no Pillow needed)
# ============================================================

def bgra_to_rgba(raw, w, h):
    out = bytearray(len(raw))
    for i in range(0, len(raw), 4):
        out[i]   = raw[i + 2]
        out[i+1] = raw[i + 1]
        out[i+2] = raw[i]
        out[i+3] = raw[i + 3]
    return bytes(out)


def write_png(filepath, width, height, rgba_bytes):
    import zlib

    def chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack(">I", ctypes.c_uint32(
            zlib.crc32(chunk_type + data) & 0xFFFFFFFF).value)
        return struct.pack(">I", len(data)) + c + crc

    raw = b""
    row_size = width * 4
    for y in range(height):
        raw += b"\x00" + rgba_bytes[y * row_size:(y + 1) * row_size]

    compressed = zlib.compress(raw)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", compressed)
    png += chunk(b"IEND", b"")

    with open(filepath, "wb") as f:
        f.write(png)


def save_screenshot(w, h, raw_bgra, filepath):
    rgba = bgra_to_rgba(raw_bgra, w, h)
    write_png(filepath, w, h, rgba)


# ============================================================
#  Window title detection (for filename context)
# ============================================================

def get_foreground_window_title():
    """Get title of the foreground window. Returns '' on failure."""
    try:
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value or ""
        # Sanitize for filename
        bad = '<>:"/\\|?*'
        for ch in bad:
            title = title.replace(ch, "_")
        return title[:40].strip()
    except Exception:
        return ""


# ============================================================
#  Output helpers
# ============================================================

def get_filename(prefix="screenshot"):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    win = get_foreground_window_title()
    parts = [prefix]
    if win:
        parts.append(win)
    parts.append(ts)
    return "_".join(parts) + ".png"


def get_output_dir():
    d = CONFIG.get("output_dir", "")
    if d and os.path.isdir(d):
        return d
    return os.path.join(os.path.expanduser("~"), "Desktop")


def open_file(path):
    os.startfile(path)


def open_folder(path):
    os.startfile(os.path.dirname(path))


# ============================================================
#  Stealth mode
# ============================================================

def capture_stealth():
    """Call the stealth PowerShell screenshot script. Uses config paths."""
    ps1 = CONFIG.get("stealth_ps1", "")
    if not ps1 or not os.path.exists(ps1):
        # Try default locations
        candidates = [
            os.path.join(SCRIPT_DIR, "educoder_screenshot_enable.ps1"),
            os.path.join(SCRIPT_DIR, "..", "educoder_screenshot_enable.ps1"),
        ]
        ps1 = None
        for c in candidates:
            if os.path.exists(c):
                ps1 = c
                break
        if not ps1:
            log_event("stealth_failed", "ps1_not_found")
            return None, "Stealth script not found. Check config or place educoder_screenshot_enable.ps1 in script directory."

    try:
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", ps1],
            capture_output=True, text=True, timeout=30,
            cwd=os.path.dirname(ps1)
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("Saved:") or line.startswith("File:"):
                path = line.split(":", 1)[1].strip()
                if os.path.exists(path):
                    log_event("stealth_ok", path)
                    return path, None
        dir_ = os.path.dirname(ps1)
        pngs = sorted(
            [f for f in os.listdir(dir_) if f.startswith("screenshot_") and f.endswith(".png")],
            key=lambda f: os.path.getmtime(os.path.join(dir_, f)),
            reverse=True
        )
        if pngs:
            fp = os.path.join(dir_, pngs[0])
            log_event("stealth_ok", fp)
            return fp, None
        log_event("stealth_failed", "no_output")
        return None, result.stderr or "No output found"
    except subprocess.TimeoutExpired:
        log_event("stealth_failed", "timeout")
        return None, "Stealth PowerShell script timed out"
    except Exception as e:
        log_event("stealth_failed", str(e))
        return None, str(e)


# ============================================================
#  Clipboard (via PowerShell)
# ============================================================

def copy_to_clipboard_image(filepath):
    ps = f'''
Add-Type -AssemblyName System.Windows.Forms
$img = [System.Drawing.Image]::FromFile("{filepath}")
[System.Windows.Forms.Clipboard]::SetImage($img)
$img.Dispose()
'''
    subprocess.run(["powershell", "-Command", ps], capture_output=True)


# ============================================================
#  Region Selector (tkinter overlay)
# ============================================================

class RegionSelector:
    def __init__(self):
        self.root = None
        self.canvas = None
        self.rect = None
        self.start_x = self.start_y = 0
        self.result = None

    def select(self):
        import tkinter as tk

        self.root = tk.Tk()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-alpha", 0.3)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="gray")

        self.canvas = tk.Canvas(self.root, cursor="cross", bg="gray", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

        self.root.mainloop()
        return self.result

    def _on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="red", width=2
        )

    def _on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def _on_release(self, event):
        x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
        x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)
        self.result = (x1, y1, x2 - x1, y2 - y1)
        self.root.after(200, self.root.destroy)


# ============================================================
#  Hotkey listener
# ============================================================

class HotkeyListener:
    VK_SNAPSHOT = 0x2C
    VK_CONTROL  = 0x11
    VK_SHIFT    = 0x10
    VK_S        = 0x53
    MOD_PRESSED = 0x8000

    def __init__(self, vk_code=VK_S, modifiers=(VK_CONTROL, VK_SHIFT)):
        self.vk = vk_code
        self.mods = modifiers
        self._running = False
        self._thread = None
        self.callback = None

    def _check(self):
        get_key = ctypes.windll.user32.GetAsyncKeyState
        while self._running:
            mod_pressed = all(get_key(m) & self.MOD_PRESSED for m in self.mods)
            key_pressed = get_key(self.vk) & self.MOD_PRESSED
            if mod_pressed and key_pressed:
                if self.callback:
                    self.callback()
                time.sleep(0.5)
            time.sleep(0.05)

    def start(self, callback):
        self.callback = callback
        self._running = True
        self._thread = threading.Thread(target=self._check, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False


# ============================================================
#  GUI Application
# ============================================================

def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog

    root = tk.Tk()
    root.title(_("title"))
    root.geometry("440x540")
    root.resizable(False, False)
    root.configure(bg="#2b2b2b")

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TButton", font=("Segoe UI", 11), padding=8)
    style.configure("TLabel", background="#2b2b2b", foreground="white", font=("Segoe UI", 10))
    style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"))
    style.configure("Status.TLabel", foreground="#888")

    out_dir = tk.StringVar(value=CONFIG.get("output_dir", get_output_dir()))
    status_var = tk.StringVar()

    # ---- Registry: all widgets that need re-translation on lang switch ----
    _widgets = []  # list of (widget, method, key)  method="text"|"configure"

    def _add(widget, method, key):
        _widgets.append((widget, method, key))

    # Header
    lbl_title = ttk.Label(root, style="Header.TLabel")
    lbl_title.pack(pady=(20, 5)); _add(lbl_title, "text", "title")
    lbl_sub = ttk.Label(root, style="Status.TLabel")
    lbl_sub.pack(); _add(lbl_sub, "text", "subtitle")

    # Language selector
    lang_frame = tk.Frame(root, bg="#2b2b2b")
    lang_frame.pack(pady=(5, 5))
    lang_var = tk.StringVar(value=_current_lang)

    def refresh_ui():
        """Re-apply all translations to registered widgets."""
        root.title(_("title"))
        for w, method, key in _widgets:
            try:
                w.configure(text=_(key))
            except Exception:
                pass
        status_var.set(_("ready"))

    def switch_lang():
        new_lang = lang_var.get()
        if set_lang(new_lang):
            refresh_ui()

    tk.Radiobutton(lang_frame, text="中文", variable=lang_var, value="zh",
                   command=switch_lang, bg="#2b2b2b", fg="white", selectcolor="#2b2b2b",
                   activebackground="#2b2b2b", activeforeground="white").pack(side=tk.LEFT, padx=5)
    tk.Radiobutton(lang_frame, text="English", variable=lang_var, value="en",
                   command=switch_lang, bg="#2b2b2b", fg="white", selectcolor="#2b2b2b",
                   activebackground="#2b2b2b", activeforeground="white").pack(side=tk.LEFT, padx=5)

    ttk.Separator(root, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20, pady=5)

    # Output dir
    dir_frame = tk.Frame(root, bg="#2b2b2b")
    dir_frame.pack(fill=tk.X, padx=20, pady=(5, 5))
    lbl_outdir = ttk.Label(dir_frame)
    lbl_outdir.pack(side=tk.LEFT); _add(lbl_outdir, "text", "output_dir")
    # append ":" manually since it's not part of the key
    dir_entry = tk.Entry(dir_frame, textvariable=out_dir, bg="#3c3c3c", fg="white",
                         insertbackground="white", relief=tk.FLAT, font=("Consolas", 9))
    dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
    ttk.Button(dir_frame, text="…", width=3,
               command=lambda: out_dir.set(filedialog.askdirectory(initialdir=out_dir.get()) or out_dir.get())
               ).pack(side=tk.RIGHT)

    ttk.Separator(root, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20, pady=10)

    # Capture buttons
    btn_frame = tk.Frame(root, bg="#2b2b2b")
    btn_frame.pack(padx=20, pady=5)

    def do_capture(mode):
        def _run():
            out = out_dir.get()
            if not os.path.isdir(out):
                root.after(0, lambda: messagebox.showerror(_("err_title"), _("err_no_dir")))
                return

            status_var.set(_("capturing"))
            root.update()

            result = None
            try:
                if mode == "full":
                    w, h, raw = capture_fullscreen()
                    fp = os.path.join(out, get_filename(_("file_prefix_full")))
                    save_screenshot(w, h, raw, fp)
                    result = fp
                    log_event("capture_full", fp)
                elif mode == "region":
                    root.withdraw()
                    time.sleep(0.3)
                    sel = RegionSelector().select()
                    root.deiconify()
                    if sel is None:
                        status_var.set(_("region_cancelled"))
                        return
                    x, y, rw, rh = sel
                    if rw < 5 or rh < 5:
                        status_var.set(_("region_too_small"))
                        return
                    w, h, raw = capture_region(x, y, rw, rh)
                    fp = os.path.join(out, get_filename(_("file_prefix_region")))
                    save_screenshot(w, h, raw, fp)
                    result = fp
                    log_event("capture_region", fp)
                elif mode == "stealth":
                    result, err = capture_stealth()
                    if err:
                        root.after(0, lambda: messagebox.showerror(_("err_title"), err))
                        status_var.set(_("stealth_failed"))
                        return
                elif mode == "clip":
                    w, h, raw = capture_fullscreen()
                    fp = os.path.join(out, get_filename(_("file_prefix_clip")))
                    save_screenshot(w, h, raw, fp)
                    copy_to_clipboard_image(fp)
                    result = fp
                    log_event("capture_clip", fp)

                if result:
                    status_var.set(f"{_('saved')}: {os.path.basename(result)}")
                    if mode != "clip":
                        copy_to_clipboard_image(result)
                        status_var.set(f"{_('saved_clip')}: {os.path.basename(result)}")
            except CaptureBusy:
                status_var.set("Capture busy — please wait")
                log_event("capture_busy")
            except Exception as e:
                log_event("capture_error", str(e))
                status_var.set(f"Error: {str(e)[:60]}")

        threading.Thread(target=_run, daemon=True).start()

    btn_configs = [
        ("btn_full",    "full",    "#4a90d9"),
        ("btn_region",  "region",  "#50b86c"),
        ("btn_stealth", "stealth", "#e8853b"),
        ("btn_clip",    "clip",    "#9b59b6"),
    ]

    for key, mode, color in btn_configs:
        btn = tk.Button(btn_frame, command=lambda m=mode: do_capture(m),
                        bg=color, fg="white", font=("Segoe UI", 11, "bold"),
                        relief=tk.FLAT, padx=12, pady=8, cursor="hand2",
                        activebackground=color, activeforeground="white")
        btn.pack(fill=tk.X, pady=4, ipady=2)
        _add(btn, "text", key)

    ttk.Separator(root, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20, pady=10)

    # Timer section
    auto_frame = tk.Frame(root, bg="#2b2b2b")
    auto_frame.pack(fill=tk.X, padx=20, pady=5)

    lbl_timed = ttk.Label(auto_frame)
    lbl_timed.pack(side=tk.LEFT); _add(lbl_timed, "text", "timed_label")
    interval_var = tk.StringVar(value="")
    tk.Entry(auto_frame, textvariable=interval_var, width=5, bg="#3c3c3c", fg="white",
             insertbackground="white", relief=tk.FLAT, font=("Consolas", 11)).pack(side=tk.LEFT, padx=5)

    def start_interval():
        try:
            sec = float(interval_var.get())
            if sec <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(_("err_title"), _("err_positive"))
            return

        def _loop():
            out = out_dir.get()
            count = 0
            while getattr(threading.current_thread(), "_interval_running", True):
                w, h, raw = capture_fullscreen()
                fp = os.path.join(out, get_filename(_("file_prefix_interval") + f"_{count:04d}"))
                save_screenshot(w, h, raw, fp)
                count += 1
                status_var.set(f"#{count}: {os.path.basename(fp)}")
                time.sleep(sec)

        t = threading.Thread(target=_loop, daemon=True)
        t._interval_running = True
        t.start()
        interval_var.set("")

    btn_start = ttk.Button(auto_frame, command=start_interval)
    btn_start.pack(side=tk.LEFT, padx=5); _add(btn_start, "text", "btn_start")

    def stop_interval():
        for t in threading.enumerate():
            if hasattr(t, "_interval_running"):
                t._interval_running = False
        status_var.set(_("interval_stopped"))

    btn_stop = ttk.Button(auto_frame, command=stop_interval)
    btn_stop.pack(side=tk.LEFT); _add(btn_stop, "text", "btn_stop")

    # Hotkey toggle
    hotkey_var = tk.BooleanVar(value=False)

    def toggle_hotkey():
        if hotkey_var.get():
            listener.start(lambda: do_capture("full"))
            status_var.set(_("hotkey_on"))
        else:
            listener.stop()
            status_var.set(_("hotkey_off"))

    hotkey_frame = tk.Frame(root, bg="#2b2b2b")
    hotkey_frame.pack(fill=tk.X, padx=20, pady=5)
    chk_hotkey = ttk.Checkbutton(hotkey_frame, variable=hotkey_var, command=toggle_hotkey)
    chk_hotkey.pack(side=tk.LEFT); _add(chk_hotkey, "configure", "hotkey_toggle")

    listener = HotkeyListener()

    ttk.Separator(root, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20, pady=(10, 5))

    # Status
    ttk.Label(root, textvariable=status_var, style="Status.TLabel").pack(pady=(0, 10))

    # Open folder
    btn_folder = ttk.Button(root, command=lambda: open_folder(out_dir.get()))
    btn_folder.pack(pady=(0, 15)); _add(btn_folder, "text", "btn_open_folder")

    # Initial translation
    refresh_ui()

    root.protocol("WM_DELETE_WINDOW", lambda: (listener.stop(), root.destroy()))
    root.mainloop()


# ============================================================
#  CLI Entry
# ============================================================

def main():
    global _current_lang, _AUTO_DETECTED

    args = sys.argv[1:]

    lang_explicit = False
    if "--lang" in args:
        try:
            idx = args.index("--lang")
            new_lang = args[idx + 1]
            if set_lang(new_lang):
                print(f"[*] {_('lang_switched', lang_name=_('lang_zh') if new_lang == 'zh' else _('lang_en'))}")
                lang_explicit = True
            else:
                print(f"Unknown language: {new_lang}. Use 'zh' or 'en'.")
            args.pop(idx)
            args.pop(idx)
        except (ValueError, IndexError):
            pass
    if not lang_explicit:
        env_lang = os.environ.get("SCREENSHOT_LANG", "")
        if env_lang in T:
            _current_lang = env_lang
        else:
            _current_lang = detect_lang()
    _AUTO_DETECTED = True

    out_dir = CONFIG.get("output_dir", get_output_dir())

    if len(args) == 0:
        run_gui()
        return

    if "--help" in args or "-h" in args:
        # Show bilingual help
        print("=" * 60)
        print("  PC Screenshot Tool / PC 截图工具")
        print("=" * 60)
        print()
        print("  GUI mode:")
        print("    python pc_screenshot.py")
        print()
        print("  CLI modes:")
        print("    --full              Full screen screenshot")
        print("    --region            Select region with mouse")
        print("    --stealth           Anti-cheat stealth mode")
        print("    --clip              Full screen => clipboard")
        print("    --hotkey            Start Ctrl+Shift+S listener")
        print("    --interval N        Capture every N seconds")
        print("    --out <dir>         Set output directory")
        print("    --lang zh|en        Switch language")
        print("    --open              Open image after capture")
        print("    --folder            Open output folder after capture")
        print()
        return

    if "--hotkey" in args:
        if CONFIG.get("hotkey_require_admin", False):
            try:
                is_admin = ctypes.windll.shell32.IsUserAnAdmin()
                if not is_admin:
                    print("ERROR: Hotkey mode requires Administrator (set in config).")
                    return
            except Exception:
                pass
        if not CONFIG.get("hotkey_enabled", True):
            print("ERROR: Hotkey mode disabled in config.")
            return
        print(_("hotkey_start"))
        log_event("hotkey_start")
        listener = HotkeyListener()
        count = [0]

        def on_hotkey():
            count[0] += 1
            try:
                w, h, raw = capture_fullscreen()
                fp = os.path.join(out_dir, get_filename(_("file_prefix_hotkey") + f"_{count[0]:04d}"))
                save_screenshot(w, h, raw, fp)
                log_event("capture_hotkey", fp)
                print(f"  [#{count[0]}] {fp}")
            except CaptureBusy:
                pass

        listener.start(on_hotkey)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(_("hotkey_stop"))
            listener.stop()
        return

    if "--interval" in args:
        try:
            idx = args.index("--interval")
            sec = float(args[idx + 1])
        except (ValueError, IndexError):
            print(_("interval_usage"))
            return
        print(_("interval_start", sec=sec))
        log_event("interval_start", f"interval={sec}s")
        count = 0
        try:
            while True:
                try:
                    w, h, raw = capture_fullscreen()
                    fp = os.path.join(out_dir, get_filename(_("file_prefix_interval") + f"_{count:04d}"))
                    save_screenshot(w, h, raw, fp)
                    log_event("capture_interval", fp)
                    print(f"  [#{count}] {fp}")
                    count += 1
                except CaptureBusy:
                    pass
                time.sleep(sec)
        except KeyboardInterrupt:
            log_event("interval_stop", f"count={count}")
            print(_("interval_stop", count=count))
        return

    if "--out" in args:
        try:
            idx = args.index("--out")
            out_dir = args[idx + 1]
        except (ValueError, IndexError):
            pass

    filepath = None

    if "--stealth" in args:
        filepath, err = capture_stealth()
        if err:
            print(f"ERROR: {err}")
            return
    elif "--region" in args:
        print(_("select_region"))
        sel = RegionSelector().select()
        if sel is None:
            print(_("cancelled"))
            return
        x, y, rw, rh = sel
        w, h, raw = capture_region(x, y, rw, rh)
        filepath = os.path.join(out_dir, get_filename(_("file_prefix_region")))
        save_screenshot(w, h, raw, filepath)
        log_event("capture_region", filepath)
    else:
        w, h, raw = capture_fullscreen()
        prefix = _("file_prefix_clip") if "--clip" in args else _("file_prefix_full")
        filepath = os.path.join(out_dir, get_filename(prefix))
        save_screenshot(w, h, raw, filepath)
        log_event("capture_full" if "--full" in args else "capture_clip", filepath)

    if filepath:
        print(f"{_('saved')}: {filepath}")

        if "--open" in args:
            open_file(filepath)
        if "--folder" in args:
            open_folder(filepath)

        if "--clip" in args or "--full" in args:
            try:
                copy_to_clipboard_image(filepath)
                print(_("clip_copied"))
            except Exception:
                pass


if __name__ == "__main__":
    main()
