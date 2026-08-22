"""Orquesta la busqueda REAL: combina fuentes activas (Computrabajo
siempre, Bumeran si esta seleccionado Y Playwright disponible), clasifica
cada oferta con core.classifier -- el mismo motor simple que usa el modo
DEMO -- y arma el DataFrame final.

Sin postulacion, sin historial, sin guardar nada en disco. Cada llamada a
buscar_ofertas_reales() es una consulta de red en vivo -- puede tardar
varios segundos (la UI debe mostrar spinner, ver ui/app.py).

Orden del pipeline, a proposito (ver punto 4 del pedido que agrego esta
funcion): buscar crudos ampliados -> normalizar -> DEDUPLICAR ->
clasificar -> (filtros y recorte a max_resultados quedan en
buscador_core._aplicar_filtros(), que corre despues)."""
import re

import pandas as pd

from core import classifier, constants
from core.sources import bumeran, computrabajo

COLUMNAS_RESULTADO = constants.COLUMNAS + [
    "categoria_detectada", "decision_sugerida", "motivo_decision", "accion_sugerida",
    "busquedas_match",
]

# Nombre visible -> funcion buscar(query, dias=, max_resultados=) -> list[dict].
# Indeed no esta aca: bloquea con Cloudflare, no implementado.
FUENTES_DISPONIBLES = {
    "Computrabajo": computrabajo.buscar,
    "Bumeran": bumeran.buscar,
}


def _dataframe_vacio():
    return pd.DataFrame(columns=COLUMNAS_RESULTADO)


def _normalizar_link(link):
    """Saca query string y fragment -- Computrabajo agrega un fragment
    tipo '#lc=ListOffers-Score6-0' que codifica la POSICION dentro de
    ESE listado de busqueda particular, no la identidad del aviso. Sin
    esto, la misma oferta real encontrada por 2 terminos distintos tiene
    2 links "diferentes" y el dedupe por link no la detecta."""
    if not link:
        return ""
    link = str(link).split("#", 1)[0].split("?", 1)[0]
    return link.strip().lower().rstrip("/")


def _normalizar_texto(texto):
    return re.sub(r"\s+", " ", str(texto or "").strip().lower())


def _clave_dedup(fila):
    """Dedupe principal por link normalizado; si no hay link, cae a la
    combinacion normalizada titulo+empresa+fuente+ubicacion."""
    link_norm = _normalizar_link(fila.get("link"))
    if link_norm:
        return f"link::{link_norm}"
    combo = "|".join(
        _normalizar_texto(fila.get(campo)) for campo in ("titulo", "empresa", "fuente", "ubicacion")
    )
    return f"combo::{combo}"


def _deduplicar(df):
    """Devuelve (df_deduplicado, cantidad_antes). Conserva la primera
    aparicion de cada oferta, y junta en 'busquedas_match' TODOS los
    terminos de busqueda que la encontraron (sin repetir, en orden de
    aparicion) -- no se pierde ese dato solo por quedarse con la
    primera fila."""
    cantidad_antes = len(df)
    if df.empty:
        df = df.copy()
        df["busquedas_match"] = []
        return df, cantidad_antes

    df = df.copy()
    df["_clave_dedup"] = df.apply(_clave_dedup, axis=1)

    busquedas_por_clave = (
        df.groupby("_clave_dedup")["busqueda"]
        .apply(lambda serie: ", ".join(dict.fromkeys(s for s in serie if s)))
        .to_dict()
    )

    df = df.drop_duplicates(subset="_clave_dedup", keep="first").copy()
    df["busquedas_match"] = df["_clave_dedup"].map(busquedas_por_clave)
    df = df.drop(columns=["_clave_dedup"]).reset_index(drop=True)
    return df, cantidad_antes


