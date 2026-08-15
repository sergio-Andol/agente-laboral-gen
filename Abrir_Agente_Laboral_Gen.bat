@echo off
rem Agente Laboral Gen corre permanentemente en andolserver (Streamlit +
rem systemd) -- este lanzador solo abre el navegador apuntando a esa
rem instancia. Ya NO crea entorno virtual, no instala dependencias ni
rem levanta Streamlit local (eso lo maneja el servidor).
start "" "http://192.168.68.106:8501"
exit /b 0
