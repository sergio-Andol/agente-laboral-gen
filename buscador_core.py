"""
Motor de la interfaz visual (ui/app.py) de Agente Laboral Gen.

100% autocontenido: no importa ningun script de scraping/postulacion. La
clasificacion, los datos demo y la exportacion a Excel viven en core/
(constants.py, classifier.py, demo_data.py, exporter.py) -- reglas simples
y genericas, sin ajuste fino de ningun perfil personal. Nada de este
modulo toca red, historial ni postula nada.
"""
import datetime
import re

import pandas as pd

from core import classifier, constants, demo_data, exporter, real_search


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

    nuevas = _aplicar_filtros(nuevas, filtros or {})

    acciones_df, conteo_acciones = classifier.construir_acciones(nuevas)
    conteo_decision = nuevas["decision_sugerida"].value_counts().to_dict()

    datos_resumen = {
        "fecha_hora": inicio.strftime("%Y-%m-%d %H:%M:%S"),
        "modo": "demo",
        "cant_resultados": len(nuevas),
        "postular": conteo_decision.get("POSTULAR", 0),
        "revisar": conteo_decision.get("REVISAR", 0),
        "descartar": conteo_decision.get("DESCARTAR", 0),
        "conteo_acciones": conteo_acciones,
    }
    return nuevas, acciones_df, datos_resumen


def ejecutar_busqueda_real(config, on_progreso=None):
    """Busca ofertas REALES (Computrabajo siempre; Bumeran si esta en
    'fuentes' Y Playwright esta disponible) y las clasifica con el mismo
    motor simple que el modo DEMO. Esto SI hace requests de red en vivo
    -- puede tardar varios segundos (mas si Bumeran esta activo: usa un
    navegador real, no solo requests HTTP), la UI debe envolver el
    llamado en un spinner.

    'config' (dict):
      'terminos': lista de strings a buscar (obligatorio, sin esto no hay
        nada que buscar -- ej. ["analista de datos junior"]).
      'dias': antiguedad maxima del aviso (default 2).
      'max_resultados': tope de resultados a traer (default 10).
      'fuentes': lista de nombres de real_search.FUENTES_DISPONIBLES a
        usar (default: todas, o sea Computrabajo + Bumeran). Si Bumeran
        esta en la lista pero Playwright no esta instalado, esa fuente
        se salta sola (no rompe la busqueda) y el aviso queda en
        datos_resumen['avisos_fuentes'].
      + los mismos filtros post-busqueda que generar_resultados_demo:
        'palabras_obligatorias', 'palabras_excluidas', 'zona',
        'modalidad', 'categorias', 'seniority'.

    'on_progreso': callback opcional callable(str) -- se invoca en los
    puntos reales de avance del pipeline (por fuente, dedupe, clasificar,
    filtrar). Pensado para que la UI muestre feedback honesto durante la
    busqueda (ver ui/app.py) sin inventar progreso que no existe. None
    por defecto: no cambia nada para quien no lo pase.

    Sin postulacion, sin historial, sin tocar disco -- generar_excel_bytes()
    sigue siendo un paso aparte y explicito. Devuelve (nuevas_df,
    acciones_df, datos_resumen), mismo shape que generar_resultados_demo.
    """
    inicio = datetime.datetime.now()
    terminos = config.get("terminos") or []
    dias = config.get("dias", 2)
    max_resultados_busqueda = config.get("max_resultados", 10)
    fuentes = config.get("fuentes") or list(real_search.FUENTES_DISPONIBLES.keys())
    zona = config.get("zona") or "Toda Argentina"
    ciudad = constants.ZONAS.get(zona, {}).get("slug_computrabajo", "")

    # Orden del pipeline, a proposito: buscar crudos ampliados ->
    # normalizar -> DEDUPLICAR -> CLASIFICAR (categoria_detectada/
    # decision_sugerida/motivo_decision/accion_sugerida, todo dentro de
    # real_search.buscar_ofertas_reales) -> recien despues filtrar.
    # _aplicar_filtros() nunca debe correr sobre datos sin clasificar.
    # 'ciudad' llega vacio ("") cuando zona="Toda Argentina" -- eso hace
    # que Computrabajo busque en TODO el pais (ver core/sources/
    # computrabajo.py), en vez de acotar solo a Capital Federal como
    # hacia antes por el default viejo de esa funcion.
    nuevas, diagnostico_busqueda = real_search.buscar_ofertas_reales(
        terminos, dias=dias, max_resultados=max_resultados_busqueda,
        fuentes=fuentes, ciudad=ciudad, on_progreso=on_progreso,
    )
    cant_tras_dedupe = len(nuevas)
    conteo_por_fuente_crudo = diagnostico_busqueda.get("conteo_por_fuente", {})
    if on_progreso:
        on_progreso("Aplicando filtros...")
    nuevas = _aplicar_filtros(nuevas, config)

    acciones_df, conteo_acciones = classifier.construir_acciones(nuevas)
    conteo_decision = (
        nuevas["decision_sugerida"].value_counts().to_dict()
        if "decision_sugerida" in nuevas.columns else {}
    )
    conteo_por_fuente_final = (
        nuevas["fuente"].value_counts().to_dict() if "fuente" in nuevas.columns else {}
    )

    datos_resumen = {
        "fecha_hora": inicio.strftime("%Y-%m-%d %H:%M:%S"),
        "modo": "real",
        "cant_resultados": len(nuevas),
        "cant_crudo": diagnostico_busqueda.get("cant_crudo", 0),
        "cant_tras_dedupe": cant_tras_dedupe,
        "cant_tras_filtros": len(nuevas),
        # 'conteo_por_fuente': cuantas trajo cada fuente tras deduplicar,
        # ANTES de filtros de contenido y del recorte a max_resultados.
        # 'conteo_por_fuente_final': cuantas de cada fuente quedan en el
        # resultado final (lo que se ve en pantalla y se exporta a
        # Excel) -- si una fuente tenia crudas pero termino en 0 aca, se
        # muestra en la UI en vez de ocultarse en silencio.
        "conteo_por_fuente": conteo_por_fuente_crudo,
        "conteo_por_fuente_final": conteo_por_fuente_final,
        # Fuentes REALMENTE pedidas en esta busqueda -- distinto de las
        # keys de conteo_por_fuente, que solo aparecen si esa fuente trajo
        # >=1 resultado. La UI la necesita para distinguir "Bumeran no
        # estaba tildado" de "Bumeran estaba tildado pero dio 0".
        "fuentes_solicitadas": fuentes,
        "avisos_fuentes": diagnostico_busqueda.get("avisos_fuentes", []),
        "alcance_geografico": zona,
        "postular": conteo_decision.get("POSTULAR", 0),
        "revisar": conteo_decision.get("REVISAR", 0),
        "descartar": conteo_decision.get("DESCARTAR", 0),
        "conteo_acciones": conteo_acciones,
    }
    return nuevas, acciones_df, datos_resumen


