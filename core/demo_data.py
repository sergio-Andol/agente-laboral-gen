"""6 ofertas simuladas para el modo DEMO -- genericas, sin datos de ningun
usuario real. Empresas y links son ficticios (dominio demo.local)."""

DATOS_DEMO = [
    {
        "titulo": "Analista de Datos Junior", "empresa": "Demo Analytics",
        "ubicacion": "CABA", "modalidad": "Híbrido", "fecha": "Publicado hoy",
        "link": "https://demo.local/ofertas/analista-de-datos-junior",
        "busqueda": "analista de datos", "fuente": "Demo",
        "descripcion_demo": (
            "Buscamos Analista de Datos Junior para el equipo de Business "
            "Intelligence. Requisitos: SQL, Power BI y armado de dashboards. "
            "Perfil junior, con ganas de aprender."
        ),
    },
    {
        "titulo": "Soporte IT Junior", "empresa": "Demo IT Services",
        "ubicacion": "Buenos Aires", "modalidad": "Presencial", "fecha": "Publicado ayer",
        "link": "https://demo.local/ofertas/soporte-it-junior",
        "busqueda": "soporte it", "fuente": "Demo",
        "descripcion_demo": (
            "Analista de Soporte IT / Mesa de Ayuda para gestión de tickets "
            "e incidentes de hardware y software. Perfil junior."
        ),
    },
    {
        "titulo": "Analista Funcional", "empresa": "Demo Software Factory",
        "ubicacion": "CABA", "modalidad": "Remoto", "fecha": "Publicado hace 2 días",
        "link": "https://demo.local/ofertas/analista-funcional",
        "busqueda": "analista funcional", "fuente": "Demo",
        "descripcion_demo": (
            "Analista Funcional para participar en proyectos de sistemas "
            "junto al equipo de negocio. Se valora buena comunicación."
        ),
    },
    {
        "titulo": "Analista de Supply Chain", "empresa": "Demo Logística",
        "ubicacion": "GBA", "modalidad": "Presencial", "fecha": "Publicado hace 1 día",
        "link": "https://demo.local/ofertas/analista-de-supply-chain",
        "busqueda": "supply chain", "fuente": "Demo",
        "descripcion_demo": (
            "Analista de Supply Chain para coordinar operaciones junto al "
            "área comercial. Buen manejo de herramientas de oficina."
        ),
    },
    {
        "titulo": "Data Engineer Senior", "empresa": "Demo Tech Senior",
        "ubicacion": "CABA", "modalidad": "Híbrido", "fecha": "Publicado hoy",
        "link": "https://demo.local/ofertas/data-engineer-senior",
        "busqueda": "data engineer", "fuente": "Demo",
        "descripcion_demo": (
            "Data Engineer Senior con más de 5 años de experiencia en "
            "arquitectura de datos cloud (AWS/GCP) y pipelines a gran escala."
        ),
    },
    {
        "titulo": "Vendedor Telefónico Call Center", "empresa": "Demo Ventas",
        "ubicacion": "CABA", "modalidad": "Presencial", "fecha": "Publicado hoy",
        "link": "https://demo.local/ofertas/vendedor-call-center",
        "busqueda": "vendedor call center", "fuente": "Demo",
        "descripcion_demo": (
            "Se buscan vendedores telefónicos para call center de venta de "
            "productos. No se requiere experiencia previa."
        ),
    },
]


def generar_datos_demo():
    """Copia defensiva -- el llamador puede mutar el resultado sin afectar
    la lista original."""
    return [dict(fila) for fila in DATOS_DEMO]
