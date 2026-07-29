# Agente Laboral Gen

Interfaz local (Streamlit) que analiza tu CV y busca ofertas de empleo
compatibles, con un motor de clasificación simple y transparente por
reglas/keywords — sin IA externa, sin APIs.

Dos modos, elegibles en pantalla:
- **Demo seguro**: 6 ofertas de ejemplo fijas, sin red, para probar la app.
- **Búsqueda real**: consulta Computrabajo en vivo.

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
  requests + BeautifulSoup, sin navegador. Bumeran e Indeed no están
  conectados todavía — ver "Qué NO hace todavía".
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

- **No se conecta a Bumeran, Indeed, LinkedIn ni otros portales** — solo
  Computrabajo por ahora. Bumeran no está implementado a propósito: 
  requeriría Playwright (un navegador Chromium real, ~300MB de descarga
  extra), lo que haría el proyecto mucho más pesado de instalar. Indeed
  suele bloquear con Cloudflare.
- **No postula.** No existe ninguna capa de envío de postulaciones — ni
  siquiera simulada.
- **No guarda historial** de búsquedas ni de ofertas vistas entre
  corridas.
- No hace OCR: un PDF escaneado (imagen sin texto seleccionable) no se
  puede leer.
- La búsqueda real puede fallar o devolver menos resultados si
  Computrabajo cambia su sitio o bloquea el acceso — es un scraper, no
  una API oficial.

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

**Demo + búsqueda real (solo Computrabajo).** Sin postulación real, sin
historial. Bumeran e Indeed quedan como pendiente.
