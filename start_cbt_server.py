"""
Modern CBT Server Controller (ttkbootstrap edition)
Features:
- Dark/Light mode toggle
- Live status indicator
- Open in browser button
- Minimize to system tray
"""

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import subprocess
import threading
import socket
import webbrowser
import pystray
from PIL import Image, ImageDraw

from run_server import start_waitress_server


class ServerStarter:

    def __init__(self):
        self.app = ttk.Window(themename="flatly")
        self.app.title("Arndale CBT Server Controller")
        self.app.state('zoomed')

        self.server_process = None
        self.dark_mode = False

        self.lan_ip = self.get_lan_ip()
        self.setup_ui()

    def get_lan_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def setup_ui(self):

        top = ttk.Frame(self.app, padding=15)
        top.pack(fill=X)

        ttk.Label(top, text="Arndale CBT Server", font=("Segoe UI", 20, "bold")).pack(side=LEFT)

        self.theme_btn = ttk.Button(top, text="🌙 Dark Mode", bootstyle="secondary",
                                    command=self.toggle_theme)
        self.theme_btn.pack(side=RIGHT, padx=5)

        self.tray_btn = ttk.Button(top, text="Minimize to Tray", bootstyle="warning",
                                  command=self.minimize_to_tray)
        self.tray_btn.pack(side=RIGHT, padx=5)

        # Info Card
        info = ttk.Labelframe(self.app, text="Server Information", padding=15)
        info.pack(fill=X, padx=15, pady=10)

        ttk.Label(info, text="IP Address:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky=W)
        ttk.Label(info, text=self.lan_ip, font=("Consolas", 13)).grid(row=1, column=0, sticky=W, pady=5)

        ttk.Label(info, text="Access URL:", font=("Segoe UI", 10, "bold")).grid(row=0, column=1, sticky=W, padx=40)
        self.url = f"http://{self.lan_ip}:5000"
        ttk.Label(info, text=self.url, font=("Consolas", 13)).grid(row=1, column=1, sticky=W, padx=40)

        self.open_btn = ttk.Button(info, text="Open in Browser", bootstyle="info",
                                   command=self.open_browser)
        self.open_btn.grid(row=1, column=2, padx=10)

        # Controls
        controls = ttk.Frame(self.app, padding=15)
        controls.pack(fill=X)

        self.start_btn = ttk.Button(controls, text="Start Server", bootstyle="success",
                                    command=self.start_server)
        self.start_btn.pack(side=LEFT, padx=5)

        self.stop_btn = ttk.Button(controls, text="Stop Server", bootstyle="danger",
                                   state=DISABLED, command=self.stop_server)
        self.stop_btn.pack(side=LEFT, padx=5)

        # Status Indicator
        status_frame = ttk.Frame(controls)
        status_frame.pack(side=RIGHT)

        self.canvas = tk.Canvas(status_frame, width=16, height=16, highlightthickness=0)
        self.canvas.pack(side=LEFT, padx=5)
        self.status_dot = self.canvas.create_oval(2, 2, 14, 14, fill="red")

        self.status_label = ttk.Label(status_frame, text="Stopped")
        self.status_label.pack(side=LEFT)

        # Logs
        log_frame = ttk.Labelframe(self.app, text="Server Log", padding=10)
        log_frame.pack(fill=BOTH, expand=True, padx=15, pady=10)

        self.log_area = ScrolledText(log_frame, height=15, font=("Consolas", 10))
        self.log_area.pack(fill=BOTH, expand=True)

    def toggle_theme(self):
        if self.dark_mode:
            self.app.style.theme_use("flatly")
            self.theme_btn.config(text="🌙 Dark Mode")
        else:
            self.app.style.theme_use("darkly")
            self.theme_btn.config(text="☀ Light Mode")
        self.dark_mode = not self.dark_mode

    def open_browser(self):
        webbrowser.open(self.url)

    def update_status(self, running):
        if running:
            self.canvas.itemconfig(self.status_dot, fill="green")
            self.status_label.config(text="Running")
        else:
            self.canvas.itemconfig(self.status_dot, fill="red")
            self.status_label.config(text="Stopped")

    def start_server(self):
        self.start_btn.config(state=DISABLED)
        self.stop_btn.config(state=NORMAL)
        self.update_status(True)

        thread = threading.Thread(target=self.run_server)
        thread.daemon = True
        thread.start()

        self.log("Server started")
        self.log(self.url)

    def stop_server(self):
        if self.server_process:
            self.server_process.terminate()

        self.start_btn.config(state=NORMAL)
        self.stop_btn.config(state=DISABLED)
        self.update_status(False)
        self.log("Server stopped")

    def run_server(self):
        try:
            self.server_thread = threading.Thread(target=start_waitress_server)
            self.server_thread.daemon = True
            self.server_thread.start()

        except Exception as e:
            self.app.after(0, self.log, f"Error: {e}")

    def log(self, msg):
        self.log_area.insert(END, msg + "\n")
        self.log_area.see(END)

    # -------- SYSTEM TRAY --------
    def minimize_to_tray(self):
        self.app.withdraw()

        image = Image.new('RGB', (64, 64), color='blue')
        draw = ImageDraw.Draw(image)
        draw.text((10, 20), "CBT", fill='white')

        menu = (
            pystray.MenuItem("Restore", self.restore_window),
            pystray.MenuItem("Exit", self.exit_app)
        )

        self.tray = pystray.Icon("CBT Server", image, "CBT Server", menu)
        threading.Thread(target=self.tray.run, daemon=True).start()

    def restore_window(self, icon=None, item=None):
        self.app.deiconify()
        self.tray.stop()

    def exit_app(self, icon=None, item=None):
        self.tray.stop()
        self.app.quit()

    def run(self):
        self.app.mainloop()


if __name__ == "__main__":
    ServerStarter().run()