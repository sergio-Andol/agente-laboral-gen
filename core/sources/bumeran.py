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

# Bumeran NO acepta cualquier antiguedad en la URL "empleos-publicacion-
# menor-a-N-dias.html" -- son buckets fijos que arma el propio sitio.
# Confirmado en vivo (2026): N en (2,3,4,5,6,7,15) devuelve avisos reales;
# cualquier otro valor (1, 8-14, 16+, incluido 30 -- el tope del slider de
# dias de la UI) responde 200 OK pero con 0 avisos, como si no hubiera
# resultados, aunque los haya. Sin este ajuste, elegir "30 dias" en la UI
# (un valor perfectamente valido para Computrabajo) garantiza 0 crudas de
# Bumeran pase lo que pase con la query.
_DIAS_SOPORTADOS = (2, 3, 4, 5, 6, 7, 15)


def _dias_soportado(dias):
    """Ajusta 'dias' al bucket soportado mas cercano POR ARRIBA (mas
    amplio, nunca mas angosto que lo pedido) -- si se pide mas de 15 (el
    maximo soportado), se usa 15 en vez de devolver 0 resultados por un
    valor que Bumeran no reconoce."""
    if dias in _DIAS_SOPORTADOS:
        return dias
    for candidato in _DIAS_SOPORTADOS:
        if candidato >= dias:
            return candidato
    return _DIAS_SOPORTADOS[-1]


_PW = {"play": None, "browser": None, "page": None}

# Avisos de diagnostico (bloqueo, estructura distinta, parseo fallido)
# acumulados durante buscar() -- core.real_search los lee con
# tomar_avisos() despues de cada llamada y los muestra en la UI, para no
# confundir "0 avisos reales" con "Bumeran esta bloqueando o cambio de
# estructura" (ver regla 8 del pedido que agrego esto).
_AVISOS_PENDIENTES = []


def tomar_avisos():
    """Devuelve y vacia los avisos acumulados desde la ultima llamada."""
    avisos = list(_AVISOS_PENDIENTES)
    _AVISOS_PENDIENTES.clear()
    return avisos


# Frases que SI esperamos ver en una pagina de listado real de Bumeran
# (haya o no resultados) -- si ninguna aparece, la pagina no tiene la
# forma esperada: cambio de estructura del sitio, o un bloqueo silencioso
# (sin las palabras de _BLOQUEO_KW) que devuelve una pagina distinta.
_MARCADORES_LISTADO = ("ofertas de empleo", "no encontramos")

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
    listado, con el fallback global por fecha como segundo intento) --
    queda documentado como limitacion conocida, no usado hoy."""
    page = _get_page()  # puede lanzar BumeranNoDisponible, sin atrapar aca

    filas = []
    try:
        from urllib.parse import quote
        slug = quote(query.strip().lower().replace(" ", "-"))
        dias_valido = _dias_soportado(dias) if dias else dias
        if dias_valido and dias_valido != dias:
            print(f"[Bumeran] días={dias} no es un bucket soportado por el sitio -- se usa {dias_valido}")

        if dias_valido:
            url = f"{BASE_URL}/empleos-publicacion-menor-a-{dias_valido}-dias-busqueda-{slug}.html"
        else:
            url = f"{BASE_URL}/empleos-busqueda-{slug}.html"

        tarjetas, cuerpo = _cargar_listado(page, url)
        if _detectar_bloqueo(cuerpo):
            print("[Bumeran] bloqueo detectado (captcha/cloudflare) -- se corta esta búsqueda")
            _AVISOS_PENDIENTES.append(
                "Bumeran parece bloquear la búsqueda (captcha/verificación detectada)."
            )
            return filas

        filtrar_localmente = False
        if not tarjetas and dias_valido:
            # A proposito SIN zona: "empleos-en-{zona}-publicacion-menor-
            # a-N-dias.html" (en cualquier orden) devuelve 0 avisos en el
            # sitio actual aunque responda 200 OK -- confirmado en vivo.
            # El fallback global (sin zona) SI funciona; Bumeran no
            # soporta scope de ciudad en esta implementacion de todas
            # formas (ver docstring del modulo).
            url_fallback = f"{BASE_URL}/empleos-publicacion-menor-a-{dias_valido}-dias.html"
            tarjetas, cuerpo = _cargar_listado(page, url_fallback)
            filtrar_localmente = True
            if _detectar_bloqueo(cuerpo):
                print("[Bumeran] bloqueo detectado en fallback -- se corta esta búsqueda")
                _AVISOS_PENDIENTES.append(
                    "Bumeran parece bloquear la búsqueda (captcha/verificación detectada)."
                )
                return filas

        if not tarjetas:
            # 0 tarjetas y sin palabras de bloqueo explicitas: puede ser
            # (a) genuinamente 0 avisos en esa ventana de dias, o (b) el
            # sitio devolvio una pagina con otra forma (bloqueo silencioso
            # o cambio de estructura) que no tiene ninguno de los
            # marcadores de una pagina de listado real. Se distingue para
            # no confundir "0 resultados reales" con "no se pudo leer".
            if cuerpo and not any(m in cuerpo.lower() for m in _MARCADORES_LISTADO):
                _AVISOS_PENDIENTES.append(
                    "Bumeran respondió con una página inesperada (posible bloqueo silencioso "
                    "o cambio de estructura del sitio) -- no se pudo confirmar si hay resultados."
                )
            return filas

        filas = _extraer_candidatos(tarjetas, query, filtrar_localmente, max_resultados)
        if tarjetas and not filas:
            _AVISOS_PENDIENTES.append(
                "Bumeran respondió con avisos, pero no se pudieron leer los resultados "
                "(posible cambio de estructura del sitio)."
            )
    except Exception as e:
        print(f"[Bumeran] error inesperado: {e}")
        _AVISOS_PENDIENTES.append(f"Bumeran: error inesperado buscando '{query}': {e}")
    return filas
