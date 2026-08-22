# Continuidad — Agente Laboral Gen

> Generado 2026-08-22. Estado verificado en disco antes de escribir esto (no de memoria). Si algo acá contradice `git status`/`git log` reales al momento de leer esto, **confiá en el repo, no en este documento**.

## 1. Proyecto y carpeta actual

- Nombre: **Agente Laboral Gen**.
- Carpeta de trabajo: `S:\Proyectos\agente-laboral-gen` (Windows, unidad de red).
- Es el **mismo filesystem** que `/srv/apps/agente-laboral-gen` en el servidor Ubuntu `andolserver` (confirmado por `pyvenv.cfg` del `.venv` del server, que referencia esa ruta) — editar en S: edita directamente lo que corre en el server.
- Repo GitHub: `https://github.com/sergio-Andol/agente-laboral-gen` (remote `origin`, rama `main`).
- **No confundir** con otras carpetas que aparecieron en sesiones previas y NO son este proyecto: `C:\Users\sergi\Documents\Buscador de trabajo\Agente-Laboral-Gen` (copia local vieja, pre-migración al server) y `C:\Users\sergi\Downloads\agente-laboral-gen-main` (cwd default de la sesión de Claude Code, irrelevante para el proyecto).

## 2. Objetivo del proyecto

App Streamlit local/server que:
- analiza un CV (PDF/DOCX/TXT) 100% local, por reglas/keywords, sin IA externa;
- detecta perfil (nombre, ubicación, skills, seniority, categorías);
- busca ofertas reales en Computrabajo (siempre) y Bumeran (opcional, requiere Playwright+Chromium);
- clasifica cada oferta (POSTULAR/REVISAR/DESCARTAR) con motivo visible;
- exporta a Excel con formato;
- **no postula nunca**, no guarda el CV, no guarda historial.

## 3. Arquitectura y archivos importantes

```
buscador_core.py          orquesta demo/real, filtros, wrappers de export
core/
  classifier.py           detectar_categoria() + clasificar_decision()
  constants.py             CATEGORIAS_KEYWORDS, ZONAS, seguridad (DRY_RUN_POSTULACION=True)
  real_search.py           combina Computrabajo+Bumeran, dedup, clasifica, on_progreso callback
  exporter.py              genera_excel_bytes() (memoria) + guardar_excel_en_disco() (compat)
  sources/
    computrabajo.py         requests + BeautifulSoup
    bumeran.py              Playwright, snap de días válidos, avisos diferenciados
ui/
  app.py                   TODA la interfaz Streamlit (flujo 4 pasos + tema)
  cv_parser.py              parseo de CV + generación de términos de búsqueda
  theme.css                 paleta CLARA (default) + toda la lógica visual
  theme_dark.css             overrides de paleta OSCURA (solo redefine variables)
.streamlit/config.toml     [theme] nativo Streamlit (negro/blanco) + toolbarMode minimal
requirements.txt           sin playwright todavía (pendiente, ver §11)
```

Módulos **no tocados en ninguna sesión de UI** (lógica de negocio, intacta): `core/classifier.py`, `ui/cv_parser.py`, `core/sources/computrabajo.py`, `core/demo_data.py`.

## 4. Estado actual de las fases

| Fase | Estado |
|---|---|
| Fase 1 — Auditoría | ✅ Cerrada, aprobada |
| Fase 2 — Rediseño funcional (flujo 4 pasos, Excel directo, session state) | ✅ Cerrada, aprobada, probada exhaustivamente |
| Fase 2B — Diseño visual (minimalista, cards, tema claro/oscuro) | ✅ Cerrada funcionalmente, **sin commitear** |
| Fase 3 — Calidad de búsqueda/clasificación (QA/Testing sin términos, Supply Chain sin skills IT, falso positivo CNC) | ⏳ NO empezada, explícitamente pausada |
| Fase 4 — Dependencias (playwright a requirements.txt) | ⏳ NO empezada |
| Fase 5 — Documentación (README, guía de usuario) | ⏳ NO empezada |
| Fase 6 — Launcher único | ⏳ NO empezada (hoy hay 3: `.bat`/`.pyw`/`.vbs`, todos apuntan a `192.168.68.106` hardcodeado — el usuario pidió sacar eso del repo público, todavía sin hacer) |
| Fase 7 — Distribución Windows sin Python visible | ⏳ NO empezada |

