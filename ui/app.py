"""
Interfaz visual local (Streamlit) para Agente Laboral Gen.

Version demo, generica (sin datos de ningun usuario particular): no hace
scraping real, no tiene historial, no postula nada. Los datos que se
muestran salen de core.demo_data.generar_datos_demo() via
buscador_core.generar_resultados_demo(). El CV se lee en memoria (nunca
se guarda en disco) y se analiza 100% local por reglas/keywords, sin IA
ni APIs externas -- ver ui/cv_parser.py.

Correr con:
    streamlit run ui/app.py
"""
import os
import sys
from pathlib import Path

import streamlit as st

# Import robusto sin importar desde donde se invoque `streamlit run`:
# agrega la raiz del proyecto a sys.path y fija el cwd ahi, porque
# core.exporter escribe en "resultados/" (ruta relativa a la raiz).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

import buscador_core as core  # noqa: E402  (import despues del sys.path fix, a proposito)
import cv_parser  # noqa: E402  (ui/cv_parser.py, mismo directorio que este archivo)

st.set_page_config(page_title="Agente Laboral Gen", layout="wide")

OPCIONES_ZONA = ["Cualquiera", "CABA", "GBA", "Buenos Aires"]
OPCIONES_SENIORITY = ["Junior", "Trainee", "Semi Senior"]


def _aplicar_perfil_a_filtros():
    """Callback del boton "Usar este perfil para filtros". Streamlit
    ejecuta los on_click ANTES de rerenderizar el script, asi que fijar
    st.session_state aca (con las mismas keys que los widgets de la
    sidebar) los deja pre-cargados en el rerun que sigue -- no importa el
    orden en que aparezcan CV/sidebar en el archivo."""
    perfil = st.session_state.get("perfil_cv")
    if not perfil:
        return

    # Se usan los valores EDITADOS (widgets *_edit), no el dict crudo del
    # parser -- el usuario pudo haber corregido algo en pantalla antes de
    # apretar este boton.
    categorias_edit = st.session_state.get("perfil_categorias_edit", perfil["categorias_sugeridas"])
    st.session_state["filtro_categorias"] = [
        c for c in categorias_edit if c in core.categorias_disponibles()
    ]

    seniority_edit = st.session_state.get("perfil_seniority_objetivo_edit", perfil["seniority_objetivo"])
    st.session_state["filtro_seniority"] = [s for s in seniority_edit if s in OPCIONES_SENIORITY]

    # La palabra obligatoria sugerida es siempre suave: solo se carga si
    # el usuario tildo el checkbox de confirmacion. Sin eso, no se toca
    # filtro_palabras_obligatorias (para no pisar algo que haya escrito a
    # mano en la sidebar).
    if st.session_state.get("perfil_aplicar_obligatoria_edit"):
        palabras_incluir_texto = st.session_state.get(
            "perfil_palabras_incluir_edit", ", ".join(perfil["palabras_clave_incluir"])
        )
        st.session_state["filtro_palabras_obligatorias"] = palabras_incluir_texto

    palabras_excluir_texto = st.session_state.get(
        "perfil_palabras_excluir_edit", ", ".join(perfil["palabras_clave_excluir"])
    )
    st.session_state["filtro_palabras_excluidas"] = palabras_excluir_texto

    ubicacion = st.session_state.get("perfil_ubicacion_edit", perfil["ubicacion"])
    zona_match = next((o for o in OPCIONES_ZONA if o.lower() in (ubicacion or "").lower()), "Cualquiera")
    st.session_state["filtro_zona"] = zona_match
    st.session_state["perfil_aplicado"] = True

    # Los resultados en pantalla son de la busqueda ANTERIOR -- si se
    # dejan, el usuario ve ofertas que ya no deberian pasar los filtros
    # nuevos hasta que aprete "Buscar ofertas demo" de nuevo. Se limpian
    # aca para no mostrar datos viejos con filtros nuevos puestos.
    st.session_state.pop("resultados_demo", None)


st.title("Agente Laboral Gen")
st.subheader("Analizá tu CV, ajustá filtros y explorá ofertas compatibles.")

# --- resumen de seguridad: valores REALES leidos del script, no hardcoded --
seguridad = core.resumen_seguridad()
with st.container(border=True):
    st.markdown("**Estado de seguridad de postulación**")
    c1, c2, c3 = st.columns(3)
    c1.metric("DRY_RUN_POSTULACION", str(seguridad["dry_run_postulacion"]))
    c2.metric("MODO_POSTULACION", seguridad["modo_postulacion"])
    c3.metric("Postulación real desde UI", "Desactivada")
    if not seguridad["dry_run_postulacion"]:
        st.error(
            "DRY_RUN_POSTULACION está en False en core/constants.py. "
            "Esta UI no envía postulaciones igual, pero avisá antes de seguir."
        )
    st.caption(
        f"MODO_POSTULACION={seguridad['modo_postulacion']} · "
        "esta pantalla solo busca y muestra resultados simulados, nunca postula."
    )

