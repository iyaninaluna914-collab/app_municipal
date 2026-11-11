
import streamlit as st
import pandas as pd
import sqlite3
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
from pathlib import Path
from datetime import datetime, date
import math
import re
import unicodedata

# =====================================================
# 1. CONFIGURACIÓN GENERAL
# =====================================================

st.set_page_config(
    page_title="Observatorio Vial Municipal 2.0",
    page_icon="🚦",
    layout="wide"
)

BASE_DIR = Path(__file__).parent
ARCHIVO_CSV = BASE_DIR / "df_final (1).csv"
BASE_DATOS = BASE_DIR / "observatorio.db"


# =====================================================
# 2. ESTILO VISUAL
# =====================================================

st.markdown("""
<style>

.stApp {
    background: linear-gradient(180deg, #F4F8FC 0%, #EDF3F8 100%);
}

h1, h2, h3 {
    color: #173B50;
}

/* BARRA LATERAL */

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #173B50 0%, #205D70 100%);
}

section[data-testid="stSidebar"] * {
    color: #FFFFFF;
}

/* MÉTRICAS */

div[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #DCE7EF;
    padding: 15px;
    border-radius: 14px;
    box-shadow: 0 3px 12px rgba(23, 59, 80, 0.05);
}

/* BOTONES */

div.stButton > button,
div.stDownloadButton > button {
    background: #176B78;
    color: white;
    border: 0;
    border-radius: 9px;
    padding: 9px 18px;
    font-weight: 600;
}

div.stButton > button:hover,
div.stDownloadButton > button:hover {
    background: #12515C;
    color: white;
}

/* INICIO */

.inicio-panel {
    background: linear-gradient(135deg, #FFFFFF 0%, #EAF3F8 100%);
    border: 1px solid #DCE8F0;
    border-radius: 22px;
    padding: 42px 40px;
    box-shadow: 0 8px 28px rgba(23, 59, 80, 0.07);
    margin: 18px 0 30px 0;
}

.inicio-etiqueta {
    display: inline-block;
    background: #DDEEF4;
    color: #176B78;
    font-size: 0.76rem;
    font-weight: 800;
    letter-spacing: 1.5px;
    padding: 8px 14px;
    border-radius: 30px;
    margin-bottom: 18px;
}

.inicio-titulo {
    color: #173B50;
    font-size: 2.8rem;
    font-weight: 800;
    margin-bottom: 16px;
    line-height: 1.2;
}

.inicio-texto {
    color: #40596A;
    font-size: 1.08rem;
    line-height: 1.8;
    max-width: 850px;
}

/* TARJETAS DE INICIO */

.paso-card {
    background: #FFFFFF;
    border: 1px solid #DCE7EF;
    border-radius: 17px;
    padding: 23px 20px;
    min-height: 175px;
    box-shadow: 0 4px 15px rgba(23, 59, 80, 0.045);
}

.paso-numero {
    color: #278092;
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 1.2px;
    margin-bottom: 12px;
}

.paso-titulo {
    color: #173B50;
    font-size: 1.05rem;
    font-weight: 750;
    margin: 8px 0;
}

.paso-texto {
    color: #526879;
    font-size: 0.91rem;
    line-height: 1.6;
}

</style>
""", unsafe_allow_html=True)


# =====================================================
# 3. BASE DE DATOS
# =====================================================

def conectar_db():

    return sqlite3.connect(
        BASE_DATOS,
        check_same_thread=False
    )


def crear_tabla():

    # No elimina ni reemplaza los registros existentes.
    with conectar_db() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS intervenciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zona TEXT NOT NULL,
                tipo_accion TEXT NOT NULL,
                descripcion TEXT,
                responsable TEXT,
                fecha_inspeccion TEXT,
                estado TEXT NOT NULL,
                observaciones TEXT,
                fecha_registro TEXT NOT NULL
            )
        """)

        conn.commit()


crear_tabla()


def obtener_intervenciones():

    with conectar_db() as conn:

        return pd.read_sql_query(
            "SELECT * FROM intervenciones ORDER BY id DESC",
            conn
        )


def guardar_intervencion(
    zona,
    tipo_accion,
    descripcion,
    responsable,
    fecha_inspeccion,
    estado,
    observaciones
):

    fecha_registro = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    with conectar_db() as conn:

        conn.execute("""
            INSERT INTO intervenciones (
                zona,
                tipo_accion,
                descripcion,
                responsable,
                fecha_inspeccion,
                estado,
                observaciones,
                fecha_registro
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            zona,
            tipo_accion,
            descripcion,
            responsable,
            fecha_inspeccion,
            estado,
            observaciones,
            fecha_registro
        ))

        conn.commit()


