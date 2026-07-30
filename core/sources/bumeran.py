"""Busqueda real de ofertas en Bumeran (Argentina) -- OPCIONAL, requiere
Playwright (un navegador Chromium real).

A diferencia de Computrabajo, Bumeran no expone un listado estatico
scrapeable con requests/BeautifulSoup (el contenido hidrata con React) --
no hay forma de leerlo sin un navegador real. Este modulo lanza
BumeranNoDisponible con un mensaje ya listo para la UI si Playwright no
esta instalado o no se pudo lanzar Chromium (falta el binario); esa
excepcion NUNCA se atrapa aca a proposito, para que
core.real_search.buscar_ofertas_reales() la detecte, avise, y siga
igual con las demas fuentes -- no debe romper toda la busqueda.

A proposito NO implementa la verificacion de "postulacion externa"
(visitar el detalle de cada aviso para ver si redirige a ZonaJobs, etc.)
que si tiene el scraper del proyecto personal -- eso agrega 1 carga de
pagina extra POR candidato (mucho mas lento) y roza logica de
postulacion, que este proyecto generico no quiere. Consecuencia
aceptada: algunos avisos con postulacion externa pueden colarse.

Logica de busqueda (igual idea que el proyecto personal, sin la
verificacion externa):
  1) URL combinada palabra clave + antiguedad
     (empleos-publicacion-menor-a-N-dias-busqueda-{slug}.html).
  2) Si esa da 0 tarjetas, cae a la pagina de zona+fecha (Buenos Aires,
     sin keyword) y filtra localmente por la query en el texto de cada
     tarjeta (titulo+empresa) -- Bumeran no siempre tiene el bucket
     combinado para busquedas de nicho.
"""
import re
import time

from core.sources.models import oferta_vacia

PAUSA_ENTRE_CARGAS = 1.5  # segundos, tras cargar cada pagina de listado
BASE_URL = "https://www.bumeran.com.ar"

_PW = {"play": None, "browser": None, "page": None}

_MENSAJE_INSTALAR = (
    "Bumeran requiere Playwright. Instalalo con: "
    "py -3.14 -m playwright install chromium "
    "(si playwright no está instalado todavía, antes: pip install playwright)."
)


class BumeranNoDisponible(Exception):
    """Playwright no esta instalado, o no se pudo lanzar Chromium (falta
    el binario). El mensaje del error ya viene listo para mostrar en la
    UI tal cual -- ver _MENSAJE_INSTALAR."""


def _get_page():
    """Abre el navegador la primera vez y reusa la misma pagina en
    llamadas siguientes (una por proceso). Lanza BumeranNoDisponible sin
    atraparla -- es responsabilidad del llamador decidir que hacer."""
    if _PW["page"] is not None:
        return _PW["page"]

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise BumeranNoDisponible(_MENSAJE_INSTALAR) from e

    try:
        _PW["play"] = sync_playwright().start()
        _PW["browser"] = _PW["play"].chromium.launch(headless=True)
        ctx = _PW["browser"].new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"),
            locale="es-AR",
        )
        _PW["page"] = ctx.new_page()
    except Exception as e:
        cerrar_navegador()
        raise BumeranNoDisponible(_MENSAJE_INSTALAR) from e

    return _PW["page"]


def cerrar_navegador():
    """Cierra el navegador si se llego a abrir. Seguro de llamar aunque
    nunca se haya usado Bumeran (no hace nada en ese caso)."""
    try:
        if _PW["browser"]:
            _PW["browser"].close()
        if _PW["play"]:
            _PW["play"].stop()
    except Exception:
        pass
    _PW["page"] = _PW["browser"] = _PW["play"] = None


# "a[href*='/empleos/']" es el mas estable: depende de la URL, no de una
# clase (Bumeran usa clases hasheadas de styled-components que cambian
# seguido).
_SELECTORES_TARJETA = [
    "a[href*='/empleos/']",
    "article a[href*='empleo']",
    "div[id^='listado'] a[href]",
]
_MODALIDADES_CONOCIDAS = {"presencial", "remoto", "hibrido", "híbrido", "mixto"}
_BLOQUEO_KW = ("captcha", "cloudflare", "robot", "acceso denegado",
               "verifica que sos humano", "unusual traffic")
_RATING = re.compile(r"^\s*\d([.,]\d)?\s*$")


def _ubicacion_valida(texto):
    if not texto:
        return ""
    t = texto.strip()
    if _RATING.match(t) or len(t) < 3:
        return ""
    return t


def _clasificar_h3(textos):
    """Los <h3> de una tarjeta traen, en orden variable: fecha, empresa,
    (a veces) rating, ubicacion, modalidad. Se clasifican por contenido,
    no por posicion -- el orden/cantidad cambia segun si el aviso tiene
    rating o no."""
    fecha = empresa = ubicacion = modalidad = ""
    resto = []
    for t in textos:
        tl = (t or "").strip()
        if not tl:
            continue
        low = tl.lower()
        if low.startswith("actualizado") or low.startswith("publicado"):
            fecha = tl
        elif low in _MODALIDADES_CONOCIDAS:
            modalidad = tl
        elif _RATING.match(tl):
            continue
        elif "," in tl:
            ubicacion = _ubicacion_valida(tl)
        else:
            resto.append(tl)
    if resto and not empresa:
        empresa = resto[0]
    return fecha, empresa, ubicacion, modalidad