def _aplicar_filtros(nuevas, filtros):
    """Recorta el DataFrame (DEMO o real) segun los filtros de la
    sidebar. 'fuentes' no se aplica aca: en DEMO los 6 avisos comparten
    fuente="Demo"; en real, el filtro de fuente ya se resuelve al elegir
    qué buscar_fn llamar (real_search.FUENTES_DISPONIBLES).

    Defensivo a proposito: si al DataFrame le falta alguna columna que
    un filtro necesita (ej. categoria_detectada, si algun dia se cambia
    el pipeline y se llega a llamar esta funcion antes de clasificar),
    ese filtro puntual se salta en vez de romper con KeyError -- se
    imprime un aviso interno, no se corta la corrida entera."""
    df = nuevas

    def _tiene_columna(nombre):
        if nombre in df.columns:
            return True
        print(f"[_aplicar_filtros] falta la columna '{nombre}' -- se salta ese filtro.")
        return False

    obligatorias = [p.strip().lower() for p in filtros.get("palabras_obligatorias", []) if p.strip()]
    if obligatorias and _tiene_columna("titulo"):
        texto = df["titulo"].fillna("").str.lower()
        df = df[texto.apply(lambda t: all(p in t for p in obligatorias))]

    excluidas = [p.strip().lower() for p in filtros.get("palabras_excluidas", []) if p.strip()]
    if excluidas and _tiene_columna("titulo"):
        texto = df["titulo"].fillna("").str.lower()
        df = df[~texto.apply(lambda t: any(p in t for p in excluidas))]

    # "Toda Argentina"/"Cualquiera"/vacio = sin filtro de ubicacion. Para
    # una zona especifica, NO se busca el nombre de la zona tal cual
    # (ej. "caba") como substring -- Computrabajo nunca devuelve "CABA"
    # en la ubicacion, devuelve "Capital Federal". Se usa el texto real
    # mapeado en core.constants.ZONAS.
    zona_cruda = filtros.get("zona") or ""
    zona_normalizada = zona_cruda.strip().lower()
    if zona_normalizada and zona_normalizada not in ("cualquiera", "toda argentina") and _tiene_columna("ubicacion"):
        texto_filtro = (constants.ZONAS.get(zona_cruda, {}).get("texto_filtro") or zona_normalizada).lower()
        if texto_filtro:
            df = df[df["ubicacion"].fillna("").str.lower().str.contains(texto_filtro, regex=False)]

    modalidad = (filtros.get("modalidad") or "").strip().lower()
    if modalidad and modalidad != "cualquiera" and _tiene_columna("modalidad"):
        df = df[df["modalidad"].fillna("").str.lower() == modalidad]

    categorias = filtros.get("categorias") or []
    if categorias and _tiene_columna("categoria_detectada"):
        df = df[df["categoria_detectada"].isin(categorias)]

    # Filtro de seniority: NO exige que el titulo diga literalmente
    # "junior"/"trainee" -- muchas ofertas aptas no lo dicen. En cambio,
    # cuando el filtro esta activo, deja pasar todo (incluidas ofertas
    # sin seniority explicita) y solo DESCARTA titulos con seniority alta
    # o de liderazgo clara. Si el usuario incluyo "Semi Senior" entre los
    # niveles elegidos, esos terminos dejan de vetarse (es lo que pidio).
    seniority = [s.strip() for s in filtros.get("seniority", []) if s.strip()]
    if seniority and _tiene_columna("titulo"):
        veto = ["senior", "sr", "ssr", "semi senior", "semi-senior",
                "líder", "lider", "jefe", "gerente", "responsable"]
        if "Semi Senior" in seniority:
            veto = [v for v in veto if v not in ("ssr", "semi senior", "semi-senior")]
        patron_veto = re.compile(r"\b(?:" + "|".join(re.escape(v) for v in veto) + r")\b")
        texto = df["titulo"].fillna("").str.lower()
        df = df[~texto.apply(lambda t: bool(patron_veto.search(t)))]

    max_resultados = filtros.get("max_resultados")
    if max_resultados and _tiene_columna("fuente"):
        df = _recortar_balanceado_por_fuente(df, int(max_resultados))
    elif max_resultados:
        df = df.head(int(max_resultados))

    return df


