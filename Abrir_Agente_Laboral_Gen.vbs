' Punto de entrada de Agente Laboral Gen -- doble click, sin consola.
' Agente Laboral Gen corre permanentemente en andolserver (Streamlit +
' systemd) -- este script solo abre el navegador apuntando a esa
' instancia. Ya NO crea entorno virtual, no instala dependencias ni
' levanta Streamlit local.

Option Explicit

CreateObject("WScript.Shell").Run "http://192.168.68.106:8501", 1, False
