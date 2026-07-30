"""
Lanzador grafico de Agente Laboral Gen -- sin consola.

Reemplaza a Abrir_Agente_Laboral_Gen.bat como via principal para usuarios no
tecnicos: crea o reutiliza el entorno virtual .venv, instala dependencias,
pregunta por Bumeran con una ventana normal (tkinter, boton Si/No) y despues
levanta Streamlit y abre el navegador. El .bat sigue existiendo como respaldo
tecnico.

100% Windows (usa subprocess.CREATE_NO_WINDOW, solo disponible en Windows).
No postula, no guarda el CV, no agrega historial, no toca el registro de
Windows y no pide permisos de administrador -- mismas garantias que el resto
del proyecto.
"""
import os
import socket
import subprocess
import sys
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(BASE_DIR, ".venv")
VENV_PYTHON = os.path.join(VENV_DIR, "Scripts", "python.exe")
REQUIREMENTS = os.path.join(BASE_DIR, "requirements.txt")
PORT = 8501

CREATE_NO_WINDOW = 0x08000000


def _run_hidden(args, timeout=None):
    """subprocess.run sin ninguna ventana de consola propia. Necesario:
    aunque este script corre con pythonw (sin consola), un python.exe/pip.exe
    hijo abriria su propia consola negra si no se pasa este flag."""
    return subprocess.run(
        args,
        creationflags=CREATE_NO_WINDOW,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=BASE_DIR,
        timeout=timeout,
    )


def _popen_hidden(args):
    return subprocess.Popen(
        args,
        creationflags=CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=BASE_DIR,
    )


class Lanzador(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Agente Laboral Gen")
        self.geometry("440x180")
        self.resizable(False, False)
        self.proceso_streamlit = None

        self.label_estado = tk.Label(
            self, text="Preparando aplicación...", font=("Segoe UI", 11),
            wraplength=400, justify="center",
        )
        self.label_estado.pack(pady=(30, 15))

        self.barra = ttk.Progressbar(self, mode="indeterminate", length=360)
        self.barra.pack(pady=5)
        self.barra.start(12)

        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)
        self.after(200, self._paso_1_venv)

    def _estado(self, texto):
        self.label_estado.config(text=texto)
        self.update_idletasks()

    def _error(self, texto):
        self.barra.stop()
        messagebox.showerror("Agente Laboral Gen", texto)
        self.destroy()

    def _paso_1_venv(self):
        if os.path.exists(VENV_PYTHON):
            self.after(50, self._paso_2_deps)
            return
        self._estado("Creando entorno virtual...")
        try:
            resultado = _run_hidden([sys.executable, "-m", "venv", VENV_DIR])
        except Exception as exc:
            self._error(f"No se pudo crear el entorno virtual:\n{exc}")
            return
        if resultado.returncode != 0 or not os.path.exists(VENV_PYTHON):
            self._error("No se pudo crear el entorno virtual (.venv).")
            return
        self.after(50, self._paso_2_deps)

    def _paso_2_deps(self):
        self._estado("Instalando dependencias...")
        try:
            _run_hidden([VENV_PYTHON, "-m", "pip", "install", "--upgrade", "pip"])
            resultado = _run_hidden([VENV_PYTHON, "-m", "pip", "install", "-r", REQUIREMENTS])
        except Exception as exc:
            self._error(f"No se pudieron instalar las dependencias:\n{exc}")
            return
        if resultado.returncode != 0:
            detalle = resultado.stderr.decode(errors="ignore")[-500:]
            self._error(f"Falló la instalación de dependencias:\n{detalle}")
            return
        self.after(50, self._paso_3_bumeran)

    def _paso_3_bumeran(self):
        self._estado("Verificando Bumeran...")
        script_check = (
            "from playwright.sync_api import sync_playwright\n"
            "n = sync_playwright().start()\n"
            "b = n.chromium.launch()\n"
            "b.close()\n"
            "n.stop()\n"
        )
        try:
            resultado = _run_hidden([VENV_PYTHON, "-c", script_check], timeout=20)
            disponible = resultado.returncode == 0
        except Exception:
            disponible = False

        if disponible:
            self.after(50, self._paso_4_iniciar)
            return

        quiere = messagebox.askyesno(
            "Agente Laboral Gen",
            "Bumeran permite ampliar la búsqueda laboral, pero requiere "
            "instalar Chromium. Puede tardar algunos minutos.\n\n"
            "¿Querés instalar soporte para Bumeran ahora?",
        )
        if not quiere:
            self.after(50, self._paso_4_iniciar)
            return

        self._estado("Instalando soporte para Bumeran...")
        try:
            _run_hidden([VENV_PYTHON, "-m", "pip", "install", "playwright"])
            _run_hidden([VENV_PYTHON, "-m", "playwright", "install", "chromium"], timeout=900)
        except Exception:
            messagebox.showwarning(
                "Agente Laboral Gen",
                "No se pudo instalar Bumeran. La app sigue funcionando igual, "
                "solo con Computrabajo.",
            )
        self.after(50, self._paso_4_iniciar)

    def _paso_4_iniciar(self):
        self._estado("Iniciando aplicación...")
        try:
            self.proceso_streamlit = _popen_hidden([
                VENV_PYTHON, "-m", "streamlit", "run",
                os.path.join(BASE_DIR, "ui", "app.py"),
                "--server.port", str(PORT),
                "--server.headless", "true",
            ])
        except Exception as exc:
            self._error(f"No se pudo iniciar la aplicación:\n{exc}")
            return
        self.after(300, self._esperar_servidor, 0)

    def _esperar_servidor(self, intentos):
        if self.proceso_streamlit.poll() is not None:
            self._error("La aplicación se cerró inesperadamente al iniciar.")
            return
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            try:
                s.connect(("127.0.0.1", PORT))
                listo = True
            except OSError:
                listo = False
        if listo:
            self._paso_5_navegador()
            return
        if intentos > 60:
            self._error("La aplicación tardó demasiado en iniciar.")
            return
        self.after(500, self._esperar_servidor, intentos + 1)

    def _paso_5_navegador(self):
        self._estado("Abriendo navegador...")
        webbrowser.open(f"http://localhost:{PORT}")
        self.after(600, self._listo)

    def _listo(self):
        self.barra.stop()
        self.barra.pack_forget()
        self._estado(
            "Agente Laboral Gen está en ejecución en\n"
            f"http://localhost:{PORT}\n\n"
            "Cerrá esta ventana para salir de la app."
        )

    def _al_cerrar(self):
        if self.proceso_streamlit and self.proceso_streamlit.poll() is None:
            self.proceso_streamlit.terminate()
        self.destroy()


if __name__ == "__main__":
    app = Lanzador()
    app.mainloop()
