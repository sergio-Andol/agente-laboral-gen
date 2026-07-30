# Agente Laboral Gen

Interfaz local (Streamlit) que analiza tu CV y busca ofertas de empleo
compatibles, con un motor de clasificación simple y transparente por
reglas/keywords — sin IA externa, sin APIs.

Dos modos, elegibles en pantalla:
- **Demo seguro**: 6 ofertas de ejemplo fijas, sin red, para probar la app.
- **Búsqueda real**: consulta Computrabajo en vivo (siempre) y Bumeran (opcional, si tenés Playwright instalado).

## Uso para usuarios no técnicos

No hace falta saber usar la terminal ni PowerShell. Un solo paso:

**Hacé doble click en `Abrir_Agente_Laboral_Gen.bat`.**

Ese archivo hace todo: crea el entorno local, instala lo necesario,
levanta la app y abre el navegador. La primera vez puede tardar un
par de minutos porque crea el entorno e instala las dependencias — las
veces siguientes es mucho más rápido, porque reusa lo que ya instaló.

En el medio te va a preguntar si querés instalar soporte opcional para
Bumeran (además de Computrabajo). Es opcional y puede pedir la
instalación de Chromium (~300MB, tarda unos minutos) — si respondés que
no, la app funciona igual solo con Computrabajo, y podés instalarlo más
adelante volviendo a abrir el mismo archivo.

La app se abre sola en tu navegador en `http://localhost:8501`, como
cualquier página web. Para cerrarla, cerrá esa ventana negra (o presioná
Ctrl+C adentro).

Tu CV se lee **en memoria** y **no se guarda en ningún lado** — se
pierde al cerrar o recargar la página. La app **no postula
automáticamente** en ningún momento: solo busca, clasifica y muestra —
postular lo hacés vos, a mano, en el sitio real, si querés.

## Qué hace

- **Sube tu CV** (PDF, DOCX o TXT) y lo analiza en el momento: detecta
  nombre, email, teléfono, ubicación, skills técnicas, herramientas,
  idiomas, experiencia, educación, seniority y categorías de puesto
  sugeridas.
- El perfil detectado es **editable** — podés corregir cualquier campo
  antes de usarlo.
- Un botón **"Usar este perfil para filtros"** vuelca esas sugerencias a
  los filtros de búsqueda (categorías, seniority, ubicación, palabras
  clave, término de búsqueda para modo real).
- **Búsqueda real en Computrabajo** (`core/sources/computrabajo.py`):
  requests + BeautifulSoup, sin navegador. Activa por defecto.
- **Búsqueda real en Bumeran, opcional** (`core/sources/bumeran.py`):
  usa un navegador real (Playwright + Chromium) porque Bumeran hidrata
  el listado con JavaScript — no hay forma de leerlo solo con
  requests/BeautifulSoup como Computrabajo. Se activa con un checkbox
  aparte en la sidebar (desactivado por defecto). Si Playwright no está
  instalado, la app no se rompe: muestra un aviso y sigue con las demás
  fuentes activas. Indeed no está conectado todavía (bloquea con
  Cloudflare) — ver "Qué NO hace todavía".
- Filtros clásicos ajustables a mano: zona, modalidad, categoría,
  seniority, palabras obligatorias/excluidas, días de publicación,
  cantidad máxima de resultados.
- Un motor de clasificación simple (`core/classifier.py`) evalúa cada
  oferta y sugiere **POSTULAR / REVISAR / DESCARTAR** + una acción
  concreta (POSTULAR HOY, REVISAR MANUALMENTE, etc.), con el motivo de la
  decisión siempre visible. En búsqueda real clasifica solo con el
  título (Computrabajo no expone la descripción completa en el listado),
  así que la mayoría de los resultados reales caen en REVISAR más que en
  POSTULAR — es esperado, no un bug.
- **Exportación a Excel** con resumen, colores por decisión, links
  clickeables y autofiltro.

## Qué NO hace todavía

- **No se conecta a Indeed ni LinkedIn** — Indeed suele bloquear con
  Cloudflare, no está implementado.
- **Bumeran no verifica si la postulación es externa** (a otro portal
  tipo ZonaJobs) — el scraper del proyecto personal en el que se basó
  esto sí lo hace, pero exige abrir el detalle de cada aviso (mucho más
  lento). Se dejó afuera a propósito para una fuente opcional.
- **No postula.** No existe ninguna capa de envío de postulaciones — ni
  siquiera simulada.
- **No guarda historial** de búsquedas ni de ofertas vistas entre
  corridas.
- No hace OCR: un PDF escaneado (imagen sin texto seleccionable) no se
  puede leer.
- La búsqueda real puede fallar o devolver menos resultados si los
  sitios cambian su markup o bloquean el acceso — son scrapers, no APIs
  oficiales.

## Instalación

Requiere Python 3.11+ (probado con 3.14).

```bash
pip install -r requirements.txt
```

Dependencias y por qué están:

| Paquete | Para qué |
|---|---|
| `streamlit` | la interfaz web local |
| `pandas` | tabla de resultados y filtros |
| `openpyxl` | exportar a Excel con formato |
| `pypdf` | leer texto de CVs en PDF |
| `python-docx` | leer texto de CVs en DOCX |
| `requests` | pedidos HTTP a Computrabajo (búsqueda real) |
| `beautifulsoup4` | parsear el HTML de resultados de Computrabajo |
| `truststore` | usa el almacén de certificados del sistema operativo — evita errores SSL en máquinas con antivirus que inspecciona HTTPS (Norton, etc.) |

### Bumeran (opcional)

Computrabajo funciona sin nada más. Si además querés usar Bumeran como
fuente, instalá Playwright y su navegador Chromium (esto no está en
`requirements.txt` a propósito — agrega ~300MB de descarga, y no todos
los que prueben la app van a querer eso):

```bash
pip install playwright
py -3.14 -m playwright install chromium
```

Si Bumeran está tildado en la sidebar pero Playwright no está instalado,
la app **no se rompe**: muestra un aviso, y sigue mostrando resultados de
las demás fuentes activas.

## Cómo ejecutar

```bash
py -3.14 -m streamlit run ui/app.py
```

(o `streamlit run ui/app.py` si `streamlit` ya está en el PATH de tu
entorno).

## Privacidad

El CV se procesa **completamente en memoria** y **no se guarda en disco
por defecto** — se lee, se analiza, y se descarta al cerrar o recargar la
sesión. El análisis es 100% local (reglas/keywords en `ui/cv_parser.py`):
no se envía a ninguna API externa ni servicio de IA.

## Estado

**Demo + búsqueda real (Computrabajo + Bumeran opcional).** Sin
postulación real, sin historial. Indeed queda como pendiente.