st.info(
    "**Versión demo segura: no postula, no guarda tu CV y no se conecta a portales reales.**\n\n"
    "- Estos resultados son **simulados** (6 ofertas de ejemplo), no ofertas reales.\n"
    "- **No** se conecta a ningún portal de empleo (Bumeran, Computrabajo, LinkedIn, etc.).\n"
    "- **No** guarda ningún historial ni archivo de postulaciones.\n"
    "- **No** postula ni envía nada — la postulación real no está implementada."
)

# --- subir CV ------------------------------------------------------------
st.header("Subir CV")
st.caption(
    "El CV se lee en memoria y no se guarda en disco. Análisis 100% local "
    "por reglas/keywords — sin IA externa ni APIs. Formatos: PDF, DOCX, TXT."
)
cv_file = st.file_uploader("Subí tu CV", type=["pdf", "docx", "txt"])

if cv_file is not None and st.button("Analizar CV"):
    try:
        texto_cv = cv_parser.leer_texto_cv(cv_file)
        if not texto_cv.strip():
            st.warning(
                "No se pudo extraer texto de este archivo (¿PDF escaneado/imagen, "
                "sin capa de texto? no se hace OCR todavía). Probá con un PDF con "
                "texto seleccionable, o subí un DOCX/TXT."
            )
        else:
            st.session_state["perfil_cv"] = cv_parser.analizar_cv(texto_cv)
            st.session_state.pop("perfil_aplicado", None)
    except ValueError as e:
        st.error(str(e))

if "perfil_cv" in st.session_state and "seniority_detectada" not in st.session_state["perfil_cv"]:
    # Perfil de una version anterior del parser, quedo en memoria de la
    # sesion de Streamlit (el hot-reload no limpia session_state solo).
    # Se descarta en vez de romper con KeyError -- pide reanalizar.
    st.session_state.pop("perfil_cv", None)
    st.info("El análisis del CV cambió desde la última carga. Volvé a subir/analizar el CV.")

if "perfil_cv" in st.session_state:
    perfil = st.session_state["perfil_cv"]
    st.subheader("Perfil detectado (editable)")
    st.warning("El perfil detectado es una sugerencia. Revisalo y ajustalo antes de buscar.")

    col_izq, col_der = st.columns(2)
    with col_izq:
        st.text_input("Nombre detectado", value=perfil["nombre"], key="perfil_nombre_edit")
        st.text_input("Email detectado", value=perfil["email"], key="perfil_email_edit")
        st.text_input("Teléfono detectado", value=perfil["telefono"], key="perfil_telefono_edit")
        st.text_input("Ubicación detectada", value=perfil["ubicacion"], key="perfil_ubicacion_edit")
        st.text_input(
            "Seniority detectada en el CV", value=perfil["seniority_detectada"],
            key="perfil_seniority_detectada_edit", disabled=True,
            help="Informativa, no se usa para filtrar. El nivel que se busca es el de abajo.",
        )
        st.multiselect(
            "Seniority objetivo para la búsqueda", OPCIONES_SENIORITY,
            default=perfil["seniority_objetivo"], key="perfil_seniority_objetivo_edit",
            help="Esta herramienta solo busca roles Junior/Trainee/Semi Senior a propósito.",
        )
    with col_der:
        st.multiselect(
            "Categorías sugeridas", core.categorias_disponibles(),
            default=perfil["categorias_sugeridas"], key="perfil_categorias_edit",
        )
        st.text_input("Skills detectadas", value=", ".join(perfil["skills"]), key="perfil_skills_edit")
        st.text_input("Herramientas detectadas", value=", ".join(perfil["herramientas"]), key="perfil_herramientas_edit")
        st.text_input("Idiomas detectados", value=", ".join(perfil["idiomas"]), key="perfil_idiomas_edit")

    st.write(
        "**Puestos objetivo sugeridos:** "
        + (", ".join(perfil["puestos_objetivo"]) if perfil["puestos_objetivo"] else "— (no se detectó categoría clara)")
    )

    exp_col, edu_col = st.columns(2)
    with exp_col:
        with st.expander("Experiencia detectada (texto crudo)"):
            st.text(perfil["experiencia"] or "No se detectó una sección de experiencia clara.")
    with edu_col:
        with st.expander("Educación detectada (texto crudo)"):
            st.text(perfil["educacion"] or "No se detectó una sección de educación clara.")

    st.text_input(
        "Palabras obligatorias sugeridas (opcional)", value=", ".join(perfil["palabras_clave_incluir"]),
        key="perfil_palabras_incluir_edit",
        help="A propósito 1 sola palabra: el filtro de la sidebar exige que TODAS estén en el título.",
    )
    st.checkbox(
        "Aplicar esta palabra obligatoria al filtro (si no, se deja el filtro como está)",
        value=False, key="perfil_aplicar_obligatoria_edit",
        help="Por defecto NO se carga: en perfiles mixtos una sola palabra obligatoria puede dejar afuera ofertas buenas.",
    )
    st.text_input(
        "Palabras excluidas sugeridas", value=", ".join(perfil["palabras_clave_excluir"]),
        key="perfil_palabras_excluir_edit",
    )

    st.button("Usar este perfil para filtros", on_click=_aplicar_perfil_a_filtros)
    if st.session_state.get("perfil_aplicado"):
        st.success("Filtros actualizados. Volvé a ejecutar la búsqueda demo.")

