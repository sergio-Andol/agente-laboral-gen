"""Orquesta la busqueda REAL: combina fuentes activas (hoy: solo
Computrabajo), clasifica cada oferta con core.classifier -- el mismo
motor simple que usa el modo DEMO -- y arma el DataFrame final.

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
from core.sources import computrabajo

COLUMNAS_RESULTADO = constants.COLUMNAS + [
    "categoria_detectada", "decision_sugerida", "motivo_decision", "accion_sugerida",
    "busquedas_match",
]

# Nombre visible -> funcion buscar(query, dias=, max_resultados=) -> list[dict].
# Bumeran no esta aca: core.sources.bumeran.buscar() existe pero lanza
# NotImplementedError a proposito (ver ese archivo).
FUENTES_DISPONIBLES = {
    "Computrabajo": computrabajo.buscar,
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


def buscar_ofertas_reales(terminos, dias=2, max_resultados=10, fuentes=None):
    """terminos: lista de strings a buscar (se consulta cada uno por
    separado). fuentes: lista de nombres de FUENTES_DISPONIBLES a usar
    (default: todas las disponibles hoy, o sea Computrabajo).

    Devuelve (df, diagnostico): df ya deduplicado y clasificado, mismo
    esquema de columnas que el modo DEMO -- SIN recortar a max_resultados
    aca (ver nota abajo). diagnostico es un dict con 'cant_crudo' y
    'cant_tras_dedupe', para que la UI pueda mostrar cuanto se filtro en
    cada etapa.

    A proposito NO se trunca a max_resultados en esta funcion: eso dejaba
    la busqueda en 0 visibles si los primeros N (crudos o duplicados, que
    ademas quedan dominados por el primer termino de la lista) no pasaban
    los filtros de la sidebar, aunque hubiera mas ofertas compatibles mas
    abajo. Se trae MAS volumen crudo del pedido final
    (max_resultados_crudos = max(max_resultados*3, 50)); el recorte final
    a max_resultados queda para buscador_core._aplicar_filtros(), que
    corre DESPUES de deduplicar, clasificar y aplicar los filtros de
    categoria/seniority/palabras."""
    fuentes = fuentes or list(FUENTES_DISPONIBLES.keys())
    terminos = [t.strip() for t in (terminos or []) if t.strip()]
    diagnostico = {"cant_crudo": 0, "cant_tras_dedupe": 0}
    if not terminos:
        return _dataframe_vacio(), diagnostico

    max_resultados_crudos = max(max_resultados * 3, 50)

    crudas = []
    for nombre_fuente in fuentes:
        buscar_fn = FUENTES_DISPONIBLES.get(nombre_fuente)
        if not buscar_fn:
            continue
        for termino in terminos:
            try:
                crudas.extend(buscar_fn(termino, dias=dias, max_resultados=max_resultados_crudos))
            except NotImplementedError as e:
                print(f"[real_search] {nombre_fuente}: {e}")
            except Exception as e:
                print(f"[real_search] {nombre_fuente} ('{termino}'): error inesperado: {e}")

    diagnostico["cant_crudo"] = len(crudas)
    if not crudas:
        return _dataframe_vacio(), diagnostico

    df = pd.DataFrame(crudas)
    df, _ = _deduplicar(df)
    diagnostico["cant_tras_dedupe"] = len(df)

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

    return df[COLUMNAS_RESULTADO].reset_index(drop=True), diagnostico
