"""Bumeran: NO implementado todavía.

Bumeran no expone un HTML estatico scrapeable con requests/BeautifulSoup
como Computrabajo -- requeriria Playwright (un navegador Chromium real),
lo que agrega ~300MB de descarga extra (`playwright install chromium`) y
vuelve el proyecto mucho mas pesado de instalar/correr para alguien que
solo quiere probarlo. Se deja afuera a propósito hasta decidir si vale
ese costo para un proyecto de portfolio pensado para bajar y correr
rápido.

Pendiente real, no una limitación técnica de esta fuente en particular.
"""


def buscar(query, **kwargs):
    raise NotImplementedError(
        "Bumeran no está implementado en Agente Laboral Gen todavía "
        "(requeriría agregar Playwright). Usá Computrabajo por ahora."
    )
