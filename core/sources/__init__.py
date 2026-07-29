"""Fuentes de busqueda real de ofertas de trabajo.

Cada modulo expone buscar(query, dias=..., max_resultados=..., **kwargs)
-> list[dict], con el formato normalizado de core.sources.models. Ninguna
fuente postula, guarda historial ni escribe nada en disco -- solo lee y
devuelve datos.
"""
