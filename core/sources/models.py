"""Forma normalizada de una oferta real, comun a todas las fuentes -- para
que core.real_search pueda combinarlas sin importar de donde vinieron."""

CAMPOS_OFERTA = [
    "titulo", "empresa", "fuente", "ubicacion", "modalidad",
    "fecha", "link", "descripcion", "busqueda",
]


def oferta_vacia(**overrides):
    """Dict con todos los campos de CAMPOS_OFERTA en "", pisados por
    'overrides'. Evita KeyError si una fuente no tiene algun dato (ej.
    Computrabajo no expone modalidad en el listado)."""
    base = {campo: "" for campo in CAMPOS_OFERTA}
    base.update(overrides)
    return base
