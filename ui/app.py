"""
Interfaz visual local (Streamlit) para Agente Laboral Gen.

Flujo guiado en 4 pasos, todos en el area central (la sidebar queda para
lo secundario: ayuda, info tecnica, link al repo):

    1 TU PERFIL      -> subir CV, analisis automatico, perfil editable
    2 PREFERENCIAS   -> categorias, seniority, zona, fuentes, terminos
                        (filtros avanzados colapsados aparte)
    3 BUSCAR         -> boton principal, feedback real durante la busqueda
    4 RESULTADOS     -> resumen, filtros rapidos, tabla, descarga Excel
                        directa (sin paso "Exportar" previo)

No es un wizard rigido: los 4 bloques se renderizan siempre, de arriba
hacia abajo, editables en cualquier momento -- el usuario puede volver a
tocar el perfil o las preferencias cuando quiera, sin "retroceder".

Modo Demo (datos simulados fijos, sin red) esta deshabilitado por
defecto (MODO_DEMO_HABILITADO=False, mas abajo) -- si se reactiva, usa
una UI minima propia en vez del flujo de 4 pasos, que no tiene sentido
sin CV real (queda intacto, no se borro nada de la logica demo).

Ningun modo postula, guarda historial ni guarda el CV en disco. El CV se
lee en memoria y se analiza 100% local por reglas/keywords, sin IA ni
APIs externas -- ver ui/cv_parser.py.

Correr con:
    streamlit run ui/app.py
"""
import os
import sys
from pathlib import Path

import streamlit as st

# Import robusto sin importar desde donde se invoque `streamlit run`:
# agrega la raiz del proyecto a sys.path y fija el cwd ahi, porque
# core.exporter (si se usa guardar_excel_en_disco) escribe en
# "resultados/" (ruta relativa a la raiz).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

import buscador_core as core  # noqa: E402  (import despues del sys.path fix, a proposito)
import cv_parser  # noqa: E402  (ui/cv_parser.py, mismo directorio que este archivo)
from core import constants  # noqa: E402

st.set_page_config(page_title="Agente Laboral Gen", layout="wide")