def actualizar_estado(id_intervencion, nuevo_estado):

    with conectar_db() as conn:

        conn.execute("""
            UPDATE intervenciones
            SET estado = ?
            WHERE id = ?
        """, (nuevo_estado, id_intervencion))

        conn.commit()


# =====================================================
# 4. CARGA Y PREPARACIÓN DE DATOS
# =====================================================

@st.cache_data
def cargar_datos():

    if not ARCHIVO_CSV.exists():

        return pd.DataFrame(), (
            f"No se encontró el archivo {ARCHIVO_CSV.name}. "
            "Colocalo en la misma carpeta que app.py."
        )

    datos = None

    requeridas = [
        "momento_exacto",
        "clasificacion_gravedad",
        "latitud",
        "longitud",
        "zona"
    ]

    # Prueba detección automática y separadores habituales.
    for separador in [None, ";", ",", "\t"]:

        try:

            if separador is None:

                candidato = pd.read_csv(
                    ARCHIVO_CSV,
                    encoding="utf-8-sig",
                    sep=None,
                    engine="python"
                )

            else:

                candidato = pd.read_csv(
                    ARCHIVO_CSV,
                    encoding="utf-8-sig",
                    sep=separador
                )

            candidato.columns = (
                candidato.columns.astype(str)
                .str.strip()
                .str.lower()
            )

            candidato = candidato.loc[
                :,
                ~candidato.columns.duplicated()
            ].copy()

            if all(
                col in candidato.columns
                for col in requeridas
            ):

                datos = candidato
                break

        except Exception:
            continue

    if datos is None:

        return pd.DataFrame(), (
            "No se encontraron todas las columnas necesarias: "
            "momento_exacto, clasificacion_gravedad, latitud, "
            "longitud y zona. Revisá los encabezados del CSV."
        )

    datos["momento_exacto"] = pd.to_datetime(
        datos["momento_exacto"],
        errors="coerce",
        dayfirst=True
    )

    datos["latitud"] = pd.to_numeric(
        datos["latitud"],
        errors="coerce"
    )

    datos["longitud"] = pd.to_numeric(
        datos["longitud"],
        errors="coerce"
    )

    for columna, valor in [
        ("zona", "SIN ZONA"),
        ("clasificacion_gravedad", "SIN CLASIFICAR"),
        ("tipo_colision", "SIN INFORMACIÓN"),
        ("direccion_completa", "SIN INFORMACIÓN"),
        ("via_publica", "SIN INFORMACIÓN"),
        ("tipo_via", "SIN INFORMACIÓN")
    ]:

        if columna not in datos.columns:

            datos[columna] = valor

        else:

            datos[columna] = (
                datos[columna]
                .fillna(valor)
                .astype(str)
                .str.strip()
            )

    return datos, None


df, error_datos = cargar_datos()

if error_datos:

    st.error(error_datos)
    st.stop()

if df.empty:

    st.error("El archivo no contiene registros para analizar.")
    st.stop()


# =====================================================
# 5. FUNCIONES AUXILIARES
# =====================================================

def normalizar(texto):

    texto = str(texto).lower().strip()

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    texto = "".join(
        c for c in texto
        if unicodedata.category(c) != "Mn"
    )

    return re.sub(r"\s+", " ", texto)


def coordenadas_validas(datos):

    return (
        datos["latitud"].between(-90, 90)
        & datos["longitud"].between(-180, 180)
        & datos["latitud"].notna()
        & datos["longitud"].notna()
    )


def distancia_metros(lat1, lon1, lat2, lon2):

    radio = 6371000

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)

    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1)
        * math.cos(p2)
        * math.sin(dl / 2) ** 2
    )

    return 2 * radio * math.asin(
        math.sqrt(a)
    )


# =====================================================
# 6. AGRUPACIÓN GEOGRÁFICA
# =====================================================