## 5. Todo lo implementado hasta este momento

**Fase 2 (funcional):**
- Flujo único en 4 pasos: ① Tu perfil → ② Preferencias → ③ Buscar → ④ Resultados, todo en el centro, sidebar reducida a secundario.
- CV se analiza automáticamente al subir (sin botón "Analizar"), con spinner, usando identidad de archivo (nombre+tamaño) para no reprocesar en cada rerun.
- Perfil auto-precarga Preferencias (categorías, seniority, ubicación, términos) sin click extra; botón manual de re-sync si el usuario edita el perfil después.
- Excel: descarga directa en memoria (`generar_excel_bytes`), un solo botón, sin paso "Exportar" previo ni archivo intermedio obligatorio.
- Feedback de búsqueda real y honesto vía `on_progreso` callback: "Buscando en Computrabajo... → ✓ Computrabajo → Eliminando duplicados... → Analizando compatibilidad... → Aplicando filtros...".
- Recorte de resultados por fuente en ronda-robin (`_recortar_balanceado_por_fuente`) — antes Computrabajo (pagina, más volumen) monopolizaba el `head()` y dejaba a Bumeran en 0 aunque hubiera aportado ofertas válidas.
- Snapshot de criterios de búsqueda (`_criterios_busqueda_actuales`) — si el usuario cambia algo sin volver a apretar "Buscar", aparece aviso "resultados desactualizados" sin borrar nada.
- Modo Demo deshabilitado (`MODO_DEMO_HABILITADO = False` en `ui/app.py`), lógica intacta para reactivar.

**Fase 2B (visual):**
- Paleta blanco/negro/gris, tipografía sistema, sin azul/rojo default de Streamlit.
- `.streamlit/config.toml`: sección `[theme]` (negro/blanco) + `toolbarMode="minimal"`.
- `ui/theme.css`: tokens de color, tipografía, botones, cards (`st.container(border=True)` solo en Perfil/Preferencias, NO en Buscar/Resultados — se sacó esa card por pedido explícito, "no llenar de cajas"), stepper HTML propio (círculos + línea), chips de resultado en pastel.
- Sidebar reorganizada: `Ayuda / Información y privacidad / Configuración avanzada / Código en GitHub`.
- Selector Claro/Oscuro propio arriba del sidebar (`st.session_state["tema"]`, pill `st.radio`), NO depende del menú de Streamlit.
- `ui/theme_dark.css`: paleta oscura sobria (gris casi negro, no negro puro), CTA/pill-seleccionada/paso-completado invertidos (fondo blanco + texto casi negro) vía par de variables `--alg-inverse-bg`/`--alg-inverse-text` (nunca blanco/negro sueltos, para no repetir el bug del CTA en el modo inverso).

## 6. Cambios hechos en ESTA sesión

Solo trabajo de continuidad — **no hubo cambios funcionales nuevos en esta sesión**, únicamente este documento. Los cambios de código descritos en §5/§7/§8 son de la sesión anterior (Fase 2B + fixes), siguen sin commitear.

## 7. Decisiones tomadas y por qué

- **Sin card en "③ Buscar"**: el usuario pidió explícitamente evitar exceso de cajas; una card con un título+botón no agrupa nada, se sacó.
- **Metrics secundarias movidas al expander**: el desglose POSTULAR HOY/REVISAR ANTES/etc. se movió dentro de "Detalle de la búsqueda" para no duplicar dos grids de métricas apiladas (dashboard look que el usuario no quería).
- **Par de variables `--alg-inverse-bg`/`--alg-inverse-text`** en vez de reusar `--alg-black` suelto: evita que invertir la paleta en modo oscuro deje texto blanco-sobre-blanco en el CTA/pills/step-dot (ese patrón exacto fue la causa del bug del botón).
- **Selectores CSS por estructura (`:has()`, roles ARIA, `data-testid`)** en vez de clases `st-emotion-cache-*`: esta versión de Streamlit usa React Aria Components, no BaseWeb — las clases auto-generadas cambian entre builds, los `data-testid`/roles son estables.
- **No se intentó recolorear la tabla de resultados**: `st.dataframe` renderiza en `<canvas>` (Glide Data Grid), es contenido pixel, no DOM/CSS — límite técnico real, se documentó en vez de forzar un hack frágil.
- **No se tocó ningún archivo del server (systemd/Ubuntu/firewall/Samba)** — instrucción explícita del usuario desde el arranque de Fase 2.

