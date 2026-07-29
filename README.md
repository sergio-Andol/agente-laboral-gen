# Agente Laboral Gen

Interfaz local (Streamlit) que analiza tu CV y sugiere filtros de búsqueda
de empleo, con un motor de clasificación simple y transparente por
reglas/keywords — sin IA externa, sin APIs, sin conexión a portales reales
todavía.

## Qué hace

- **Sube tu CV** (PDF, DOCX o TXT) y lo analiza en el momento: detecta
  nombre, email, teléfono, ubicación, skills técnicas, herramientas,
  idiomas, experiencia, educación, seniority y categorías de puesto
  sugeridas.
- El perfil detectado es **editable** — podés corregir cualquier campo
  antes de usarlo.
- Un botón **"Usar este perfil para filtros"** vuelca esas sugerencias a
  los filtros de búsqueda (categorías, seniority, ubicación, palabras
  clave).
- Filtros clásicos ajustables a mano: zona, modalidad, categoría,
  seniority, palabras obligatorias/excluidas, cantidad máxima de
  resultados.
- Un motor de clasificación simple (`core/classifier.py`) evalúa cada
  oferta y sugiere **POSTULAR / REVISAR / DESCARTAR** + una acción
  concreta (POSTULAR HOY, REVISAR MANUALMENTE, etc.), con el motivo de la
  decisión siempre visible.
- **Exportación a Excel** con resumen, colores por decisión, links
  clickeables y autofiltro.

## Qué NO hace todavía

- **No busca en portales reales.** Los resultados vienen de un set fijo
  de 6 ofertas de ejemplo (modo DEMO) pensado para mostrar cómo funciona
  el análisis y el filtrado.
- **No se conecta a Bumeran, Computrabajo, LinkedIn ni ningún otro
  portal.**
- **No postula.** No existe ninguna capa de envío de postulaciones — ni
  siquiera simulada.
- **No guarda historial** de búsquedas ni de ofertas vistas entre
  corridas.
- No hace OCR: un PDF escaneado (imagen sin texto seleccionable) no se
  puede leer.

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

**Versión demo.** Sin scraping real, sin postulación real, sin historial.
Pensado como base para conectar fuentes reales de búsqueda más adelante.