def crear_grupos_geograficos(
    datos,
    distancia=150
):

    puntos = datos.reset_index(drop=True).copy()

    cantidad = len(puntos)

    visitados = set()
    grupos = []

    for inicio in range(cantidad):

        if inicio in visitados:
            continue

        grupo = []
        pendientes = [inicio]

        visitados.add(inicio)

        while pendientes:

            actual = pendientes.pop()

            grupo.append(actual)

            lat_a = float(
                puntos.loc[actual, "latitud"]
            )

            lon_a = float(
                puntos.loc[actual, "longitud"]
            )

            for candidato in range(cantidad):

                if candidato in visitados:
                    continue

                lat_b = float(
                    puntos.loc[candidato, "latitud"]
                )

                lon_b = float(
                    puntos.loc[candidato, "longitud"]
                )

                distancia_actual = distancia_metros(
                    lat_a,
                    lon_a,
                    lat_b,
                    lon_b
                )

                if distancia_actual <= distancia:

                    visitados.add(candidato)
                    pendientes.append(candidato)

        grupos.append(grupo)

    resultado = []

    for numero, indices in enumerate(
        grupos,
        start=1
    ):

        grupo_df = puntos.iloc[indices].copy()

        moda_zona = grupo_df["zona"].mode()

        zona = (
            moda_zona.iloc[0]
            if not moda_zona.empty
            else "SIN ZONA"
        )

        resultado.append({

            "id": numero,

            "datos": grupo_df,

            "latitud": float(
                grupo_df["latitud"].mean()
            ),

            "longitud": float(
                grupo_df["longitud"].mean()
            ),

            "cantidad": len(grupo_df),

            "zona": zona

        })

    return resultado


# =====================================================
# 7. MOTOR DE RECOMENDACIONES
# =====================================================

def recomendar_infraestructura(datos_zona):

    tipos = (
        datos_zona["tipo_colision"]
        .astype(str)
        .str.strip()
    )

    tipos = tipos[
        ~tipos.map(normalizar).isin([
            "sin informacion",
            "",
            "nan",
            "none"
        ])
    ]

    if tipos.empty:

        return {

            "tipo": "Información insuficiente",

            "accion": (
                "Realizar un relevamiento técnico de seguridad vial"
            ),

            "motivo": (
                "No hay suficientes tipos de colisión informados "
                "para identificar un patrón predominante."
            ),

            "prioridad": "A determinar",

            "confianza": "No calculable",

            "cantidad_tipo": 0,

            "cantidad_informada": 0,

            "heridos": 0,

            "fallecidos": 0

        }

    conteo = tipos.value_counts()

    predominante = str(conteo.index[0])

    porcentaje = (
        conteo.iloc[0] / len(tipos) * 100
    )

    t = normalizar(predominante)

    if any(
        p in t
        for p in ["atropello", "peaton", "peatones"]
    ):

        accion = (
            "Evaluar cruces peatonales seguros, iluminación "
            "y señalización peatonal"
        )

        motivo = (
            "Predominan siniestros que involucran peatones. "
            "Se recomienda revisar cruces, visibilidad, iluminación "
            "y velocidades de aproximación."
        )

    elif any(
        p in t
        for p in ["lateral", "interseccion", "cruce"]
    ):

        accion = (
            "Evaluar el diseño del cruce y la necesidad de semaforización"
        )

        motivo = (
            "Predominan colisiones laterales o asociadas a cruces. "
            "Se deben estudiar prioridades de paso, visibilidad "
            "y conflictos de giro."
        )

    elif any(
        p in t
        for p in ["alcance", "trasera"]
    ):

        accion = (
            "Evaluar control de velocidad, señalización preventiva "
            "y distancia de detención"
        )

        motivo = (
            "Predominan choques por alcance. Conviene revisar "
            "velocidades, frenadas, señalización y circulación."
        )

    elif any(
        p in t
        for p in ["vuelco", "despiste", "salida de calzada"]
    ):

        accion = (
            "Evaluar delineadores, señalización de curvas y defensas viales"
        )

        motivo = (
            "Se observan siniestros compatibles con pérdida de control "
            "o salida de calzada. La solución depende de la geometría, "
            "velocidad y obstáculos laterales."
        )

    elif "frontal" in t:

        accion = (
            "Evaluar demarcación, señalización y separación de sentidos"
        )

        motivo = (
            "Predominan colisiones frontales. Se debe revisar la "
            "separación de flujos, adelantamientos, demarcación y visibilidad."
        )

    elif any(
        p in t
        for p in ["moto", "motocicleta"]
    ):

        accion = (
            "Evaluar señalización, estado de calzada y condiciones "
            "de circulación"
        )

        motivo = (
            "Los registros predominantes involucran motocicletas. "
            "Se recomienda revisar calzada, visibilidad y señalización."
        )

    else:

        accion = (
            "Realizar inspección de seguridad vial en el sector"
        )

        motivo = (
            "El tipo predominante no permite asignar una infraestructura "
            "específica mediante estas reglas. Se recomienda inspección técnica."
        )

    # CORRECCIÓN: reconocer las categorías reales del CSV.
    gravedad = (
        datos_zona["clasificacion_gravedad"]
        .astype(str)
        .map(normalizar)
    )

    fallecidos = int(
        (gravedad == "fatal").sum()
    )

    heridos = int(
        (gravedad == "con heridos").sum()
    )

    if fallecidos > 0:

        prioridad = (
            "Alta: existen registros clasificados con fallecidos."
        )

    elif heridos > 0:

        prioridad = (
            "Revisión prioritaria: existen registros con heridos."
        )

    else:

        prioridad = (
            "A evaluar según inspección y contexto vial."
        )

    return {

        "tipo": predominante,

        "accion": accion,

        "motivo": motivo,

        "prioridad": prioridad,

        "confianza": (
            f"{porcentaje:.1f}% de los tipos informados en el grupo."
        ),

        "cantidad_tipo": int(conteo.iloc[0]),

        "cantidad_informada": int(len(tipos)),

        "heridos": heridos,

        "fallecidos": fallecidos

    }