## 8. Errores encontrados y cómo se resolvieron

| Error | Causa | Fix |
|---|---|---|
| CSS no se aplicaba, se mostraba como texto plano | Comentarios `/* \n * línea \n */` con `*` al inicio de línea interpretados como lista Markdown antes de llegar al `<style>` | Comentarios reformateados sin asterisco de continuación |
| Header/sidebar quedaban con tema oscuro del SO pese a `base="light"` | Servidor de prueba lanzado con `cwd` incorrecto → nunca leía `.streamlit/config.toml` | Lanzar streamlit siempre con `cwd` = raíz del proyecto |
| Íconos de Streamlit se veían como texto (`"arrow_right"`) | `[class*="st-"] { font-family: ... !important }` pisaba la fuente de íconos | Selector acotado a `.stApp`, sin `!important` ni comodín de clase |
| **CTA "Buscar ofertas" con texto gris/azulado** | `p { color: var(--text-secondary) !important }` (genérico) pisaba el `<p>` interno del label del botón | `.stButton p, .stDownloadButton p { color: inherit !important }` |
| Selectbox/multiselect/dropdown/placeholder blancos en modo oscuro | CSS apuntaba a `[data-baseweb=...]`, que **no existe** en esta versión de Streamlit (usa React Aria) | Selectores por `data-testid="stSelectbox"/"stMultiSelect"`, `:has([role="listbox"])`, `:has(> [data-testid="stMultiSelectTagsContainer"])` |
| Punto nativo del radio visible encima de las pills | Se asumía que el marcador era el primer `div` hijo del label; en realidad es un `span`, y el marcador visual real es un `div` sin `<p>` anidado varios niveles más adentro | `label div:not(:has(p)) { display: none }` (selector estructural, no depende de tags exactos) |
| **`TypeError: ejecutar_busqueda_real() got an unexpected keyword argument 'on_progreso'`** en producción | `app.py`/`buscador_core.py` en disco están sincronizados (confirmado con `grep`) — el proceso systemd tenía `buscador_core` **cacheado en memoria** de antes de que se agregara ese parámetro; Python no relee módulos ya importados sin reiniciar el proceso | Requiere reinicio de `agente-laboral-gen.service` — **no era un bug de código** |

## 9. Limitaciones conocidas

- **Tabla de resultados no tematiza en modo oscuro** (queda clara) — `st.dataframe` es canvas-rendered, no se puede recolorear con CSS. Sigue siendo legible y funcional.
- Multiselect (categorías/seniority) usa el `primaryColor` fijo de `config.toml` para el color de los "tags" — no es dinámico por sesión, queda igual en ambos temas (no reportado como problema, pero es una limitación de la misma naturaleza).
- Fase 3 (clasificación) sigue sin tocar: QA/Testing no genera términos de búsqueda, Supply Chain sin skills IT no genera términos, "Programador CNC" se clasifica como Desarrollo (falso positivo confirmado en pruebas reales).
- `requirements.txt` sigue sin Playwright (Fase 4 pendiente) — hoy se instala manualmente aparte.
- Los 3 launchers (`.bat`/`.pyw`/`.vbs`) siguen con `192.168.68.106` hardcodeado — pendiente de sacar del repo público (Fase 6).

## 10. Pruebas realizadas y resultados

- **CV**: TXT, DOCX, PDF (generado con reportlab, texto real via pypdf) y archivo inválido (.jpg, rechazado por el propio `file_uploader`) — los 4 casos probados end-to-end, perfil detectado correctamente en cada uno.
- **Búsqueda real**: Computrabajo solo, Bumeran solo, ambas fuentes — balance de resultados confirmado (ej. 9 Computrabajo + 13 Bumeran, no monopolio de una fuente).
- **Excel**: verificado con `openpyxl` en cada corrida — 3 hojas (RESUMEN/RESULTADOS/ACCIONES), hyperlinks reales, colores por decisión, `freeze_panes`, autofiltro.
- **Tema claro/oscuro**: recorrido completo (pantalla inicial, CV analizado, Preferencias, búsqueda en progreso, resultados, filtros avanzados abiertos/cerrados) en ambos temas, con CV subido y búsqueda real ejecutada en modo oscuro (9 resultados, funcionó).
- **Ventana angosta (~1135px, tipo notebook)**: layout de 2 columnas se mantiene usable, chips de resultado hacen wrap sin romper.
- Todo probado en un venv de prueba local aparte (Windows, fuera del repo) apuntando al código real en `S:\Proyectos\agente-laboral-gen` — nunca se corrió contra el server de producción directamente (salvo el chequeo HTTP de disponibilidad).