def _coincide_query_local(texto, query):
    """Usado solo en el fallback zona+fecha (sin keyword en la URL):
    exige que todas las palabras relevantes (>=3 letras) de la query
    esten en el texto de la tarjeta, en cualquier orden."""
    texto_low = texto.lower()
    q = query.lower().strip()
    if q in texto_low:
        return True
    palabras = [w for w in re.split(r"\s+", q) if len(w) >= 3]
    return bool(palabras) and all(w in texto_low for w in palabras)


def _detectar_bloqueo(cuerpo):
    cuerpo_low = (cuerpo or "").lower()
    return [kw for kw in _BLOQUEO_KW if kw in cuerpo_low]


def _cargar_listado(page, url):
    """Abre una URL de listado y devuelve (tarjetas, cuerpo_texto). No
    lanza: si algo falla devuelve listas/strings vacias."""
    try:
        page.goto(url, timeout=45000, wait_until="domcontentloaded")
        try:
            page.wait_for_selector(_SELECTORES_TARJETA[0], timeout=8000)
        except Exception:
            pass
        time.sleep(PAUSA_ENTRE_CARGAS)

        tarjetas = []
        for sel in _SELECTORES_TARJETA:
            try:
                candidatas = page.query_selector_all(sel)
            except Exception:
                candidatas = []
            if candidatas:
                tarjetas = candidatas
                break

        cuerpo = page.inner_text("body") or ""
        return tarjetas, cuerpo
    except Exception as e:
        print(f"[Bumeran] error cargando {url}: {e}")
        return [], ""


def _extraer_candidatos(tarjetas, query, filtrar_localmente, max_candidatos):
    candidatos = []
    vistos = set()
    for t in tarjetas[:max_candidatos * 2]:
        try:
            href = t.get_attribute("href") or ""
            if "/empleos/" not in href or href in vistos:
                continue
            vistos.add(href)

            texto_completo = t.inner_text()
            h2 = t.query_selector("h2")
            titulo = h2.inner_text().strip() if h2 else ""
            if not titulo:
                for linea in texto_completo.split("\n"):
                    linea = linea.strip()
                    if (linea and not linea.lower().startswith(("actualizado", "publicado"))
                            and not _RATING.match(linea)):
                        titulo = linea
                        break
            if not titulo or len(titulo) < 4:
                continue

            if filtrar_localmente and not _coincide_query_local(texto_completo, query):
                continue

            h3s = [h.inner_text() for h in t.query_selector_all("h3")]
            fecha, empresa, ubicacion, modalidad = _clasificar_h3(h3s)
            link = href if href.startswith("http") else (BASE_URL + href)

            candidatos.append(oferta_vacia(
                titulo=titulo, empresa=empresa, fuente="Bumeran",
                ubicacion=ubicacion, modalidad=modalidad, fecha=fecha,
                link=link, busqueda=query,
            ))
            if len(candidatos) >= max_candidatos:
                break
        except Exception:
            continue
    return candidatos


def buscar(query, dias=2, max_paginas=1, max_resultados=20, **_kwargs):
    """Busca 'query' en Bumeran. Lanza BumeranNoDisponible (sin
    atraparla) si Playwright/Chromium no estan disponibles -- el
    llamador (core.real_search) debe capturarla y avisar en la UI sin
    romper la busqueda completa. Cualquier otro error (bloqueo, timeout
    de red, selector roto) se atrapa aca y devuelve lo que se pudo
    juntar (lista vacia como minimo), igual que computrabajo.buscar().

    'max_paginas' se acepta por simetria con la firma de Computrabajo,
    pero Bumeran no pagina en esta implementacion (una sola carga de
    listado, con el fallback zona+fecha como segundo intento) -- queda
    documentado como limitacion conocida, no usado hoy."""
    page = _get_page()  # puede lanzar BumeranNoDisponible, sin atrapar aca

    filas = []
    try:
        from urllib.parse import quote
        slug = quote(query.strip().lower().replace(" ", "-"))

        if dias:
            url = f"{BASE_URL}/empleos-publicacion-menor-a-{dias}-dias-busqueda-{slug}.html"
        else:
            url = f"{BASE_URL}/empleos-busqueda-{slug}.html"

        tarjetas, cuerpo = _cargar_listado(page, url)
        if _detectar_bloqueo(cuerpo):
            print("[Bumeran] bloqueo detectado (captcha/cloudflare) -- se corta esta búsqueda")
            return filas

        filtrar_localmente = False
        if not tarjetas and dias:
            url_fallback = f"{BASE_URL}/en-buenos-aires/empleos-publicacion-menor-a-{dias}-dias.html"
            tarjetas, cuerpo = _cargar_listado(page, url_fallback)
            filtrar_localmente = True
            if _detectar_bloqueo(cuerpo):
                print("[Bumeran] bloqueo detectado en fallback -- se corta esta búsqueda")
                return filas

        if not tarjetas:
            return filas

        filas = _extraer_candidatos(tarjetas, query, filtrar_localmente, max_resultados)
    except Exception as e:
        print(f"[Bumeran] error inesperado: {e}")
    return filas