# =====================================================
# 8. MENÚ PRINCIPAL
# =====================================================

st.sidebar.markdown("## 🚦 OBSERVATORIO VIAL")
st.sidebar.caption("Municipal 2.0")

opcion = st.sidebar.radio(
    "NAVEGACIÓN",
    [
        "Inicio",
        "Mapa territorial",
        "Registrar acción preventiva",
        "Seguimiento de acciones",
        "Calidad de datos",
        "Informe y exportación"
    ]
)

st.sidebar.divider()

st.sidebar.caption(
    "Prototipo académico — PP3"
)


# =====================================================
# 9. INICIO CORREGIDO SIN HTML
# =====================================================

if opcion == "Inicio":

    st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(
            180deg,
            #F4F8FC 0%,
            #EDF3F8 100%
        );
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("## OBSERVATORIO VIAL MUNICIPAL 2.0")

    st.title("¡Bienvenido/a!")

    st.write(
        "Al ingresar a la aplicación podrás explorar la información "
        "de los accidentes viales mediante el mapa interactivo. "
        "Podrás consultar los registros, identificar sectores críticos "
        "y analizar los resultados que se muestran en el mapa y los gráficos."
    )

    st.divider()

    st.subheader("¿Cómo comenzar?")

    c1, c2, c3 = st.columns(3, gap="medium")

    with c1:
        with st.container(border=True):
            st.markdown("## 🗺️")
            st.caption("PASO 01")
            st.markdown("### Explorá el mapa")
            st.write(
                "Observá la distribución geográfica de los accidentes "
                "y las concentraciones que aparecen señaladas."
            )

    with c2:
        with st.container(border=True):
            st.markdown("## 📍")
            st.caption("PASO 02")
            st.markdown("### Identificá sectores críticos")
            st.write(
                "Seleccioná los círculos amarillos para conocer "
                "las características de los accidentes agrupados."
            )

    with c3:
        with st.container(border=True):
            st.markdown("## 💡")
            st.caption("PASO 03")
            st.markdown("### Consultá recomendaciones")
            st.write(
                "Revisá los patrones detectados y las propuestas "
                "de acciones preventivas para cada concentración."
            )

    st.divider()

    st.info(
        "Para comenzar: ingresá en «Mapa territorial» y explorá "
        "los puntos calientes y sus recomendaciones."
    )


# =====================================================
# 10. MAPA TERRITORIAL Y RECOMENDACIONES
# =====================================================

