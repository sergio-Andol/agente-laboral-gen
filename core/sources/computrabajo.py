"""Busqueda real de ofertas en Computrabajo (Argentina).

Solo requests + BeautifulSoup, sin navegador -- la fuente mas liviana y
estable para scraping (sin Cloudflare, sin Playwright). Selectores tal
como aparecen hoy en el HTML publico del sitio; si Computrabajo cambia su
markup, esto puede dejar de funcionar (no hay forma de evitarlo del todo
en un scraper).

A proposito NO trae la descripcion completa del aviso -- eso exigiria 1
request HTTP extra POR resultado a la pagina de detalle (mas lento, mas
carga para el sitio). Se clasifica solo con el titulo; ver
core/classifier.py, que ya soporta descripcion vacia.
"""
import re
import time

import requests
from bs4 import BeautifulSoup

from core.sources.models import oferta_vacia

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
BASE_URL = "https://ar.computrabajo.com"
PAUSA_ENTRE_PAGINAS = 1.0

_RATING = re.compile(r"^\s*\d([.,]\d)?\s*$")


def _ubicacion_valida(texto):
    """Descarta texto tipo "4,2" (rating de empresa mal capturado como
    ubicacion) o strings demasiado cortos para ser una ubicacion real."""
    if not texto:
        return ""
    t = texto.strip()
    if _RATING.match(t):
        return ""
    if len(t) < 3:
        return ""
    return t


def _parse_tarjeta(art, query):
    """El <a> del titulo tambien lleva la clase 'fc_base' (igual que el
    <a> de la empresa), y el parrafo de rating/empresa tambien matchea
    'fs16.fc_base.mt5' (tiene esas 3 clases MAS 'dFlex') -- por eso los
    selectores de empresa/ubicacion excluyen explicitamente ese parrafo
    (via 'p.dFlex a' / clase 'dFlex') en vez de usar 'a.fc_base' o
    'p.fs16.fc_base.mt5' sueltos, que matchean el elemento equivocado
    primero (orden de documento) y devuelven el titulo duplicado como
    empresa, o el rating como ubicacion."""
    titulo_tag = art.select_one("a.js-o-link")
    if not titulo_tag:
        return None
    titulo = titulo_tag.get_text(strip=True)

    ubicacion = ""
    for p in art.select("p.fs16.fc_base.mt5"):
        if "dFlex" in (p.get("class") or []):
            continue  # parrafo de empresa/rating, no de ubicacion
        cand = _ubicacion_valida(p.get_text(" ", strip=True))
        if cand:
            ubicacion = cand
            break

    empresa_tag = art.select_one("a[offer-grid-article-company-url]") or art.select_one("p.dFlex a")

    # El mismo bloque "fs13 mt15 / dIB" tambien se usa para el badge de
    # salario en algunos avisos (ej. "$ 10.000,00 (Mensual)") -- se
    # descarta si el texto no parece una modalidad real, para no meter
    # un salario en la columna equivocada.
    modalidad = ""
    for tag in art.select("div.fs13.mt15 span.dIB"):
        texto = tag.get_text(strip=True)
        if any(kw in texto.lower() for kw in ("presencial", "remoto", "remote", "híbrido", "hibrido", "home office")):
            modalidad = texto
            break

    fecha = ""
    for tag in art.find_all(["p", "span"]):
        t = tag.get_text(" ", strip=True)
        if t.lower().startswith("hace ") or t.lower() in ("ayer", "hoy"):
            fecha = t
            break

    return oferta_vacia(
        titulo=titulo,
        empresa=empresa_tag.get_text(strip=True) if empresa_tag else "",
        modalidad=modalidad,
        fuente="Computrabajo",
        ubicacion=ubicacion,
        fecha=fecha,
        link=BASE_URL + titulo_tag.get("href", ""),
        busqueda=query,
    )


def buscar(query, dias=2, ciudad="", max_paginas=3, max_resultados=20, **_kwargs):
    """Busca 'query' en Computrabajo.

    dias: antiguedad maxima del aviso (parametro 'pubdate' del sitio).
    ciudad: slug de ciudad para la URL, ej. "capital-federal" ("" = todo
      el pais -- default a proposito, para que "Toda Argentina" en la UI
      realmente busque en todo el pais y no solo en Capital Federal).
    max_paginas: tope de SEGURIDAD (no de resultados esperados) -- corta
      solo si el sitio devuelve pagina vacia o repetida, evita loop
      infinito si algo falla.
    max_resultados: tope final de ofertas devueltas.

    Nunca lanza si el sitio bloquea o falla la red -- devuelve lo que
    haya juntado hasta ese punto (lista vacia si nada funciono), con un
    aviso impreso a consola.
    """
    resultados = []
    ciudad_url = f"-en-{ciudad}" if ciudad else ""
    url = f"{BASE_URL}/trabajo-de-{query.strip().lower().replace(' ', '-')}{ciudad_url}"

    firmas_vistas = set()
    for pagina in range(1, max_paginas + 1):
        if len(resultados) >= max_resultados:
            break

        params = {}
        if dias:
            params["pubdate"] = dias
        if pagina > 1:
            params["p"] = pagina

        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
        except requests.RequestException as e:
            print(f"[Computrabajo] error de red en página {pagina}: {e}")
            break

        if r.status_code == 403:
            print(f"[Computrabajo] página {pagina}: 403 (bloqueo) -- corto la búsqueda")
            break
        if r.status_code != 200:
            print(f"[Computrabajo] página {pagina}: status {r.status_code} -- corto la búsqueda")
            break

        soup = BeautifulSoup(r.text, "html.parser")
        tarjetas = soup.select("article.box_offer")
        if not tarjetas:
            break

        firma = tuple(
            t.select_one("a.js-o-link").get_text(strip=True)
            for t in tarjetas if t.select_one("a.js-o-link")
        )
        if firma in firmas_vistas:
            break
        firmas_vistas.add(firma)

        for art in tarjetas:
            fila = _parse_tarjeta(art, query)
            if fila:
                resultados.append(fila)
            if len(resultados) >= max_resultados:
                break

        time.sleep(PAUSA_ENTRE_PAGINAS)

    return resultados[:max_resultados]
