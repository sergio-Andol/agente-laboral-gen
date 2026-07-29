"""
Motor de la interfaz visual (ui/app.py) de Agente Laboral Gen.

100% autocontenido: no importa ningun script de scraping/postulacion. La
clasificacion, los datos demo y la exportacion a Excel viven en core/
(constants.py, classifier.py, demo_data.py, exporter.py) -- reglas simples
y genericas, sin ajuste fino de ningun perfil personal. Nada de este
modulo toca red, historial ni postula nada.
"""
import datetime

import pandas as pd

from core import classifier, constants, demo_data, exporter


def resumen_seguridad():
    """Estado de seguridad de postulacion, leido de core.constants (fijo:
    Agente Laboral Gen no tiene ninguna capa de postulacion real)."""
    return {
        "dry_run_postulacion": constants.DRY_RUN_POSTULACION,
        "modo_postulacion": constants.MODO_POSTULACION,
        "max_postulaciones_por_corrida": constants.MAX_POSTULACIONES_POR_CORRIDA,
        "probar_postulacion_en_test": constants.PROBAR_POSTULACION_EN_TEST,
    }


def categorias_disponibles():
    """Categorias que puede devolver classifier.detectar_categoria(), para
    poblar el filtro de categorias en la UI sin hardcodear la lista dos
    veces."""
    return list(constants.CATEGORIAS_KEYWORDS.keys()) + [constants.CATEGORIA_OTRO, constants.CATEGORIA_AMBIGUO]


def generar_resultados_demo(filtros=None):
    """Clasifica las 6 ofertas simuladas de core.demo_data con
    core.classifier (reglas simples) y aplica los filtros de la sidebar.
    Sin efectos secundarios: no escribe Excel ni toca ningun archivo --
    eso queda para exportar_excel(), que el caller dispara aparte.

    'filtros' es opcional: dict con 'palabras_obligatorias',
    'palabras_excluidas', 'zona', 'modalidad', 'categorias', 'seniority',
    'max_resultados' para acotar los 6 datos DEMO en pantalla.

    Devuelve (nuevas_df, acciones_df, datos_resumen).
    """
    inicio = datetime.datetime.now()
    filas_demo = demo_data.generar_datos_demo()

    nuevas = pd.DataFrame(filas_demo)

    relevancias, categorias, decisiones, motivos, acciones = [], [], [], [], []
    for f in filas_demo:
        categoria, cantidad = classifier.detectar_categoria(f"{f['titulo']} {f['descripcion_demo']}")
        decision, motivo = classifier.clasificar_decision(f["titulo"], f["descripcion_demo"])
        relevancias.append(cantidad)
        categorias.append(categoria)
        decisiones.append(decision)
        motivos.append(motivo)
        acciones.append(classifier.determinar_accion_sugerida(decision))

    nuevas["relevancia"] = relevancias
    nuevas["categoria_detectada"] = categorias
    nuevas["decision_sugerida"] = decisiones
    nuevas["motivo_decision"] = motivos
    nuevas["accion_sugerida"] = acciones
    nuevas = nuevas.drop(columns=["descripcion_demo"])

    nuevas["_orden_decision"] = nuevas["decision_sugerida"].map(constants.ORDEN_DECISION)
    nuevas = nuevas.sort_values(
        by=["_orden_decision", "relevancia"], ascending=[True, False]
    ).drop(columns=["_orden_decision"])

    nuevas = _aplicar_filtros_demo(nuevas, filtros or {})

    acciones_df, conteo_acciones = classifier.construir_acciones(nuevas)
    conteo_decision = nuevas["decision_sugerida"].value_counts().to_dict()

    datos_resumen = {
        "fecha_hora": inicio.strftime("%Y-%m-%d %H:%M:%S"),
        "cant_resultados": len(nuevas),
        "postular": conteo_decision.get("POSTULAR", 0),
        "revisar": conteo_decision.get("REVISAR", 0),
        "descartar": conteo_decision.get("DESCARTAR", 0),
        "conteo_acciones": conteo_acciones,
    }
    return nuevas, acciones_df, datos_resumen


def _aplicar_filtros_demo(nuevas, filtros):
    """Recorta el DataFrame DEMO segun los filtros de la sidebar. 'fuentes'
    no se aplica: los 6 avisos DEMO comparten fuente="Demo"."""
    df = nuevas

    obligatorias = [p.strip().lower() for p in filtros.get("palabras_obligatorias", []) if p.strip()]
    if obligatorias:
        texto = df["titulo"].fillna("").str.lower()
        df = df[texto.apply(lambda t: all(p in t for p in obligatorias))]

    excluidas = [p.strip().lower() for p in filtros.get("palabras_excluidas", []) if p.strip()]
    if excluidas:
        texto = df["titulo"].fillna("").str.lower()
        df = df[~texto.apply(lambda t: any(p in t for p in excluidas))]

    zona = (filtros.get("zona") or "").strip().lower()
    if zona and zona != "cualquiera":
        df = df[df["ubicacion"].fillna("").str.lower().str.contains(zona, regex=False)]

    modalidad = (filtros.get("modalidad") or "").strip().lower()
    if modalidad and modalidad != "cualquiera":
        df = df[df["modalidad"].fillna("").str.lower() == modalidad]

    categorias = filtros.get("categorias") or []
    if categorias:
        df = df[df["categoria_detectada"].isin(categorias)]

    # OR, no AND: alcanza con que el titulo tenga alguna de las
    # seniorities elegidas.
    seniority = [s.strip().lower() for s in filtros.get("seniority", []) if s.strip()]
    if seniority:
        texto = df["titulo"].fillna("").str.lower()
        df = df[texto.apply(lambda t: any(s in t for s in seniority))]

    max_resultados = filtros.get("max_resultados")
    if max_resultados:
        df = df.head(int(max_resultados))

    return df


def exportar_excel(nuevas, acciones_df, datos_resumen):
    """Escribe el Excel DEMO en resultados/YYYY-MM/ via core.exporter.
    Nunca toca ningun historial (no existe en este proyecto). Devuelve la
    ruta del archivo generado."""
    return exporter.exportar_excel(nuevas, acciones_df, datos_resumen)
