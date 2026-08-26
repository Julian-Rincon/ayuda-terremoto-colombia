"""
Los 33 departamentos de Colombia (32 departamentos + Bogotá D.C.), con
coordenadas de referencia (capital departamental) para el mapa nacional y
para poder activar automáticamente un centro de coordinación en cualquier
zona del país cuando haga falta — no solo en las 4 que hoy tienen actividad
real confirmada.

Los slugs de "risaralda-pereira" y "valle" coinciden a propósito con los
centros ya sembrados a mano en seed_data.py (con datos reales confirmados
en medios), para que sembrar este listado completo nunca duplique esas dos
zonas. geocoding.py usa este mismo listado para reconocer el departamento
que devuelve Nominatim y mapearlo al centro correcto.
"""

DEPARTAMENTOS_COLOMBIA = [
    {"nombre": "Amazonas", "id_territorio": "amazonas", "lat": -4.2153, "lon": -69.9406},
    {"nombre": "Antioquia", "id_territorio": "antioquia", "lat": 6.2442, "lon": -75.5812},
    {"nombre": "Arauca", "id_territorio": "arauca", "lat": 7.0847, "lon": -70.7591},
    {"nombre": "Atlántico", "id_territorio": "atlantico", "lat": 10.9639, "lon": -74.7964},
    {"nombre": "Bogotá D.C.", "id_territorio": "bogota-dc", "lat": 4.7110, "lon": -74.0721},
    {"nombre": "Bolívar", "id_territorio": "bolivar", "lat": 10.3910, "lon": -75.4794},
    {"nombre": "Boyacá", "id_territorio": "boyaca", "lat": 5.5353, "lon": -73.3678},
    {"nombre": "Caldas", "id_territorio": "caldas", "lat": 5.0703, "lon": -75.5138},
    {"nombre": "Caquetá", "id_territorio": "caqueta", "lat": 1.6144, "lon": -75.6062},
    {"nombre": "Casanare", "id_territorio": "casanare", "lat": 5.3378, "lon": -72.3959},
    {"nombre": "Cauca", "id_territorio": "cauca", "lat": 2.4448, "lon": -76.6147},
    {"nombre": "Cesar", "id_territorio": "cesar", "lat": 10.4631, "lon": -73.2532},
    {"nombre": "Chocó", "id_territorio": "choco", "lat": 5.6947, "lon": -76.6611},
    {"nombre": "Córdoba", "id_territorio": "cordoba", "lat": 8.7479, "lon": -75.8814},
    {"nombre": "Cundinamarca", "id_territorio": "cundinamarca", "lat": 4.7110, "lon": -74.0721},
    {"nombre": "Guainía", "id_territorio": "guainia", "lat": 3.8653, "lon": -67.9239},
    {"nombre": "Guaviare", "id_territorio": "guaviare", "lat": 2.5709, "lon": -72.6413},
    {"nombre": "Huila", "id_territorio": "huila", "lat": 2.9273, "lon": -75.2819},
    {"nombre": "La Guajira", "id_territorio": "la-guajira", "lat": 11.5444, "lon": -72.9072},
    {"nombre": "Magdalena", "id_territorio": "magdalena", "lat": 11.2408, "lon": -74.1990},
    {"nombre": "Meta", "id_territorio": "meta", "lat": 4.1420, "lon": -73.6266},
    {"nombre": "Nariño", "id_territorio": "narino", "lat": 1.2136, "lon": -77.2811},
    {"nombre": "Norte de Santander", "id_territorio": "norte-de-santander", "lat": 7.8939, "lon": -72.5078},
    {"nombre": "Putumayo", "id_territorio": "putumayo", "lat": 1.1487, "lon": -76.6478},
    {"nombre": "Quindío", "id_territorio": "quindio", "lat": 4.5339, "lon": -75.6811},
    {"nombre": "Risaralda", "id_territorio": "risaralda-pereira", "lat": 4.8133, "lon": -75.6961},
    {"nombre": "San Andrés y Providencia", "id_territorio": "san-andres-y-providencia", "lat": 12.5847, "lon": -81.7006},
    {"nombre": "Santander", "id_territorio": "santander", "lat": 7.1193, "lon": -73.1227},
    {"nombre": "Sucre", "id_territorio": "sucre", "lat": 9.3047, "lon": -75.3978},
    {"nombre": "Tolima", "id_territorio": "tolima", "lat": 4.4389, "lon": -75.2322},
    {"nombre": "Valle del Cauca", "id_territorio": "valle", "lat": 3.4516, "lon": -76.5320},
    {"nombre": "Vaupés", "id_territorio": "vaupes", "lat": 1.1983, "lon": -70.2331},
    {"nombre": "Vichada", "id_territorio": "vichada", "lat": 6.1891, "lon": -67.4859},
]

assert len(DEPARTAMENTOS_COLOMBIA) == 33