# Tema visual (Fase 2B, solo presentacion) -- tokens/tipografia/botones/
# cards en un CSS aparte para no ensuciar este archivo con estilos
# inline. El [theme] de .streamlit/config.toml ya recolorea los widgets
# nativos (checkbox/radio/slider/multiselect); esto cubre el resto.
#
# Claro/Oscuro: selector PROPIO (no el menu interno de Streamlit), mas
# abajo en el sidebar -- se lee aca ANTES de que ese widget se
# renderice porque st.session_state ya trae el valor de la corrida
# anterior (o el default la primera vez). ui/theme_dark.css solo
# redefine las mismas variables --alg-*; se inyecta DESPUES de
# theme.css para que gane por orden de cascada, sin duplicar reglas.
_CSS_DIR = Path(__file__).resolve().parent
_TEMA_ACTUAL = st.session_state.get("tema", "☀ Claro")
st.markdown(f"<style>{(_CSS_DIR / 'theme.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
if _TEMA_ACTUAL == "🌙 Oscuro":
    st.markdown(f"<style>{(_CSS_DIR / 'theme_dark.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

# "Toda Argentina" primera a proposito: es el default (index 0 de un
# selectbox sin key todavia en session_state). Mismo listado que usa
# buscador_core para armar la URL de Computrabajo -- ver core/constants.py.
OPCIONES_ZONA = constants.OPCIONES_ZONA
OPCIONES_SENIORITY = ["Junior", "Trainee", "Semi Senior"]
REPO_URL = "https://github.com/sergio-Andol/agente-laboral-gen"


# ---------------------------------------------------------------------
# Helpers de estado / callbacks
# ---------------------------------------------------------------------

def _precargar_filtros_desde_perfil():
    """Vuelca el perfil detectado (o editado) a los widgets de
    Preferencias. Se llama automaticamente apenas se analiza un CV
    nuevo, y tambien queda disponible como boton manual para cuando el
    usuario edita el perfil despues y quiere re-sincronizar. Usa los
    valores EDITADOS (widgets *_edit) si ya existen, si no cae al dict
    crudo del parser -- no importa el orden en que se rendericen los
    bloques."""
    perfil = st.session_state.get("perfil_cv")
    if not perfil:
        return

    categorias_edit = st.session_state.get("perfil_categorias_edit", perfil["categorias_sugeridas"])
    st.session_state["filtro_categorias"] = [
        c for c in categorias_edit if c in core.categorias_disponibles()
    ]

    seniority_edit = st.session_state.get("perfil_seniority_objetivo_edit", perfil["seniority_objetivo"])
    st.session_state["filtro_seniority"] = [s for s in seniority_edit if s in OPCIONES_SENIORITY]

    # La palabra obligatoria sugerida es siempre suave: solo se carga si
    # el usuario tildo el checkbox de confirmacion. Sin eso, no se toca
    # filtro_palabras_obligatorias (para no pisar algo que haya escrito
    # a mano).
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
    zona_match = next((o for o in OPCIONES_ZONA if o.lower() in (ubicacion or "").lower()), "Toda Argentina")
    st.session_state["filtro_zona"] = zona_match

    busquedas_sugeridas_texto = st.session_state.get(
        "perfil_busquedas_edit", ", ".join(cv_parser.generar_busquedas_desde_perfil(perfil))
    )
    st.session_state["terminos_busqueda"] = busquedas_sugeridas_texto

    st.session_state["perfil_aplicado"] = True
    # Resultados de una busqueda anterior ya no corresponden a este
    # perfil/estos filtros -- se descartan para no mostrar ofertas
    # viejas con criterios nuevos hasta la proxima busqueda.
    st.session_state.pop("resultados_busqueda", None)


def _criterios_busqueda_actuales():
    """Snapshot de los criterios que determinan el resultado de una
    busqueda real (leidos directo de session_state por key, no de
    variables locales -- esta funcion se llama desde _renderizar_
    resultados(), fuera del scope donde se definen los widgets).
    Se usa para detectar si el usuario cambio algo desde la ultima vez
    que apreto "Buscar ofertas", y avisarlo en vez de mostrar resultados
    viejos como si fueran de los criterios actuales."""
    return {
        "terminos_busqueda": st.session_state.get("terminos_busqueda", ""),
        "dias_publicacion": st.session_state.get("dias_publicacion"),
        "max_resultados": st.session_state.get("max_resultados"),
        "filtro_zona": st.session_state.get("filtro_zona"),
        "filtro_modalidad": st.session_state.get("filtro_modalidad"),
        "filtro_categorias": tuple(st.session_state.get("filtro_categorias") or []),
        "filtro_seniority": tuple(st.session_state.get("filtro_seniority") or []),
        "filtro_palabras_obligatorias": st.session_state.get("filtro_palabras_obligatorias", ""),
        "filtro_palabras_excluidas": st.session_state.get("filtro_palabras_excluidas", ""),
        "usar_computrabajo": st.session_state.get("usar_computrabajo"),
        "usar_bumeran": st.session_state.get("usar_bumeran"),
    }


def _renderizar_pasos(paso_actual):
    """Indicador visual de en que paso del flujo esta el usuario --
    barra discreta (circulos + linea), no un wizard: los 4 bloques
    igual se renderizan siempre debajo, esto es solo orientacion (puede
    ir 1 render detras de la ultima accion, ej. justo al analizar un CV
    -- se corrige solo en la proxima interaccion, no afecta la logica)."""
    etiquetas = ["Perfil", "Preferencias", "Buscar", "Resultados"]
    partes = ['<div class="alg-stepper">']
    for i, etiqueta in enumerate(etiquetas, start=1):
        estado = "done" if i < paso_actual else ("activo" if i == paso_actual else "")
        marca = "✓" if i < paso_actual else str(i)
        partes.append(
            f'<div class="alg-step {estado}"><span class="alg-step-dot">{marca}</span>'
            f'<span>{etiqueta}</span></div>'
        )
        if i < len(etiquetas):
            partes.append('<div class="alg-step-line"></div>')
    partes.append("</div>")
    st.markdown("".join(partes), unsafe_allow_html=True)


def _renderizar_resultados():
    """Paso ④. Se llama siempre al final del script (real o demo) --
    lee de session_state['resultados_busqueda'], no recibe nada por
    parametro, para no duplicar esta seccion en cada rama de modo."""
    st.markdown('<div class="alg-section-title alg-section-title-spaced">④ Resultados</div>', unsafe_allow_html=True)
    resultado = st.session_state.get("resultados_busqueda")
    if not resultado:
        st.caption("Todavía no buscaste. Completá tus preferencias arriba y apretá el botón de buscar.")
        return

    nuevas, acciones_df, datos_resumen, excel_bytes, excel_nombre, criterios_snapshot = resultado
    texto_cantidad = "1 oportunidad encontrada" if len(nuevas) == 1 else f"{len(nuevas)} oportunidades encontradas"

    if (
        datos_resumen.get("modo") == "real"
        and criterios_snapshot is not None
        and criterios_snapshot != _criterios_busqueda_actuales()
    ):
        st.info(
            "Cambiaste algún criterio desde esta búsqueda -- lo de abajo son los "
            "resultados de la búsqueda anterior. Volvé a apretar \"🔎 Buscar ofertas\" "
            "para actualizarlos."
        )

    st.markdown(f'<div class="alg-section-sub">{texto_cantidad}</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="alg-metric-row">
          <div class="alg-metric alg-metric-green">
            <div class="alg-metric-num">{datos_resumen["postular"]}</div>
            <div class="alg-metric-label">POSTULAR</div>
          </div>
          <div class="alg-metric alg-metric-amber">
            <div class="alg-metric-num">{datos_resumen["revisar"]}</div>
            <div class="alg-metric-label">REVISAR</div>
          </div>
          <div class="alg-metric alg-metric-rose">
            <div class="alg-metric-num">{datos_resumen["descartar"]}</div>
            <div class="alg-metric-label">DESCARTAR</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if datos_resumen.get("modo") == "real":
        with st.expander("Detalle de la búsqueda"):
            conteo_acciones = datos_resumen["conteo_acciones"]
            st.caption(
                "Acciones sugeridas — "
                f"POSTULAR HOY: {conteo_acciones.get('POSTULAR HOY', 0)} · "
                f"REVISAR ANTES DE POSTULAR: {conteo_acciones.get('REVISAR ANTES DE POSTULAR', 0)} · "
                f"REVISAR MANUALMENTE: {conteo_acciones.get('REVISAR MANUALMENTE', 0)} · "
                f"NO ACCIONAR: {conteo_acciones.get('NO ACCIONAR', 0)}"
            )
            st.caption(f"Alcance geográfico: {datos_resumen.get('alcance_geografico', 'Toda Argentina')}")
            conteo_por_fuente = datos_resumen.get("conteo_por_fuente") or {}
            conteo_por_fuente_final = datos_resumen.get("conteo_por_fuente_final") or {}
            fuentes_solicitadas = datos_resumen.get("fuentes_solicitadas") or []
            if conteo_por_fuente:
                desglose = ", ".join(f"{fuente}: {cant}" for fuente, cant in conteo_por_fuente.items())
                st.caption(f"Fuentes reales consultadas — {desglose}. Indeed todavía no está conectado.")
            else:
                st.caption("Ninguna fuente devolvió resultados. Computrabajo activo por defecto, Bumeran opcional (si lo tildaste). Indeed no conectado todavía.")
            if conteo_por_fuente:
                desglose_final = ", ".join(
                    f"{fuente}: {conteo_por_fuente_final.get(fuente, 0)}" for fuente in conteo_por_fuente
                )
                st.caption(f"En el resultado final (tras filtros) — {desglose_final}.")

            # 3 situaciones bien distintas de Bumeran (no confundir "0
            # resultados reales" con "el sitio bloqueó/cambió de
            # estructura" -- cada aviso ya trae su propio texto
            # diferenciado, ver core/sources/bumeran.py):
            #   a) Playwright/Chromium no disponible (BumeranNoDisponible)
            #   b) respondió pero no se pudo leer / estructura distinta
            #   c) bloqueo (captcha/verificación) detectado
            avisos_fuentes = datos_resumen.get("avisos_fuentes") or []
            if avisos_fuentes:
                st.warning("Bumeran tuvo un problema en esta búsqueda. Se muestran resultados de las demás fuentes.")
                for aviso in avisos_fuentes:
                    st.caption(f"⚠️ {aviso}")
            elif "Bumeran" in fuentes_solicitadas and conteo_por_fuente.get("Bumeran", 0) == 0:
                st.info("Bumeran no devolvió resultados con estos filtros.")
            elif "Bumeran" in fuentes_solicitadas and conteo_por_fuente.get("Bumeran", 0) > 0 and conteo_por_fuente_final.get("Bumeran", 0) == 0:
                st.info(
                    f"Bumeran crudas: {conteo_por_fuente['Bumeran']}, tras filtros: 0 — "
                    "los filtros de Preferencias (categoría, seniority, palabras, zona) descartaron todas sus ofertas."
                )

            st.caption(
                f"Ofertas encontradas: {datos_resumen.get('cant_crudo', 0)} crudas → "
                f"{datos_resumen.get('cant_tras_dedupe', 0)} únicas (sin duplicados) → "
                f"{datos_resumen.get('cant_tras_filtros', 0)} tras aplicar filtros."
            )
            terminos_usados = datos_resumen.get("terminos_usados") or []
            if terminos_usados:
                etiquetas_origen = {"cv": "sugeridas desde el CV", "campo": "editadas por el usuario"}
                etiqueta_origen = etiquetas_origen.get(datos_resumen.get("origen_terminos"))
                titulo_busquedas = f"Búsquedas usadas ({etiqueta_origen})" if etiqueta_origen else "Búsquedas usadas"
                st.caption(f"{titulo_busquedas}: {', '.join(terminos_usados)}")

    st.subheader(f"Resultados ({len(nuevas)})")
    if nuevas.empty:
        if datos_resumen.get("modo") == "real":
            obligatorias_activas = datos_resumen.get("palabras_obligatorias_usadas") or []
            if obligatorias_activas:
                st.warning(
                    "No se encontraron ofertas. El filtro de palabras obligatorias "
                    "puede estar limitando demasiado la búsqueda. Probá borrar: "
                    f"{', '.join(obligatorias_activas)}"
                )
            elif datos_resumen.get("filtros_categoria_seniority_activos"):
                st.warning(
                    "No se encontraron ofertas después de aplicar filtros. Probá "
                    "ampliar días, aumentar máximo de resultados o relajar "
                    "seniority/categorías."
                )
            else:
                st.warning(
                    "No se encontraron ofertas. Probá:\n"
                    "- Ampliar los días a 30\n"
                    "- Usar términos más cortos\n"
                    "- Buscar una categoría por vez"
                )
        else:
            st.warning("Ningún resultado pasa los filtros actuales. Probá aflojar zona/modalidad/palabras/seniority.")
    else:
        opciones_vista = ["Todas", "Postular", "Revisar", "Descartar"]
        vista = st.radio(
            "Filtrar por decisión", opciones_vista, horizontal=True,
            key="filtro_vista_resultados", label_visibility="collapsed",
        )
        mapa_decision = {"Postular": "POSTULAR", "Revisar": "REVISAR", "Descartar": "DESCARTAR"}
        vista_df = nuevas if vista == "Todas" else nuevas[nuevas["decision_sugerida"] == mapa_decision[vista]]

        columnas_mostrar = [
            "titulo", "empresa", "fuente", "ubicacion", "modalidad", "fecha",
            "categoria_detectada", "decision_sugerida", "motivo_decision",
            "accion_sugerida", "link",
        ]
        st.dataframe(
            vista_df[columnas_mostrar],
            width="stretch",
            hide_index=True,
            column_config={
                "link": st.column_config.LinkColumn("link", display_text="Abrir oferta"),
            },
        )

    # Descarga directa: los bytes ya se generaron cuando se corrió la
    # busqueda (ver mas abajo) -- un solo click, sin paso "Exportar"
    # previo ni archivo intermedio en resultados/.
    st.download_button(
        "⬇ Descargar resultados en Excel",
        data=excel_bytes,
        file_name=excel_nombre,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )


# ---------------------------------------------------------------------
# Sidebar: solo lo secundario -- el flujo principal va en el centro
# ---------------------------------------------------------------------

with st.sidebar:
    # Selector de apariencia propio -- no depende del menu interno de
    # Streamlit. key="tema" persiste la eleccion en st.session_state;
    # el CSS correspondiente ya se cargo mas arriba, ANTES de este
    # widget (leyendo el mismo session_state con .get()).
    st.radio(
        "Apariencia", ["☀ Claro", "🌙 Oscuro"], key="tema",
        horizontal=True, label_visibility="collapsed",
    )

    st.markdown("### Agente Laboral Gen")

    with st.expander("Ayuda"):
        st.caption(
            "Subís tu CV, revisás el perfil que se detecta, elegís qué "
            "buscás y la app consulta portales reales para mostrarte "
            "ofertas compatibles ya clasificadas. No postula por vos."
        )

    with st.expander("Información y privacidad"):
        st.caption(
            "Tu CV se lee en memoria y se analiza 100% local (reglas/"
            "keywords) -- nunca se guarda en disco ni se envía a ninguna "
            "API externa."
        )
        st.caption(
            "Esta app no tiene ninguna capa de postulación real: solo "
            "busca, clasifica y muestra. Postular lo hacés vos, a mano, "
            "en el sitio real."
        )

    _seguridad = core.resumen_seguridad()
    with st.expander("Configuración avanzada"):
        st.caption(
            f"DRY_RUN_POSTULACION={_seguridad['dry_run_postulacion']} · "
            f"MODO_POSTULACION={_seguridad['modo_postulacion']}"
        )
        st.caption(
            "Bumeran usa Playwright + Chromium (navegador real) en vez de "
            "requests simples -- por eso es opcional y más lento que "
            "Computrabajo. Ver README."
        )
        if not _seguridad["dry_run_postulacion"]:
            st.error(
                "DRY_RUN_POSTULACION está en False en core/constants.py. "
                "Esta UI no envía postulaciones igual, pero avisá antes de seguir."
            )

    st.caption(f"[Código en GitHub]({REPO_URL})")

# ---------------------------------------------------------------------
# Encabezado
# ---------------------------------------------------------------------

st.title("Agente Laboral Gen")
st.caption("Encontrá ofertas compatibles con tu perfil.")
# Texto discreto en vez de un st.info -- es informativo, no requiere
# llamar la atencion del usuario cada vez que abre la app.
st.markdown(
    '<div class="alg-aviso-discreto">🔒 Esta versión solo busca y analiza ofertas. '
    "No realiza postulaciones ni envía mensajes. Tu CV se procesa localmente y no se guarda.</div>",
    unsafe_allow_html=True,
)


def _al_cambiar_modo():
    """Dias y maximo de resultados por defecto distintos segun modo --
    con pocos dias/pocos resultados, Búsqueda real devuelve 0 seguido.
    Se resetea al valor sugerido de cada modo al tocar el selector."""
    es_real = st.session_state.get("modo_busqueda") == "Búsqueda real"
    st.session_state["dias_publicacion"] = 30 if es_real else 2
    st.session_state["max_resultados"] = 50 if es_real else 10


# Modo Demo deshabilitado por defecto -- ver docstring del archivo. Para
# reactivarlo (pruebas sin red), volver esta constante a True.
MODO_DEMO_HABILITADO = False

if MODO_DEMO_HABILITADO:
    modo = st.radio(
        "Modo", ["Demo seguro", "Búsqueda real"], horizontal=True,
        key="modo_busqueda", on_change=_al_cambiar_modo,
    )
else:
    modo = "Búsqueda real"
    st.session_state.setdefault("modo_busqueda", modo)
    st.session_state.setdefault("dias_publicacion", 30)
    st.session_state.setdefault("max_resultados", 50)

if modo == "Demo seguro":
    # UI minima para el modo demo -- no replica el flujo de 4 pasos (no
    # tiene sentido sin CV real). Se mantiene funcional para pruebas
    # rapidas sin red si se reactiva MODO_DEMO_HABILITADO.
    st.warning("Modo demo: resultados simulados para probar la app, sin conexión a portales reales.")
    zona = st.selectbox("Zona", OPCIONES_ZONA, key="filtro_zona")
    modalidad = st.selectbox("Modalidad", ["Cualquiera", "Remoto", "Híbrido", "Presencial"])
    categorias = st.multiselect("Categorías", core.categorias_disponibles(), key="filtro_categorias")
    seniority = st.multiselect("Seniority", OPCIONES_SENIORITY, key="filtro_seniority")
    palabras_obligatorias = st.text_input("Palabras obligatorias (separadas por coma)", key="filtro_palabras_obligatorias")
    palabras_excluidas = st.text_input("Palabras excluidas (separadas por coma)", key="filtro_palabras_excluidas")
    max_resultados = st.slider("Máximo de resultados", 1, 10, key="max_resultados")
    if st.button("Buscar ofertas demo", type="primary"):
        filtros = {
            "palabras_obligatorias": [p for p in palabras_obligatorias.split(",")],
            "palabras_excluidas": [p for p in palabras_excluidas.split(",")],
            "zona": zona, "modalidad": modalidad, "categorias": categorias,
            "seniority": seniority, "max_resultados": max_resultados,
        }
        nuevas, acciones_df, datos_resumen = core.generar_resultados_demo(filtros)
        excel_bytes = core.generar_excel_bytes(nuevas, acciones_df, datos_resumen)
        excel_nombre = core.nombre_archivo_excel(datos_resumen)
        # criterios_snapshot=None: el aviso de "resultados desactualizados"
        # solo aplica a busqueda real (ver _renderizar_resultados).
        st.session_state["resultados_busqueda"] = (nuevas, acciones_df, datos_resumen, excel_bytes, excel_nombre, None)
        st.session_state["filtro_vista_resultados"] = "Todas"

    _renderizar_resultados()

else:
    # -------------------------------------------------------------
    # PASO ① — Tu perfil
    # -------------------------------------------------------------
    paso_actual = 1 if "perfil_cv" not in st.session_state else (
        2 if "resultados_busqueda" not in st.session_state else 4
    )
    _renderizar_pasos(paso_actual)

    with st.container(border=True):
        st.markdown('<div class="alg-section-title">① Tu perfil</div>', unsafe_allow_html=True)
        st.caption("PDF · DOCX · TXT — se lee en memoria, no se guarda en disco.")
        cv_file = st.file_uploader("Subí tu CV", type=["pdf", "docx", "txt"], label_visibility="collapsed")

        if cv_file is not None:
            identidad_actual = (cv_file.name, cv_file.size)
            if st.session_state.get("perfil_cv_identidad") != identidad_actual:
                with st.spinner("Analizando tu CV..."):
                    texto_cv = None
                    try:
                        texto_cv = cv_parser.leer_texto_cv(cv_file)
                    except ValueError as e:
                        st.error(str(e))
                    if texto_cv is not None:
                        if not texto_cv.strip():
                            st.warning(
                                "No se pudo extraer texto de este archivo (¿PDF escaneado/imagen, "
                                "sin capa de texto? no se hace OCR todavía). Probá con un PDF con "
                                "texto seleccionable, o subí un DOCX/TXT."
                            )
                        else:
                            st.session_state["perfil_cv"] = cv_parser.analizar_cv(texto_cv)
                            st.session_state["perfil_cv_identidad"] = identidad_actual
                            st.session_state.pop("perfil_aplicado", None)
                            st.session_state.pop("resultados_busqueda", None)
                            # Automatico: precarga Preferencias con lo que se
                            # acaba de detectar, sin exigir un click aparte.
                            _precargar_filtros_desde_perfil()

        if "perfil_cv" in st.session_state and "seniority_detectada" not in st.session_state["perfil_cv"]:
            # Perfil de una version anterior del parser, quedo en memoria de
            # la sesion de Streamlit (el hot-reload no limpia session_state
            # solo). Se descarta en vez de romper con KeyError -- pide
            # reanalizar.
            st.session_state.pop("perfil_cv", None)
            st.info("El análisis del CV cambió desde la última carga. Volvé a subir tu CV.")

        if "perfil_cv" in st.session_state:
            perfil = st.session_state["perfil_cv"]
            st.success("✓ CV analizado correctamente")
            st.caption("Revisalo y ajustalo si hace falta -- es una sugerencia, no una verdad absoluta.")

            col_izq, col_der = st.columns(2)
            with col_izq:
                st.text_input("Nombre detectado", value=perfil["nombre"], key="perfil_nombre_edit")
                st.text_input("Ubicación detectada", value=perfil["ubicacion"], key="perfil_ubicacion_edit")
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

            st.write(
                "**Puestos objetivo sugeridos:** "
                + (", ".join(perfil["puestos_objetivo"]) if perfil["puestos_objetivo"] else "— (no se detectó categoría clara)")
            )

            with st.expander("Editar perfil avanzado"):
                st.text_input("Email detectado", value=perfil["email"], key="perfil_email_edit")
                st.text_input("Teléfono detectado", value=perfil["telefono"], key="perfil_telefono_edit")
                st.text_input(
                    "Seniority detectada en el CV", value=perfil["seniority_detectada"],
                    key="perfil_seniority_detectada_edit", disabled=True,
                    help="Informativa, no se usa para filtrar. El nivel que se busca es el de arriba.",
                )
                st.text_input("Herramientas detectadas", value=", ".join(perfil["herramientas"]), key="perfil_herramientas_edit")
                st.text_input("Idiomas detectados", value=", ".join(perfil["idiomas"]), key="perfil_idiomas_edit")

                exp_col, edu_col = st.columns(2)
                with exp_col:
                    st.caption("Experiencia detectada (texto crudo)")
                    st.text(perfil["experiencia"] or "No se detectó una sección de experiencia clara.")
                with edu_col:
                    st.caption("Educación detectada (texto crudo)")
                    st.text(perfil["educacion"] or "No se detectó una sección de educación clara.")

                busquedas_sugeridas = cv_parser.generar_busquedas_desde_perfil(perfil)
                st.text_input(
                    "Puestos o búsquedas a consultar (sugeridas, editable)",
                    value=", ".join(busquedas_sugeridas), key="perfil_busquedas_edit",
                    help="Se arman a partir de categorías, skills y seniority objetivo.",
                )
                st.text_input(
                    "Palabras obligatorias sugeridas (opcional)", value=", ".join(perfil["palabras_clave_incluir"]),
                    key="perfil_palabras_incluir_edit",
                    help="A propósito 1 sola palabra: el filtro exige que TODAS estén en el título.",
                )
                st.checkbox(
                    "Aplicar esta palabra obligatoria al filtro (si no, se deja el filtro como está)",
                    value=False, key="perfil_aplicar_obligatoria_edit",
                    help="Por defecto NO se carga: en perfiles mixtos una sola palabra obligatoria puede dejar afuera ofertas buenas.",
                )
                if st.session_state.get("perfil_aplicar_obligatoria_edit"):
                    st.warning("Este filtro puede dejar afuera ofertas compatibles que no usen exactamente esa palabra.")
                st.text_input(
                    "Palabras excluidas sugeridas", value=", ".join(perfil["palabras_clave_excluir"]),
                    key="perfil_palabras_excluir_edit",
                )
                st.button("Volver a aplicar mi perfil a las preferencias", on_click=_precargar_filtros_desde_perfil)
                if st.session_state.get("perfil_aplicado"):
                    st.success("Preferencias actualizadas con tu perfil.")

    # -------------------------------------------------------------
    # PASO ② — Preferencias
    # -------------------------------------------------------------
    with st.container(border=True):
        st.markdown('<div class="alg-section-title">② Preferencias</div>', unsafe_allow_html=True)

        st.markdown("**¿Qué tipo de trabajo buscás?**")
        categorias = st.multiselect(
            "Categorías", core.categorias_disponibles(), placeholder="Elegir categorías",
            key="filtro_categorias", label_visibility="collapsed",
        )
        seniority = st.multiselect(
            "Seniority", OPCIONES_SENIORITY, placeholder="Elegir seniority (Trainee/Junior/Semi Senior)",
            key="filtro_seniority",
        )

        col_zona, col_dias = st.columns(2)
        with col_zona:
            zona = st.selectbox("Ubicación", OPCIONES_ZONA, key="filtro_zona")
        with col_dias:
            dias_publicacion = st.slider("Publicado en los últimos (días)", 1, 30, key="dias_publicacion")

        st.markdown("**Fuentes**")
        col_ct, col_bu = st.columns(2)
        with col_ct:
            usar_computrabajo = st.checkbox("Computrabajo", value=True, key="usar_computrabajo")
        with col_bu:
            usar_bumeran = st.checkbox(
                "Bumeran (opcional, puede tardar más)", value=False, key="usar_bumeran",
                help="Usa un navegador real (Playwright + Chromium) en vez de requests simples -- ver Información técnica en la barra lateral.",
            )
        st.caption("Computrabajo funciona siempre. Bumeran es opcional y amplía la búsqueda. Indeed todavía no está conectado.")
        fuentes_activas = [n for n, activa in (("Computrabajo", usar_computrabajo), ("Bumeran", usar_bumeran)) if activa]
        if not fuentes_activas:
            st.warning("Elegí al menos una fuente para poder buscar.")

        terminos_busqueda = st.text_input(
            "Puestos o búsquedas a consultar (separado por coma)", key="terminos_busqueda",
            placeholder="ej: power bi, soporte it, analista de datos",
            help=(
                "Si subiste un CV, estas búsquedas ya vienen sugeridas a partir de tu "
                "perfil -- editalas libremente. Términos concretos y cortos funcionan mejor."
            ),
        )

        with st.expander("▸ Filtros avanzados"):
            modalidad = st.selectbox("Modalidad", ["Cualquiera", "Remoto", "Híbrido", "Presencial"], key="filtro_modalidad")
            palabras_obligatorias = st.text_input("Palabras obligatorias (separadas por coma)", key="filtro_palabras_obligatorias")
            palabras_excluidas = st.text_input("Palabras excluidas (separadas por coma)", key="filtro_palabras_excluidas")
            max_resultados = st.slider("Máximo de resultados", 1, 50, key="max_resultados")
            st.caption(
                "\"Publicado en los últimos\" y \"Máximo de resultados\" se mandan directo "
                "a Computrabajo/Bumeran. El resto se aplica después, sobre lo que haya "
                "devuelto la búsqueda."
            )

    # -------------------------------------------------------------
    # PASO ③ — Buscar (sin card: es un titulo + 1 boton, envolverlo en
    # una caja no agrupa nada -- el negro del CTA ya lo hace visible)
    # -------------------------------------------------------------
    st.markdown('<div class="alg-section-title alg-section-title-spaced">③ Buscar</div>', unsafe_allow_html=True)
    buscar = st.button("🔎 Buscar ofertas", type="primary", use_container_width=True)

    if buscar:
        st.session_state.pop("perfil_aplicado", None)
        st.session_state["filtro_vista_resultados"] = "Todas"
        filtros = {
            "palabras_obligatorias": [p for p in palabras_obligatorias.split(",")],
            "palabras_excluidas": [p for p in palabras_excluidas.split(",")],
            "zona": zona,
            "modalidad": modalidad,
            "categorias": categorias,
            "seniority": seniority,
            "max_resultados": max_resultados,
        }
        terminos = [t.strip() for t in terminos_busqueda.split(",") if t.strip()]
        # "cv" = el campo estaba vacio, se uso el fallback automatico del
        # perfil. "campo" = el campo tenia contenido (sea porque el
        # usuario lo escribio a mano, o porque quedo pre-cargado
        # automaticamente al analizar el CV) -- desde el campo no se
        # puede distinguir esos dos casos, y esta bien etiquetarlo
        # "editadas por el usuario" en ambos.
        origen_terminos = "campo" if terminos else None
        if not terminos and "perfil_cv" in st.session_state:
            terminos = cv_parser.generar_busquedas_desde_perfil(st.session_state["perfil_cv"])
            origen_terminos = "cv"

        if not terminos:
            st.error("Subí un CV o escribí al menos un puesto para buscar.")
        elif not fuentes_activas:
            st.error("Elegí al menos una fuente (Computrabajo y/o Bumeran) para buscar.")
        else:
            with st.status("Buscando oportunidades...", expanded=True) as status:
                def _reportar(mensaje):
                    status.write(mensaje)

                config_real = dict(filtros, terminos=terminos, dias=dias_publicacion, fuentes=fuentes_activas)
                nuevas, acciones_df, datos_resumen = core.ejecutar_busqueda_real(config_real, on_progreso=_reportar)

                datos_resumen["terminos_usados"] = terminos
                datos_resumen["origen_terminos"] = origen_terminos
                datos_resumen["palabras_obligatorias_usadas"] = [
                    p.strip() for p in palabras_obligatorias.split(",") if p.strip()
                ]
                datos_resumen["filtros_categoria_seniority_activos"] = bool(categorias or seniority)

                excel_bytes = core.generar_excel_bytes(nuevas, acciones_df, datos_resumen)
                excel_nombre = core.nombre_archivo_excel(datos_resumen)
                # Snapshot de los criterios usados en ESTA busqueda -- si el
                # usuario despues cambia algo sin volver a buscar,
                # _renderizar_resultados() lo detecta comparando contra
                # _criterios_busqueda_actuales() y avisa (no borra nada).
                criterios_snapshot = _criterios_busqueda_actuales()
                st.session_state["resultados_busqueda"] = (
                    nuevas, acciones_df, datos_resumen, excel_bytes, excel_nombre, criterios_snapshot,
                )

                cantidad = len(nuevas)
                texto_cantidad = "1 oportunidad compatible" if cantidad == 1 else f"{cantidad} oportunidades compatibles"
                status.update(label=f"✓ Encontramos {texto_cantidad}", state="complete")

    _renderizar_resultados()