def _recortar_balanceado_por_fuente(df, tope):
    """Recorta a 'tope' filas repartiendo en ronda-robin entre las
    fuentes presentes en 'df', en vez de cortar la lista global de
    punta a punta con head().

    Por que: 'df' ya viene ordenado globalmente por decision/relevancia
    (mejores ofertas primero), pero Computrabajo pagina y Bumeran no --
    Computrabajo aporta muchas mas filas crudas. Un head(tope) sobre la
    lista global le da todo el cupo a la fuente con mas volumen y deja
    a la otra en 0, aunque haya aportado ofertas validas (bug real
    detectado: Computrabajo 50 crudas + Bumeran 20 -> las primeras 10
    finales eran todas Computrabajo). La ronda-robin garantiza que cada
    fuente activa se quede con una porcion, preservando el orden interno
    (mejor primero) de cada una. Con una sola fuente presente (modo DEMO,
    o busqueda real con 1 sola fuente activa) el resultado es identico a
    head(tope) -- no hay regresion en esos casos."""
    if df.empty or len(df) <= tope:
        return df

    orden_fuentes = list(dict.fromkeys(df["fuente"]))
    grupos = {f: list(indices) for f, indices in df.groupby("fuente", sort=False).groups.items()}
    punteros = {f: 0 for f in orden_fuentes}

    elegidos = []
    while len(elegidos) < tope:
        avanzo = False
        for f in orden_fuentes:
            lista = grupos[f]
            p = punteros[f]
            if p < len(lista):
                elegidos.append(lista[p])
                punteros[f] = p + 1
                avanzo = True
                if len(elegidos) >= tope:
                    break
        if not avanzo:
            break

    # sorted() restaura el orden original (decision/relevancia) sobre el
    # subconjunto elegido -- la ronda-robin decide QUE filas entran, no
    # el orden en que se muestran.
    return df.loc[sorted(elegidos)].reset_index(drop=True)


def generar_excel_bytes(nuevas, acciones_df, datos_resumen):
    """Arma el .xlsx en memoria (RESUMEN + RESULTADOS + ACCIONES si
    corresponde) y devuelve los bytes -- no toca disco. Es lo que usa la
    UI para el boton de descarga directa (ver ui/app.py)."""
    return exporter.generar_excel_bytes(nuevas, acciones_df, datos_resumen)


def nombre_archivo_excel(datos_resumen):
    """Nombre legible para el boton de descarga, ej.
    agente_laboral_resultados_2026-08-21_03-18.xlsx."""
    return exporter.nombre_archivo_descarga(datos_resumen)


def guardar_excel_en_disco(nuevas, acciones_df, datos_resumen):
    """Compatibilidad: escribe el Excel en resultados/YYYY-MM/ via
    core.exporter, ademas de en memoria. Ya NO es parte del flujo
    principal de la UI. Nunca toca ningun historial (no existe en este
    proyecto). Devuelve la ruta del archivo generado."""
    return exporter.guardar_excel_en_disco(nuevas, acciones_df, datos_resumen)
