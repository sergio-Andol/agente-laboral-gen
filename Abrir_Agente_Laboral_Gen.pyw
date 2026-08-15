"""
Lanzador de Agente Laboral Gen -- abre el navegador apuntando a la
instancia que corre permanentemente en andolserver (Streamlit + systemd).

Ya NO crea ni usa .venv, no instala dependencias ni levanta Streamlit
local -- eso lo maneja el servidor. Sin consola, sin ventana: solo abre
el navegador.
"""
import webbrowser

URL = "http://192.168.68.106:8501"

if __name__ == "__main__":
    webbrowser.open(URL)