# --- sidebar: filtros -------------------------------------------------------
st.sidebar.header("Fuentes")
st.sidebar.caption(
    "Todavía no hay conexión a portales reales — esta versión solo trabaja "
    "con las 6 ofertas de ejemplo del modo DEMO."
)

st.sidebar.header("Filtros")
zona = st.sidebar.selectbox("Zona", OPCIONES_ZONA, key="filtro_zona")
modalidad = st.sidebar.selectbox("Modalidad", ["Cualquiera", "Remoto", "Híbrido", "Presencial"])
dias_publicacion = st.sidebar.slider("Días máximos de publicación", 1, 15, 2)
categorias = st.sidebar.multiselect(
    "Categorías", core.categorias_disponibles(), placeholder="Elegir opciones", key="filtro_categorias",
)
seniority = st.sidebar.multiselect(
    "Seniority", OPCIONES_SENIORITY, placeholder="Elegir opciones", key="filtro_seniority",
)
palabras_obligatorias = st.sidebar.text_input(
    "Palabras obligatorias (separadas por coma)", key="filtro_palabras_obligatorias",
)
palabras_excluidas = st.sidebar.text_input(
    "Palabras excluidas (separadas por coma)", key="filtro_palabras_excluidas",
)
max_resultados = st.sidebar.slider("Máximo de resultados", 1, 10, 10)

st.sidebar.caption(
    "Todos estos filtros son funcionales sobre las 6 ofertas simuladas: "
    "palabras obligatorias/excluidas, zona, modalidad, categorías, "
    "seniority y máximo de resultados."
)

buscar = st.sidebar.button("Buscar ofertas demo", type="primary")

if buscar:
    st.session_state.pop("perfil_aplicado", None)
    filtros = {
        "palabras_obligatorias": [p for p in palabras_obligatorias.split(",")],
        "palabras_excluidas": [p for p in palabras_excluidas.split(",")],
        "zona": zona,
        "modalidad": modalidad,
        "categorias": categorias,
        "seniority": seniority,
        "max_resultados": max_resultados,
    }
    nuevas, acciones_df, datos_resumen = core.generar_resultados_demo(filtros)
    st.session_state["resultados_demo"] = (nuevas, acciones_df, datos_resumen)

# --- resultados --------------------------------------------------------
if "resultados_demo" in st.session_state:
    nuevas, acciones_df, datos_resumen = st.session_state["resultados_demo"]

    st.subheader("Resumen")
    m1, m2, m3 = st.columns(3)
    m1.metric("POSTULAR", datos_resumen["postular"])
    m2.metric("REVISAR", datos_resumen["revisar"])
    m3.metric("DESCARTAR", datos_resumen["descartar"])

    conteo_acciones = datos_resumen["conteo_acciones"]
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("POSTULAR HOY", conteo_acciones.get("POSTULAR HOY", 0))
    a2.metric("REVISAR ANTES DE POSTULAR", conteo_acciones.get("REVISAR ANTES DE POSTULAR", 0))
    a3.metric("REVISAR MANUALMENTE", conteo_acciones.get("REVISAR MANUALMENTE", 0))
    a4.metric("NO ACCIONAR", conteo_acciones.get("NO ACCIONAR", 0))

    st.subheader(f"Resultados ({len(nuevas)})")
    columnas_mostrar = [
        "titulo", "empresa", "fuente", "ubicacion", "modalidad", "fecha",
        "categoria_detectada", "decision_sugerida", "motivo_decision",
        "accion_sugerida", "link",
    ]
    if nuevas.empty:
        st.warning("Ningún resultado DEMO pasa los filtros actuales. Probá aflojar zona/modalidad/palabras/seniority.")
    else:
        st.dataframe(
            nuevas[columnas_mostrar],
            width="stretch",
            hide_index=True,
            column_config={
                "link": st.column_config.LinkColumn("link", display_text="Abrir oferta"),
            },
        )

    st.subheader("Exportar")
    if st.button("Exportar a Excel"):
        archivo = core.exportar_excel(nuevas, acciones_df, datos_resumen)
        st.success(f"Excel generado: {archivo}")
        with open(archivo, "rb") as f:
            st.download_button(
                "Descargar Excel",
                data=f.read(),
                file_name=Path(archivo).name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
else:
    st.caption("Elegí filtros en la barra lateral y apretá \"Buscar ofertas demo\".")