## 11. Estado del modo claro/oscuro

**Implementado y funcionando**, con la única limitación documentada en §9 (tabla). Toggle en `st.session_state["tema"]`, valores `"☀ Claro"` (default) / `"🌙 Oscuro"`. CSS base (`theme.css`) se carga siempre; `theme_dark.css` se inyecta encima solo si `tema == "🌙 Oscuro"`, redefiniendo las mismas variables `--alg-*`.

## 12. Estado de la búsqueda real

Funciona correctamente en el entorno de prueba local (Computrabajo, Bumeran, ambas). **Confirmado también en producción**: tras el reinicio del servicio (§13), el usuario probó una búsqueda real en `andolserver` y devolvió **9 ofertas** correctamente clasificadas.

## 13. Situación del error `on_progreso` y su resolución

Ver tabla en §8, última fila. **Resumen**: no fue un bug de código, fue un proceso systemd con módulo Python cacheado en memoria desde antes del cambio. Se diagnosticó con `grep` (confirmando sincronización app.py/buscador_core.py en disco) — no se tocó ningún archivo para "arreglarlo" porque no había nada que arreglar en el código.

**Confirmado por el usuario**: ejecutó `sudo systemctl restart agente-laboral-gen.service` y probó una búsqueda real en producción después del reinicio — 9 ofertas encontradas, sin `TypeError`. Se confirma que la causa era el proceso/módulo viejo cacheado en memoria, no un error del código actual. No queda nada pendiente de verificar sobre este punto.

## 14. Estado del servidor y servicio systemd

- Server: Ubuntu, `andolserver`, alcanzable en `http://192.168.68.106:8501` (confirmado HTTP 200 al momento de escribir esto).
- Servicio: `agente-laboral-gen.service` (systemd), corre desde `/srv/apps/agente-laboral-gen`.
- **Este entorno de Claude Code NO tiene acceso SSH al server** (puerto 22 inalcanzable) — cualquier comando `systemctl` debe pedirse explícitamente al usuario para que lo corra él.
- Sí hay alcance HTTP al puerto 8501 desde este entorno, para verificación pasiva (no para probar funcionalidad interactiva).

## 15. Comandos importantes

**Reiniciar/verificar el servicio (correrlo el usuario, no Claude):**
```bash
sudo systemctl restart agente-laboral-gen.service
sudo systemctl status agente-laboral-gen.service --no-pager
```

**Levantar localmente para pruebas (Windows, venv aparte, ejemplo):**
```bash
py -3.12 -m venv %TEMP%\agente_test_venv
%TEMP%\agente_test_venv\Scripts\python.exe -m pip install -r "S:\Proyectos\agente-laboral-gen\requirements.txt"
%TEMP%\agente_test_venv\Scripts\python.exe -m pip install "playwright>=1.61"
%TEMP%\agente_test_venv\Scripts\python.exe -m playwright install chromium
%TEMP%\agente_test_venv\Scripts\python.exe -m streamlit run "S:\Proyectos\agente-laboral-gen\ui\app.py"
```
Importante: lanzar SIEMPRE con `cwd` = raíz del proyecto (`cd` antes del comando), si no `.streamlit/config.toml` no se lee y el tema queda roto (ver §8).

## 16. Dependencias relevantes

`requirements.txt` actual: `streamlit, pandas, openpyxl, pypdf, python-docx, requests, beautifulsoup4, truststore`. Playwright **no está** en requirements.txt (se instala aparte, a mano) — agregarlo es Fase 4, todavía no autorizada.

## 17. Archivos modificados actualmente (sin commitear)

