"""Orquesta la busqueda REAL: combina fuentes activas (hoy: solo
Computrabajo), clasifica cada oferta con core.classifier -- el mismo
motor simple que usa el modo DEMO -- y arma el DataFrame final.

Sin postulacion, sin historial, sin guardar nada en disco. Cada llamada a
buscar_ofertas_reales() es una consulta de red en vivo -- puede tardar
varios segundos (la UI debe mostrar spinner, ver ui/app.py).
"""
import pandas as pd

from core import classifier, constants
from core.sources import computrabajo

COLUMNAS_RESULTADO = constants.COLUMNAS + [
    "categoria_detectada", "decision_sugerida", "motivo_decision", "accion_sugerida",
]

# Nombre visible -> funcion buscar(query, dias=, max_resultados=) -> list[dict].
# Bumeran no esta aca: core.sources.bumeran.buscar() existe pero lanza
# NotImplementedError a proposito (ver ese archivo).
FUENTES_DISPONIBLES = {
    "Computrabajo": computrabajo.buscar,
}


def _dataframe_vacio():
    return pd.DataFrame(columns=COLUMNAS_RESULTADO)


def buscar_ofertas_reales(terminos, dias=2, max_resultados=10, fuentes=None):
    """terminos: lista de strings a buscar (se consulta cada uno por
    separado, se combinan y deduplican por link). fuentes: lista de
    nombres de FUENTES_DISPONIBLES a usar (default: todas las
    disponibles hoy, o sea Computrabajo). Devuelve un DataFrame ya
    clasificado, mismo esquema de columnas que el modo DEMO."""
    fuentes = fuentes or list(FUENTES_DISPONIBLES.keys())
    terminos = [t.strip() for t in (terminos or []) if t.strip()]
    if not terminos:
        return _dataframe_vacio()

    crudas = []
    for nombre_fuente in fuentes:
        buscar_fn = FUENTES_DISPONIBLES.get(nombre_fuente)
        if not buscar_fn:
            continue
        for termino in terminos:
            try:
                crudas.extend(buscar_fn(termino, dias=dias, max_resultados=max_resultados))
            except NotImplementedError as e:
                print(f"[real_search] {nombre_fuente}: {e}")
            except Exception as e:
                print(f"[real_search] {nombre_fuente} ('{termino}'): error inesperado: {e}")

    if not crudas:
        return _dataframe_vacio()

    df = pd.DataFrame(crudas)
    df = df.drop_duplicates(subset=["link"]).reset_index(drop=True)
    df = df.head(max_resultados).copy()

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

    return df[COLUMNAS_RESULTADO].reset_index(drop=True)