elif opcion == "Mapa territorial":

    st.title("🗺️ Mapa territorial de puntos calientes")

    st.write(
        "Explorá la distribución de los accidentes viales, "
        "identificá las concentraciones geográficas y consultá "
        "las recomendaciones preventivas generadas para cada grupo."
    )

    # DATOS COMPLETOS, SIN FILTROS DE BÚSQUEDA

    datos_mapa = (
        df[coordenadas_validas(df)]
        .copy()
        .reset_index(drop=True)
    )

    st.metric(
        "Total de accidentes con coordenadas válidas",
        len(datos_mapa)
    )

    if datos_mapa.empty:

        st.warning(
            "No hay registros con coordenadas válidas para mostrar en el mapa."
        )

        st.stop()

    # DISTANCIA DE AGRUPACIÓN

    distancia_grupo = st.slider(
        "Distancia máxima para agrupar accidentes (metros)",
        min_value=50,
        max_value=500,
        value=150,
        step=25,
        help=(
            "Define la distancia máxima entre accidentes para "
            "considerarlos parte de un mismo punto caliente."
        )
    )

    grupos = crear_grupos_geograficos(
        datos_mapa,
        distancia=distancia_grupo
    )

    # CREACIÓN DEL MAPA

    centro_lat = datos_mapa["latitud"].mean()
    centro_lon = datos_mapa["longitud"].mean()

    mapa = folium.Map(
        location=[
            centro_lat,
            centro_lon
        ],
        zoom_start=13,
        control_scale=True
    )

    # Capa de calor

    HeatMap(
        datos_mapa[
            ["latitud", "longitud"]
        ].values.tolist(),
        radius=22,
        blur=18,
        min_opacity=0.35,
        name="Mapa de calor"
    ).add_to(mapa)

    # Puntos calientes amarillos

    for grupo in grupos:

        cantidad = grupo["cantidad"]

        radio = min(
            18,
            7 + cantidad * 1.2
        )

        popup_html = f"""
        <div style="font-family:Arial;width:230px">
            <h4 style="color:#173B50">
                Punto caliente {grupo['id']}
            </h4>
            <b>Zona:</b> {grupo['zona']}<br>
            <b>Accidentes:</b> {cantidad}<br>
            <b>Identificador:</b> GRUPO_ID:{grupo['id']}<br>
            Seleccioná este círculo para consultar su análisis.
        </div>
        """

        folium.CircleMarker(

            location=[
                grupo["latitud"],
                grupo["longitud"]
            ],

            radius=radio,

            color="#173B66",

            weight=2,

            fill=True,

            fill_color="#FFD166",

            fill_opacity=0.9,

            tooltip=(
                f"Punto caliente {grupo['id']} — "
                f"{cantidad} accidente(s)"
            ),

            popup=folium.Popup(
                popup_html,
                max_width=300
            )

        ).add_to(mapa)

    folium.LayerControl(
        collapsed=True
    ).add_to(mapa)

    # Mostrar mapa

    resultado_mapa = st_folium(

        mapa,

        width=None,

        height=570,

        use_container_width=True,

        key="mapa_puntos_calientes",

        returned_objects=[
            "last_object_clicked",
            "last_object_clicked_popup"
        ]

    )

    st.caption(
        "El mapa de calor muestra la concentración de ubicaciones. "
        "Los círculos amarillos representan grupos de accidentes cercanos. "
        "Su tamaño indica la cantidad de registros."
    )

    # SELECCIÓN POR CLIC

    clic = (
        resultado_mapa.get("last_object_clicked")
        if resultado_mapa
        else None
    )

    popup_clic = (
        resultado_mapa.get("last_object_clicked_popup")
        if resultado_mapa
        else None
    )

    grupo_por_popup = None

    if popup_clic:

        coincidencia = re.search(
            r"GRUPO_ID:(\d+)",
            str(popup_clic)
        )

        if coincidencia:

            grupo_por_popup = int(
                coincidencia.group(1)
            )

    ids_disponibles = [
        g["id"] for g in grupos
    ]

    if grupo_por_popup in ids_disponibles:

        st.session_state[
            "grupo_seleccionado"
        ] = grupo_por_popup

    elif (
        clic
        and clic.get("lat") is not None
        and clic.get("lng") is not None
    ):

        lat_clic = float(clic["lat"])
        lon_clic = float(clic["lng"])

        grupo_elegido = min(
            grupos,

            key=lambda g: distancia_metros(
                lat_clic,
                lon_clic,
                g["latitud"],
                g["longitud"]
            )
        )

        distancia_clic = distancia_metros(
            lat_clic,
            lon_clic,
            grupo_elegido["latitud"],
            grupo_elegido["longitud"]
        )

        tolerancia = max(
            75,
            min(250, distancia_grupo)
        )

        if distancia_clic <= tolerancia:

            st.session_state[
                "grupo_seleccionado"
            ] = grupo_elegido["id"]

    # SELECTOR MANUAL

    st.divider()

    st.subheader("Seleccionar punto caliente")

    opciones = {
        (
            f"Punto {g['id']} - {g['zona']} - "
            f"{g['cantidad']} accidente(s)"
        ): g["id"]
        for g in grupos
    }

    etiquetas = [
        "Seleccioná un punto..."
    ] + list(opciones.keys())

    grupo_actual = st.session_state.get(
        "grupo_seleccionado"
    )

    if grupo_actual not in ids_disponibles:
        grupo_actual = None

    etiqueta_actual = "Seleccioná un punto..."

    if grupo_actual is not None:

        for etiqueta, identificador in opciones.items():

            if identificador == grupo_actual:
                etiqueta_actual = etiqueta
                break

    if (
        "selector_punto_caliente" not in st.session_state
        or st.session_state.get(
            "selector_punto_caliente"
        ) != etiqueta_actual
    ):

        st.session_state[
            "selector_punto_caliente"
        ] = etiqueta_actual

    def cambiar_punto():

        etiqueta = st.session_state[
            "selector_punto_caliente"
        ]

        if etiqueta == "Seleccioná un punto...":

            st.session_state[
                "grupo_seleccionado"
            ] = None

        else:

            st.session_state[
                "grupo_seleccionado"
            ] = opciones[etiqueta]

    st.selectbox(
        "Elegí una concentración para analizar:",
        etiquetas,
        key="selector_punto_caliente",
        on_change=cambiar_punto
    )

    # ANÁLISIS DEL GRUPO SELECCIONADO

    grupo_actual = st.session_state.get(
        "grupo_seleccionado"
    )

    if grupo_actual is not None and grupo_actual in ids_disponibles:

        seleccionado = next(
            g for g in grupos
            if g["id"] == grupo_actual
        )

        datos_seleccionados = seleccionado["datos"]

        recomendacion = recomendar_infraestructura(
            datos_seleccionados
        )

        st.divider()

        st.subheader(
            f"📍 Análisis del punto caliente {seleccionado['id']}"
        )

        m1, m2, m3 = st.columns(3)

        m1.metric(
            "Accidentes agrupados",
            seleccionado["cantidad"]
        )

        m2.metric(
            "Zona más frecuente",
            seleccionado["zona"]
        )

        m3.metric(
            "Tipos informados",
            recomendacion["cantidad_informada"]
        )

        # Análisis de colisiones

        st.markdown(
            "### Análisis de accidentes por tipo de colisión"
        )

        tipos = (
            datos_seleccionados["tipo_colision"]
            .astype(str)
            .str.strip()
        )

        tipos = tipos[
            ~tipos.map(normalizar).isin([
                "sin informacion",
                "",
                "nan",
                "none"
            ])
        ]

        if tipos.empty:

            st.warning(
                "No hay tipos de colisión informados en este grupo."
            )

        else:

            resumen_tipos = (
                tipos.value_counts()
                .rename_axis("Tipo de colisión")
                .reset_index(name="Cantidad")
            )

            resumen_tipos["Porcentaje"] = (
                resumen_tipos["Cantidad"]
                / len(tipos)
                * 100
            ).round(1)

            st.dataframe(
                resumen_tipos,
                use_container_width=True,
                hide_index=True
            )

        # Gravedad

        st.markdown("### Gravedad de los accidentes")

        g1, g2 = st.columns(2)

        g1.metric(
            "Registros con heridos",
            recomendacion["heridos"]
        )

        g2.metric(
            "Registros con fallecidos",
            recomendacion["fallecidos"]
        )

        # Recomendación

        st.divider()

        st.subheader(
            "💡 Recomendación del motor de análisis"
        )

        st.markdown(
            f"**Tipo de accidente predominante:** "
            f"{recomendacion['tipo']}"
        )

        st.info(
            f"**Infraestructura o acción a evaluar:**\n\n"
            f"{recomendacion['accion']}\n\n"
            f"**Justificación:**\n\n"
            f"{recomendacion['motivo']}\n\n"
            f"**Prioridad orientativa:**\n\n"
            f"{recomendacion['prioridad']}\n\n"
            f"**Base del cálculo:**\n\n"
            f"{recomendacion['confianza']}"
        )

        st.caption(
            "Las recomendaciones son propuestas orientativas generadas "
            "mediante reglas de análisis. No determinan por sí solas la "
            "instalación de infraestructura. Se requiere inspección y "
            "evaluación técnica."
        )

        # Detalle de los registros

        with st.expander(
            "Consultar accidentes incluidos en este punto"
        ):

            columnas = [
                c for c in [
                    "momento_exacto",
                    "zona",
                    "direccion_completa",
                    "tipo_colision",
                    "clasificacion_gravedad",
                    "latitud",
                    "longitud"
                ]
                if c in datos_seleccionados.columns
            ]

            st.dataframe(
                datos_seleccionados[columnas],
                use_container_width=True,
                hide_index=True
            )

        # Registrar recomendación

        st.divider()

        st.subheader(
            "Registrar recomendación preventiva"
        )

        st.write(
            "Podés guardar esta propuesta para asignarle "
            "un responsable y realizar su seguimiento."
        )

        if st.button(
            "📌 Preparar registro de esta recomendación",
            type="primary"
        ):

            st.session_state[
                "zona_para_registro"
            ] = seleccionado["zona"]

            st.session_state[
                "recomendacion_para_registro"
            ] = recomendacion["accion"]

            st.session_state[
                "descripcion_para_registro"
            ] = (
                f"Punto caliente {seleccionado['id']}. "
                f"Tipo predominante: {recomendacion['tipo']}. "
                f"Justificación: {recomendacion['motivo']} "
                f"Base: {recomendacion['confianza']} "
                "Requiere inspección técnica."
            )

            st.success(
                "Recomendación preparada. Ingresá en "
                "«Registrar acción preventiva» para completar el registro."
            )

    else:

        st.info(
            "Seleccioná un círculo amarillo del mapa o utilizá el selector "
            "para consultar el análisis y las recomendaciones."
        )


