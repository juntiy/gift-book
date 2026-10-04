# -*- coding: utf-8 -*-
"""
电子礼簿 桌面外壳
- 内置一个本地 HTTP 服务，提供打包进来的 gift-book 站点（index.html + static/）
- 用 pywebview (Edge WebView2) 加载 http://127.0.0.1:<PORT>/index.html
- 使用固定端口，保证 IndexedDB / localStorage 的“来源(origin)”在每次启动间保持不变，
  从而让礼簿数据持续保存
- 固定端口同时充当单实例锁：端口已被占用说明程序已在运行

【数据持久化（关键）】
- 必须关闭 private_mode（默认是 True，会导致 WebView2 把用户数据放进临时目录，退出即清空）
- 并把 storage_path 固定到用户配置目录（与 exe 解压目录解耦），
  这样礼簿数据（IndexedDB）跨启动、跨 exe 移动/重装都安全保留
"""
import os
import sys
import time
import socket
import threading

import ctypes

PORT = 8273
APP_TITLE = "电子礼簿"


def _msgbox(text, title=APP_TITLE):
    try:
        ctypes.windll.user32.MessageBoxW(0, str(text), str(title), 0x10)
    except Exception:
        print(text)


def _resolve_root():
    if getattr(sys, "frozen", False):
        # PyInstaller onefile 解压目录
        return os.path.join(sys._MEIPASS, "gift-book")
    # 开发模式：launcher.py 位于 build/，站点位于上一级 gift-book/
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", "gift-book"))


def _user_data_path():
    """持久化 WebView2 用户数据目录（IndexedDB / 礼簿数据所在地）。

    放在用户配置目录（%LOCALAPPDATA%/电子礼簿/webview_data），
    与 exe 解压目录解耦：即使移动或重装 exe，数据也不会丢。
    """
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "电子礼簿", "webview_data")
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    return path


ROOT = _resolve_root()


class _Handler:
    """动态构造请求处理器，绑定到当前 ROOT 目录。"""

    def __new__(cls):
        from http.server import SimpleHTTPRequestHandler

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=ROOT, **kwargs)

            def log_message(self, *args):
                pass

            def end_headers(self):
                # 关闭缓存，避免更新后网页仍加载旧资源
                self.send_header("Cache-Control", "no-store")
                super().end_headers()

        return Handler


def main():
    # 单实例检测：固定端口即锁
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        probe.bind(("127.0.0.1", PORT))
    except OSError:
        _msgbox("《电子礼簿》已在运行中，请勿重复打开。")
        sys.exit(1)
    probe.close()

    from http.server import ThreadingHTTPServer

    server = ThreadingHTTPServer(("127.0.0.1", PORT), _Handler())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.5)

    import webview

    webview.create_window(
        APP_TITLE,
        f"http://127.0.0.1:{PORT}/index.html",
        width=1280,
        height=860,
        min_size=(900, 600),
    )
    try:
        # 关键：关闭隐私模式 + 固定持久化数据目录，保证礼簿数据不丢失
        webview.start(private_mode=False, storage_path=_user_data_path())
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