def buscar_ofertas_reales(terminos, dias=2, max_resultados=10, fuentes=None, ciudad="", on_progreso=None):
    """terminos: lista de strings a buscar (se consulta cada uno por
    separado). fuentes: lista de nombres de FUENTES_DISPONIBLES a usar
    (default: todas las disponibles hoy, o sea Computrabajo + Bumeran).
    ciudad: slug de ciudad para Computrabajo ("" = todo el pais, ver
    core.constants.ZONAS). Bumeran ignora este parametro (no soporta
    scope de ciudad en esta implementacion, absorbe el kwarg via
    **_kwargs sin romper).

    on_progreso: callback opcional callable(str), invocado en los puntos
    reales de avance (antes/despues de cada fuente, antes de deduplicar,
    antes de clasificar) -- para que la UI muestre feedback honesto sin
    inventar pasos que no existen. None por defecto (no hace nada).

    Devuelve (df, diagnostico): df ya deduplicado y clasificado, mismo
    esquema de columnas que el modo DEMO -- SIN recortar a max_resultados
    aca (ver nota abajo). diagnostico trae 'cant_crudo', 'cant_tras_dedupe',
    'conteo_por_fuente' (ofertas unicas por fuente, post-dedupe) y
    'avisos_fuentes' (mensajes de fuentes que fallaron, ej. Bumeran sin
    Playwright) -- para que la UI pueda mostrar cuanto aporto cada etapa
    y avisar sin romper si una fuente no respondio.

    A proposito NO se trunca a max_resultados en esta funcion: eso dejaba
    la busqueda en 0 visibles si los primeros N (crudos o duplicados, que
    ademas quedan dominados por el primer termino de la lista) no pasaban
    los filtros de la sidebar, aunque hubiera mas ofertas compatibles mas
    abajo. Se trae MAS volumen crudo del pedido final
    (max_resultados_crudos = max(max_resultados*3, 50)); el recorte final
    a max_resultados queda para buscador_core._aplicar_filtros(), que
    corre DESPUES de deduplicar, clasificar y aplicar los filtros de
    categoria/seniority/palabras."""
    def _avisar(mensaje):
        if on_progreso:
            on_progreso(mensaje)

    fuentes = fuentes or list(FUENTES_DISPONIBLES.keys())
    terminos = [t.strip() for t in (terminos or []) if t.strip()]
    diagnostico = {
        "cant_crudo": 0, "cant_tras_dedupe": 0,
        "conteo_por_fuente": {}, "avisos_fuentes": [],
    }
    if not terminos:
        return _dataframe_vacio(), diagnostico

    max_resultados_crudos = max(max_resultados * 3, 50)

    crudas = []
    fuentes_fallidas = set()
    try:
        for nombre_fuente in fuentes:
            buscar_fn = FUENTES_DISPONIBLES.get(nombre_fuente)
            if not buscar_fn:
                continue
            _avisar(f"Buscando en {nombre_fuente}...")
            for termino in terminos:
                if nombre_fuente in fuentes_fallidas:
                    # Ya fallo con este termino (ej. Playwright ausente):
                    # no tiene sentido reintentar termino por termino, se
                    # salta el resto de esta fuente directamente.
                    break
                try:
                    crudas.extend(buscar_fn(
                        termino, dias=dias, max_resultados=max_resultados_crudos, ciudad=ciudad
                    ))
                    if nombre_fuente == "Bumeran":
                        for aviso in bumeran.tomar_avisos():
                            if aviso not in diagnostico["avisos_fuentes"]:
                                diagnostico["avisos_fuentes"].append(aviso)
                except bumeran.BumeranNoDisponible as e:
                    fuentes_fallidas.add(nombre_fuente)
                    if str(e) not in diagnostico["avisos_fuentes"]:
                        diagnostico["avisos_fuentes"].append(str(e))
                    print(f"[real_search] {nombre_fuente}: {e}")
                except NotImplementedError as e:
                    fuentes_fallidas.add(nombre_fuente)
                    print(f"[real_search] {nombre_fuente}: {e}")
                except Exception as e:
                    print(f"[real_search] {nombre_fuente} ('{termino}'): error inesperado: {e}")
            if nombre_fuente not in fuentes_fallidas:
                _avisar(f"✓ {nombre_fuente}")
    finally:
        # Bumeran deja un navegador Playwright abierto (se reusa entre
        # terminos por velocidad) -- se cierra siempre al terminar la
        # corrida, haya ido bien o mal. No hace nada si nunca se abrio.
        bumeran.cerrar_navegador()

    diagnostico["cant_crudo"] = len(crudas)
    if not crudas:
        return _dataframe_vacio(), diagnostico

    # Todo este bloque (dedupe + clasificacion + normalizacion final) va
    # envuelto: si algo inesperado revienta aca (parsing raro de alguna
    # fuente, columna faltante, etc.), la busqueda entera no debe romper
    # -- se devuelve el DataFrame vacio con el esquema correcto y se dej
    # a constancia en 'avisos_fuentes', en vez de propagar la excepcion
    # hasta la UI.
    try:
        _avisar("Eliminando duplicados...")
        df = pd.DataFrame(crudas)
        df, _ = _deduplicar(df)
        diagnostico["cant_tras_dedupe"] = len(df)
        diagnostico["conteo_por_fuente"] = df["fuente"].value_counts().to_dict()

        _avisar("Analizando compatibilidad...")
        relevancias, categorias, decisiones, motivos, acciones = [], [], [], [], []
        for _, fila in df.iterrows():
            texto_titulo_desc = f"{fila['titulo']} {fila.get('descripcion', '')}"
            categoria, cantidad = classifier.detectar_categoria(texto_titulo_desc)
            decision, motivo = classifier.clasificar_decision(fila["titulo"], fila.get("descripcion", ""))
            relevancias.append(cantidad)
            categorias.append(categoria)
            decisiones.append(decision)
            motivos.append(motivo)
            acciones.append(classifier.determinar_accion_sugerida(decision))

        df["relevancia"] = relevancias
        df["categoria_detectada"] = categorias
        df["decision_sugerida"] = decisiones
        df["motivo_decision"] = motivos
        df["accion_sugerida"] = acciones

        df["_orden_decision"] = df["decision_sugerida"].map(constants.ORDEN_DECISION)
        df = df.sort_values(
            by=["_orden_decision", "relevancia"], ascending=[True, False]
        ).drop(columns=["_orden_decision"])

        # Red de seguridad final: aunque todo lo de arriba haya ido bien,
        # garantiza que las columnas esperadas existan antes de indexar
        # con ellas -- una columna faltante rellena con "" en vez de
        # lanzar KeyError.
        for columna in COLUMNAS_RESULTADO:
            if columna not in df.columns:
                df[columna] = ""

        return df[COLUMNAS_RESULTADO].reset_index(drop=True), diagnostico
    except Exception as e:
        print(f"[real_search] error normalizando/clasificando resultados: {e}")
        diagnostico["avisos_fuentes"].append(
            "Ocurrió un error inesperado clasificando los resultados de esta búsqueda; "
            "se muestran 0 ofertas."
        )
        return _dataframe_vacio(), diagnostico
