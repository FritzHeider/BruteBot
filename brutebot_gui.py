#!/usr/bin/env python3
"""Simple Tkinter GUI wrapper for BruteBot's CLI workflow."""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import scrolledtext


class BruteBotGUI(tk.Tk):
    """Tkinter application that orchestrates BruteBot via subprocess."""

    def __init__(self):
        super().__init__()
        self.title("BruteBot GUI")
        self.resizable(False, False)

        self.process = None
        self.process_thread = None
        self.output_queue: "queue.Queue[str]" = queue.Queue()
        self.running = False

        self._build_widgets()
        self._layout_widgets()

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------
    def _build_widgets(self):
        self.target_var = tk.StringVar()
        self.username_var = tk.StringVar()
        self.password_file_var = tk.StringVar()
        self.uid_var = tk.StringVar()
        self.pid_var = tk.StringVar()
        self.button_name_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="headless")
        self.wait_time_var = tk.StringVar(value="1")
        self.proxy_var = tk.StringVar()

        self.target_entry = tk.Entry(self, width=50, textvariable=self.target_var)
        self.username_entry = tk.Entry(self, width=30, textvariable=self.username_var)
        self.password_entry = tk.Entry(self, width=38, textvariable=self.password_file_var)
        self.uid_entry = tk.Entry(self, width=30, textvariable=self.uid_var)
        self.pid_entry = tk.Entry(self, width=30, textvariable=self.pid_var)
        self.button_entry = tk.Entry(self, width=30, textvariable=self.button_name_var)
        self.wait_entry = tk.Entry(self, width=10, textvariable=self.wait_time_var)
        self.proxy_entry = tk.Entry(self, width=30, textvariable=self.proxy_var)

        self.mode_menu = tk.OptionMenu(self, self.mode_var, "headless", "visible")
        self.mode_menu.configure(width=10)

        self.browse_button = tk.Button(self, text="Browse", command=self._browse_password_file)
        self.run_button = tk.Button(self, text="Run", command=self._start_bruteforce)
        self.stop_button = tk.Button(self, text="Stop", state=tk.DISABLED, command=self._stop_bruteforce)

        self.log_output = scrolledtext.ScrolledText(self, width=80, height=20, state=tk.DISABLED)

    def _layout_widgets(self):
        padding = {"padx": 8, "pady": 4, "sticky": "w"}

        tk.Label(self, text="Target URL:").grid(row=0, column=0, **padding)
        self.target_entry.grid(row=0, column=1, columnspan=3, **padding)

        tk.Label(self, text="Username:").grid(row=1, column=0, **padding)
        self.username_entry.grid(row=1, column=1, **padding)

        tk.Label(self, text="Password list:").grid(row=2, column=0, **padding)
        self.password_entry.grid(row=2, column=1, columnspan=2, **padding)
        self.browse_button.grid(row=2, column=3, **padding)

        tk.Label(self, text="Username field ID:").grid(row=3, column=0, **padding)
        self.uid_entry.grid(row=3, column=1, **padding)

        tk.Label(self, text="Password field ID:").grid(row=4, column=0, **padding)
        self.pid_entry.grid(row=4, column=1, **padding)

        tk.Label(self, text="Button text/value:").grid(row=5, column=0, **padding)
        self.button_entry.grid(row=5, column=1, **padding)

        tk.Label(self, text="Browser mode:").grid(row=6, column=0, **padding)
        self.mode_menu.grid(row=6, column=1, **padding)

        tk.Label(self, text="Wait time (s):").grid(row=6, column=2, **padding)
        self.wait_entry.grid(row=6, column=3, **padding)

        tk.Label(self, text="Proxy (optional):").grid(row=7, column=0, **padding)
        self.proxy_entry.grid(row=7, column=1, columnspan=3, **padding)

        self.run_button.grid(row=8, column=2, **padding)
        self.stop_button.grid(row=8, column=3, **padding)

        self.log_output.grid(row=9, column=0, columnspan=4, padx=8, pady=(4, 8), sticky="nsew")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _browse_password_file(self):
        initial_dir = os.path.dirname(self.password_file_var.get() or os.getcwd())
        file_path = filedialog.askopenfilename(initialdir=initial_dir, title="Select password list")
        if file_path:
            self.password_file_var.set(file_path)

    def _start_bruteforce(self):
        if self.running:
            return

        data = self._collect_form_data()
        if data is None:
            return

        self._clear_log()
        self._append_log("Launching BruteBot...\n")

        self.run_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)
        self.running = True

        self.process_thread = threading.Thread(target=self._run_subprocess, args=(data,), daemon=True)
        self.process_thread.start()
        self.after(100, self._poll_output_queue)

    def _stop_bruteforce(self):
        if self.process and self.running:
            try:
                self.process.terminate()
            except OSError:
                pass
        self._append_log("Attempting to stop BruteBot...\n")

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    def _collect_form_data(self):
        required_fields = {
            "Target URL": self.target_var.get().strip(),
            "Username": self.username_var.get().strip(),
            "Password list": self.password_file_var.get().strip(),
            "Username field ID": self.uid_var.get().strip(),
            "Password field ID": self.pid_var.get().strip(),
            "Button text/value": self.button_name_var.get().strip(),
        }

        missing = [label for label, value in required_fields.items() if not value]
        if missing:
            messagebox.showerror("Missing information", f"Please fill out: {', '.join(missing)}")
            return None

        password_path = required_fields["Password list"]
        if not os.path.isfile(password_path):
            messagebox.showerror("Password list not found", "The selected password list could not be located.")
            return None

        wait_time = self.wait_time_var.get().strip() or "1"
        try:
            float(wait_time)
        except ValueError:
            messagebox.showerror("Invalid wait time", "Please enter a numeric wait time value in seconds.")
            return None

        return {
            "target": required_fields["Target URL"],
            "username": required_fields["Username"],
            "password_file": password_path,
            "uid": required_fields["Username field ID"],
            "pid": required_fields["Password field ID"],
            "button": required_fields["Button text/value"],
            "mode": self.mode_var.get(),
            "wait": wait_time,
            "proxy": self.proxy_var.get().strip(),
        }

    # ------------------------------------------------------------------
    # Subprocess handling
    # ------------------------------------------------------------------
    def _run_subprocess(self, form_data):
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "BruteBot.py"))

        command = [
            sys.executable,
            script_path,
            "-t",
            form_data["target"],
            "-u",
            form_data["username"],
            "-p",
            os.path.basename(form_data["password_file"]),
            "--uid",
            form_data["uid"],
            "--pid",
            form_data["pid"],
            "--bname",
            form_data["button"],
            "-m",
            form_data["mode"],
            "-s",
            form_data["wait"],
        ]

        if form_data["proxy"]:
            command.extend(["--proxy", form_data["proxy"]])

        password_cwd = os.path.dirname(form_data["password_file"])
        cwd = password_cwd if password_cwd else os.path.dirname(script_path)

        try:
            self.process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=cwd,
                bufsize=1,
            )
        except FileNotFoundError:
            self.output_queue.put("Python executable not found.\n")
            self.output_queue.put("Ensure Python 3 is installed and accessible.\n")
            self._mark_process_complete()
            return
        except Exception as exc:  # pragma: no cover - defensive safety net
            self.output_queue.put(f"Failed to launch BruteBot: {exc}\n")
            self._mark_process_complete()
            return

        try:
            self.process.stdin.write("1\n")
            self.process.stdin.flush()
        except Exception:
            pass

        try:
            for line in self.process.stdout:
                self.output_queue.put(line)
        finally:
            self.process.stdout.close()
            self.process.wait()
            self._mark_process_complete()

    def _mark_process_complete(self):
        self.output_queue.put("\nBruteBot finished.\n")
        self.running = False
        self.after(0, self._on_process_complete)

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------
    def _poll_output_queue(self):
        while True:
            try:
                line = self.output_queue.get_nowait()
            except queue.Empty:
                break
            else:
                self._append_log(line)

        if self.running:
            self.after(100, self._poll_output_queue)

    def _append_log(self, text):
        self.log_output.configure(state=tk.NORMAL)
        self.log_output.insert(tk.END, text)
        self.log_output.see(tk.END)
        self.log_output.configure(state=tk.DISABLED)

    def _clear_log(self):
        self.log_output.configure(state=tk.NORMAL)
        self.log_output.delete("1.0", tk.END)
        self.log_output.configure(state=tk.DISABLED)

    def _on_process_complete(self):
        self.run_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.DISABLED)
        self.process = None
        self.process_thread = None


def main():
    app = BruteBotGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