```
M  .streamlit/config.toml
M  buscador_core.py
M  core/exporter.py
M  core/real_search.py
M  ui/app.py
?? ui/theme.css
?? ui/theme_dark.css
```
(`docs/continuidad_claude.md`, este archivo, se sumará como `??` también.)

## 18. `git status --short` (verificado al escribir esto)

```
 M .streamlit/config.toml
 M buscador_core.py
 M core/exporter.py
 M core/real_search.py
 M ui/app.py
?? ui/theme.css
?? ui/theme_dark.css
```

## 19. `git diff --stat` (verificado al escribir esto)

```
 .streamlit/config.toml |  21 ++
 buscador_core.py       |  45 ++-
 core/exporter.py       |  39 +-
 core/real_search.py    |  16 +-
 ui/app.py              | 959 +++++++++++++++++++++++++++++--------------------
 5 files changed, 679 insertions(+), 401 deletions(-)
```
(`ui/theme.css` y `ui/theme_dark.css` no aparecen acá por ser untracked — `git diff --stat` nunca muestra archivos nuevos, solo tracked. No están perdidos.)

## 20. Últimos commits relevantes

```
8b29e03 Point launchers at the andolserver Streamlit instance instead of running locally
e439bde Disable Demo mode temporarily, keep real search as only flow
b054636 Fix Bumeran date handling and source diagnostics
3ce9d29 Add graphical Windows launcher
5dd5b75 Add single-click Windows launcher
9ee472f Add optional Bumeran source and Argentina-wide search
df27a71 Deduplicate real search results before filtering
2d6f8bf Improve empty real-search guidance
23c0207 Harden real search filters in UI
14854c9 Add real Computrabajo search from CV profile
```
Todo lo de Fase 2 / Fase 2B (incluidos los 7 archivos de §17) está **sin commitear** todavía — ningún commit nuevo desde `8b29e03`.

## 21. Qué está pendiente

1. Fase 3: QA/Testing sin términos de búsqueda, Supply Chain sin skills IT sin términos, falso positivo "Programador CNC" clasificado como Desarrollo.
2. Fase 4: agregar Playwright a `requirements.txt` con versión mínima, documentar instalación.
3. Fase 5: README + guía de usuario.
4. Fase 6: launcher único, sacar IP hardcodeada del repo público.
5. Fase 7: distribución Windows sin Python visible.

## 22. Próximo paso recomendado

Reinicio del servicio confirmado, búsqueda real en producción confirmada (9 ofertas, sin `TypeError`, §12/§13). Fase 2 + 2B commiteadas (3 commits: funcional backend, UI+tema, este documento — ver §20 para hashes una vez hecho). **Próximo paso: pedir aprobación explícita del usuario para arrancar Fase 3** (QA/Testing, Supply Chain, falso positivo CNC) — no asumir aprobación blanket, cada fase se aprueba una por una.

## 23. Qué NO debe modificar el próximo chat

- `core/classifier.py`, `ui/cv_parser.py`, `core/sources/computrabajo.py`, `core/demo_data.py` — lógica de negocio, no tocada en ninguna sesión de UI, no tocar sin que el usuario lo pida explícitamente (eso es Fase 3).
- Nada de infraestructura del server: systemd, firewall, Samba, Ubuntu — solo el repositorio. Comandos `systemctl` los corre el usuario, nunca Claude directamente (sin acceso SSH de todos modos).
- `core/constants.py`: `DRY_RUN_POSTULACION=True`, `MODO_POSTULACION="OFF"`, `MAX_POSTULACIONES_POR_CORRIDA=0` — no cambiar estos valores de seguridad bajo ninguna circunstancia.
- No hardcodear IPs privadas ni datos personales en el repo público.
- No avanzar a Fase 3 (ni ninguna fase) sin aprobación explícita del usuario en ese chat — cada fase se aprobó una por una en esta sesión, no asumir aprobación blanket.

## 24. Reglas explícitas para el próximo chat

- **No hacer `git commit` ni `git push` sin autorización explícita del usuario en ese chat**, aunque este documento describa cambios ya "terminados" — terminado funcionalmente no es lo mismo que autorizado para commitear.
- **No avanzar de fase sin autorización explícita.**
- Verificar SIEMPRE el estado real (`git status`, `git log`, lectura de archivos) antes de actuar — este documento es un punto de partida, no la fuente de verdad definitiva si el repo cambió después de escribirlo.
