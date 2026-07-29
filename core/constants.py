"""Constantes de clasificacion: categorias/keywords genericas, columnas y
estado de seguridad de postulacion. Nada de esto es especifico de un
usuario -- es taxonomia general de rubros IT/Data junior.
"""

# Categoria -> frases que la identifican en un titulo/descripcion. Frases
# especificas a proposito (no palabras sueltas demasiado genericas como
# "datos" o "tecnico"), para no categorizar mal ofertas de otros rubros.
CATEGORIAS_KEYWORDS = {
    "Data / BI": [
        "analista de datos", "análisis de datos", "analisis de datos",
        "data analyst", "business intelligence", "power bi", "bi",
        "sql", "dashboard", "dashboards", "base de datos",
        "bases de datos", "analytics", "data visualization",
        "visualización de datos", "visualizacion de datos", "etl",
        "python para datos", "reporting", "kpi",
    ],
    "Soporte IT": [
        "soporte it", "soporte técnico", "soporte tecnico", "mesa de ayuda",
        "help desk", "helpdesk", "service desk", "técnico en sistemas",
        "tecnico en sistemas", "incidentes", "tickets", "redes",
        "hardware", "software",
    ],
    "QA / Testing": [
        "qa", "tester", "testing", "quality assurance",
        "casos de prueba", "test cases", "automatización de pruebas",
        "automatizacion de pruebas", "selenium", "jira",
    ],
    "Desarrollo": [
        "desarrollador", "developer", "programador", "frontend",
        "backend", "full stack", "javascript", "html", "css",
        "react", "node", "python developer",
    ],
    "Analista Funcional": [
        "analista funcional", "functional analyst", "requerimientos",
        "user stories", "historias de usuario", "backlog",
        "documentación funcional", "documentacion funcional",
        "uat", "procesos",
    ],
    "Supply Chain": [
        "supply chain", "abastecimiento", "compras", "inventario",
        "logística", "logistica", "planificación", "planificacion",
        "planeamiento", "planner", "almacén", "almacen",
        "deposito", "depósito",
    ],
    "Administrativo / Procesos": [
        "administrativo", "administración", "administracion",
        "asistente administrativo", "carga de datos",
        "excel", "procesos", "facturación", "facturacion",
        "documentación", "documentacion",
        "coordinación administrativa", "coordinacion administrativa",
    ],
    "Técnico / Producción": [
        "mecánico", "mecanico", "mantenimiento", "producción", "produccion",
        "operario", "electromecánico", "electromecanico", "industrial",
    ],
}

CATEGORIA_OTRO = "Otro"
CATEGORIA_AMBIGUO = "Ambiguo"

COLUMNAS = ["titulo", "empresa", "ubicacion", "modalidad", "fecha", "link", "busqueda", "fuente"]

ORDEN_DECISION = {"POSTULAR": 0, "REVISAR": 1, "DESCARTAR": 2}

# Estado de seguridad mostrado en la UI. Agente Laboral Gen no tiene NINGUNA
# capa de postulacion real (a diferencia de un agente personal que sí
# podria tenerla) -- estos valores son fijos, no interruptores que alguien
# pueda prender.
DRY_RUN_POSTULACION = True
MODO_POSTULACION = "OFF"
MAX_POSTULACIONES_POR_CORRIDA = 0
PROBAR_POSTULACION_EN_TEST = False