# =====================================================
# 11. REGISTRAR ACCIÓN PREVENTIVA
# =====================================================

elif opcion == "Registrar acción preventiva":

    st.title("📋 Registro de acciones preventivas")

    st.write(
        "Registrá una recomendación generada por el sistema "
        "o incorporá una propuesta propia."
    )

    zonas = sorted(
        df["zona"].dropna().unique().tolist()
    )

    if not zonas:
        zonas = ["SIN ZONA"]

    zona_previa = st.session_state.get(
        "zona_para_registro",
        zonas[0]
    )

    if zona_previa not in zonas:
        zona_previa = zonas[0]

    descripcion_previa = st.session_state.get(
        "descripcion_para_registro",
        ""
    )

    tipo_previo = st.session_state.get(
        "recomendacion_para_registro",
        ""
    )

    opciones_accion = [
        "Inspección de señalización",
        "Revisión de iluminación",
        "Evaluación de infraestructura",
        "Evaluar semaforización",
        "Evaluar reductor de velocidad",
        "Evaluar cruce peatonal",
        "Control de tránsito",
        "Relevamiento preventivo",
        "Otra acción"
    ]

    if tipo_previo and tipo_previo not in opciones_accion:
        opciones_accion.insert(0, tipo_previo)

    indice_accion = (
        opciones_accion.index(tipo_previo)
        if tipo_previo in opciones_accion
        else 0
    )

    with st.form("formulario_intervencion"):

        zona = st.selectbox(
            "Zona a revisar",
            zonas,
            index=zonas.index(zona_previa)
        )

        tipo_accion = st.selectbox(
            "Tipo de acción",
            opciones_accion,
            index=indice_accion
        )

        descripcion = st.text_area(
            "Descripción de la acción propuesta",
            value=descripcion_previa,
            placeholder="Describí qué se propone revisar o realizar..."
        )

        responsable = st.text_input(
            "Responsable o área asignada",
            placeholder="Ej.: Área de Tránsito"
        )

        fecha_inspeccion = st.date_input(
            "Fecha prevista de inspección",
            value=date.today()
        )

        estado = st.selectbox(
            "Estado inicial",
            [
                "Pendiente",
                "En proceso",
                "Finalizada"
            ]
        )

        observaciones = st.text_area(
            "Observaciones adicionales"
        )

        guardar = st.form_submit_button(
            "Guardar acción preventiva"
        )

    if guardar:

        if not descripcion.strip():

            st.error(
                "Ingresá una descripción de la acción."
            )

        else:

            guardar_intervencion(
                zona,
                tipo_accion,
                descripcion,
                responsable,
                str(fecha_inspeccion),
                estado,
                observaciones
            )

            st.success(
                "La acción preventiva fue registrada correctamente."
            )

            for clave in [
                "zona_para_registro",
                "recomendacion_para_registro",
                "descripcion_para_registro"
            ]:

                st.session_state.pop(clave, None)


