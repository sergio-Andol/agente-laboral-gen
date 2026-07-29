"""Clasificacion simple y generica de ofertas de trabajo.

Reglas basicas por keyword/regex, sin ajuste fino de ningun perfil
personal (a diferencia de un motor de agente personal, que puede tener
docenas de listas de veto/rescate afinadas con el tiempo). Pensado para
mostrar el concepto -- categoria + decision + accion sugerida -- de forma
transparente y facil de leer.
"""
import re

from core.constants import CATEGORIA_AMBIGUO, CATEGORIA_OTRO, CATEGORIAS_KEYWORDS

# senior/semi senior/ssr/sr, con limite de palabra para no matchear
# substrings de otras palabras.
_PATRON_SENIORITY_ALTA = re.compile(
    r"\bsemi[-\s]?senior\b|\bsemi\s+s?sr\.?\b|\bsenior\b|\bs?sr\.?\b"
)


def detectar_categoria(texto):
    """Devuelve (categoria, cantidad_de_keywords_matcheadas). Si 2+
    categorias empatan en el maximo, devuelve CATEGORIA_AMBIGUO -- un
    empate real no tiene una unica respuesta correcta. Sin matches,
    CATEGORIA_OTRO."""
    texto = (texto or "").lower()
    scores = {}
    for categoria, keywords in CATEGORIAS_KEYWORDS.items():
        cantidad = sum(1 for kw in keywords if kw in texto)
        if cantidad:
            scores[categoria] = cantidad

    if not scores:
        return CATEGORIA_OTRO, 0

    mejor = max(scores.values())
    empatadas = [c for c, v in scores.items() if v == mejor]
    if len(empatadas) > 1:
        return CATEGORIA_AMBIGUO, mejor
    return empatadas[0], mejor


def clasificar_decision(titulo, descripcion=""):
    """Devuelve (decision_sugerida, motivo). Reglas, en orden:
    1) seniority alta detectada -> DESCARTAR (esta herramienta apunta a
       roles junior/trainee/semi senior).
    2) sin categoria clara (Otro/Ambiguo) -> DESCARTAR.
    3) categoria clara con 2+ señales -> POSTULAR.
    4) categoria clara con 1 señal -> REVISAR (señal debil, ojo humano)."""
    texto = f"{titulo or ''} {descripcion or ''}".lower()

    if _PATRON_SENIORITY_ALTA.search(texto):
        return "DESCARTAR", "Seniority alta (senior/semi senior/ssr) detectada."

    categoria, cantidad = detectar_categoria(texto)
    if categoria in (CATEGORIA_OTRO, CATEGORIA_AMBIGUO):
        return "DESCARTAR", "No matchea ninguna categoría conocida con claridad."
    if cantidad >= 2:
        return "POSTULAR", f"{cantidad} señales de '{categoria}' en título/descripción."
    return "REVISAR", f"Solo 1 señal de '{categoria}' -- revisar manualmente."


_ACCION_POR_DECISION = {
    "POSTULAR": "POSTULAR HOY",
    "REVISAR": "REVISAR MANUALMENTE",
    "DESCARTAR": "NO ACCIONAR",
}


def determinar_accion_sugerida(decision):
    """Mapeo directo decision -> accion. Simplificado a proposito: sin la
    distincion fina por alertas graves/seniority que tendria un motor mas
    grande -- por eso 'REVISAR ANTES DE POSTULAR' no se usa aca, queda en
    0 en el conteo (no es un bug, es la version simple)."""
    return _ACCION_POR_DECISION.get(decision, "NO ACCIONAR")


def construir_acciones(nuevas):
    """DataFrame de acciones (solo POSTULAR/REVISAR) + conteo por tipo,
    con las 4 etiquetas fijas para que la UI siempre tenga las 4 metricas
    aunque alguna de 0."""
    conteo_base = {
        "POSTULAR HOY": 0, "REVISAR ANTES DE POSTULAR": 0,
        "REVISAR MANUALMENTE": 0, "NO ACCIONAR": 0,
    }
    acciones = nuevas[nuevas["decision_sugerida"].isin(["POSTULAR", "REVISAR"])].copy()
    if acciones.empty:
        return acciones, conteo_base

    conteo = conteo_base.copy()
    conteo.update(acciones["accion_sugerida"].value_counts().to_dict())
    return acciones, conteo