# =====================================================
# 12. SEGUIMIENTO DE ACCIONES
# =====================================================

elif opcion == "Seguimiento de acciones":

    st.title("📌 Seguimiento de acciones preventivas")

    acciones = obtener_intervenciones()

    if acciones.empty:

        st.info(
            "Todavía no hay acciones registradas. Podés registrar una "
            "desde el mapa o desde el formulario de acciones preventivas."
        )

    else:

        pendientes = int(
            (acciones["estado"] == "Pendiente").sum()
        )

        proceso = int(
            (acciones["estado"] == "En proceso").sum()
        )

        finalizadas = int(
            (acciones["estado"] == "Finalizada").sum()
        )

        c1, c2, c3 = st.columns(3)

        c1.metric("Pendientes", pendientes)
        c2.metric("En proceso", proceso)
        c3.metric("Finalizadas", finalizadas)

        st.divider()

        st.subheader("Acciones registradas")

        st.dataframe(
            acciones,
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        st.subheader("Actualizar estado")

        id_seleccionado = st.selectbox(
            "Seleccioná el número de acción",
            acciones["id"].tolist()
        )

        estado_actual = acciones.loc[
            acciones["id"] == id_seleccionado,
            "estado"
        ].iloc[0]

        estados = [
            "Pendiente",
            "En proceso",
            "Finalizada"
        ]

        nuevo_estado = st.selectbox(
            "Nuevo estado",
            estados,
            index=(
                estados.index(estado_actual)
                if estado_actual in estados
                else 0
            )
        )

        if st.button("Actualizar acción"):

            actualizar_estado(
                id_seleccionado,
                nuevo_estado
            )

            st.success(
                "Estado actualizado correctamente."
            )

            st.rerun()


# =====================================================
# 13. CALIDAD DE DATOS
# =====================================================

elif opcion == "Calidad de datos":

    st.title("🔎 Diagnóstico de calidad de datos")

    total = len(df)

    duplicados = int(
        df.duplicated().sum()
    )

    sin_fecha = int(
        df["momento_exacto"].isna().sum()
    )

    sin_zona = int(
        df["zona"].isin(["SIN ZONA", ""]).sum()
    )

    coords_ok = coordenadas_validas(df)

    con_coords = int(coords_ok.sum())

    sin_coords = total - con_coords

    a, b, c = st.columns(3)

    a.metric("Total de registros", total)
    b.metric("Registros duplicados", duplicados)
    c.metric("Coordenadas válidas", con_coords)

    d, e, f = st.columns(3)

    d.metric("Sin fecha válida", sin_fecha)
    e.metric("Sin zona identificada", sin_zona)
    f.metric("Sin coordenadas", sin_coords)

    porcentaje = (
        con_coords / total * 100
        if total
        else 0
    )

    st.divider()

    st.subheader("Cobertura geográfica")

    st.progress(porcentaje / 100)

    st.write(
        f"El {porcentaje:.1f}% de los registros cuenta "
        "con coordenadas válidas."
    )

    st.caption(
        "El diagnóstico no modifica el archivo original."
    )


# =====================================================
# 14. INFORME Y EXPORTACIÓN
# =====================================================

elif opcion == "Informe y exportación":

    st.title("📄 Informes y exportación")

    st.subheader("Datos históricos")

    csv_historico = df.to_csv(
        index=False
    ).encode("utf-8-sig")

    st.download_button(
        "Descargar datos históricos CSV",
        data=csv_historico,
        file_name="siniestros_historicos.csv",
        mime="text/csv"
    )

    st.divider()

    st.subheader("Acciones preventivas")

    acciones = obtener_intervenciones()

    if acciones.empty:

        st.info(
            "No hay acciones preventivas para exportar."
        )

    else:

        csv_acciones = acciones.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            "Descargar seguimiento de acciones CSV",
            data=csv_acciones,
            file_name="seguimiento_acciones_preventivas.csv",
            mime="text/csv"
        )

        st.subheader("Resumen de seguimiento")

        resumen_estado = (
            acciones["estado"]
            .value_counts()
            .reset_index()
        )

        resumen_estado.columns = [
            "Estado",
            "Cantidad"
        ]

        st.dataframe(
            resumen_estado,
            use_container_width=True,
            hide_index=True
        )


# =====================================================
# 15. PIE DE PÁGINA
# =====================================================

st.sidebar.divider()

st.sidebar.caption(
    "Observatorio Vial Municipal 2.0"
)

st.sidebar.caption(
    "Prototipo académico — PP3"
)

