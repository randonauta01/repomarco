"""
App básica de Streamlit — Nivel de ríos/quebradas (CORNARE / MARCO)
--------------------------------------------------------------------
Aplicación personalizada para consultar el nivel de una estación
de monitoreo de CORNARE.

Estudiante: Aylin
Municipio: Carmen del Viboral
Estación: 44

Para correrla:
    streamlit run app_nivel_cornare.py
"""

import requests
import pandas as pd
import numpy as np
import streamlit as st
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ------------------------------------------------------------------
# COORDENADAS POR DEFECTO
# ------------------------------------------------------------------
LAT_DEFECTO = 6.2766
LON_DEFECTO = -75.5901

API_BASE_URL = "https://marco.cornare.gov.co/api/v1/estaciones"

LLAVE_FECHA = "level_date"
LLAVE_VALOR = "level"

CANDIDATOS_LAT = ["lat", "latitude", "latitud"]
CANDIDATOS_LON = ["lng", "lon", "longitude", "longitud"]


# ------------------------------------------------------------------
# CONFIGURACIÓN DE LA PÁGINA
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Nivel de estación — CORNARE",
    page_icon="🌊",
    layout="wide"
)


# ------------------------------------------------------------------
# FUNCIONES DE CONSULTA
# ------------------------------------------------------------------

def obtener_serie_nivel(
    codigo_estacion,
    desde,
    hasta,
    calidad=1,
    timeout=30
):
    """
    Consulta la API de CORNARE para obtener los niveles
    registrados en una estación.
    """

    url = f"{API_BASE_URL}/{codigo_estacion}/nivel"

    params = {
        "desde": desde,
        "hasta": hasta,
        "calidad": calidad
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
    }

    try:
        resp = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            verify=False
        )

        if resp.status_code == 200:
            return resp.json(), None

        return None, f"HTTP {resp.status_code}"

    except requests.exceptions.RequestException as e:
        return None, f"Error de red: {e}"


def obtener_todas_las_paginas(datos_json, timeout=30):
    """
    Obtiene todos los registros cuando la API devuelve
    varias páginas de resultados.
    """

    registros = list(datos_json.get("values", []))

    siguiente_url = datos_json.get("next")

    while siguiente_url:

        try:
            resp = requests.get(
                siguiente_url,
                timeout=timeout,
                verify=False
            )

        except requests.exceptions.RequestException:
            break

        if resp.status_code != 200:
            break

        pagina = resp.json()

        registros.extend(
            pagina.get("values", [])
        )

        siguiente_url = pagina.get("next")

    return registros


def detectar_coordenadas(datos_json):
    """
    Busca latitud y longitud dentro de la respuesta de la API.
    Si no encuentra las coordenadas, utiliza las coordenadas
    por defecto.
    """

    if not isinstance(datos_json, dict):
        return LAT_DEFECTO, LON_DEFECTO, False

    lat = next(
        (
            datos_json[k]
            for k in CANDIDATOS_LAT
            if k in datos_json
        ),
        None
    )

    lon = next(
        (
            datos_json[k]
            for k in CANDIDATOS_LON
            if k in datos_json
        ),
        None
    )

    if lat is not None and lon is not None:

        try:
            return float(lat), float(lon), True

        except (TypeError, ValueError):
            pass

    return LAT_DEFECTO, LON_DEFECTO, False


# ------------------------------------------------------------------
# FUNCIÓN PARA CALCULAR CALIDAD
# ------------------------------------------------------------------

def calcular_indice_calidad(df):
    """
    Calcula un índice sencillo de calidad entre 0 y 100.

    Tiene en cuenta:
    - Completitud de la serie.
    - Cantidad de valores atípicos.
    """

    if df.empty or len(df) < 2:
        return 0.0, 0, 0

    df_idx = df.set_index("fecha")

    frecuencia_tipica = (
        df["fecha"]
        .diff()
        .dropna()
        .mode()
    )

    if len(frecuencia_tipica) == 0:
        return 0.0, 0, 0

    frecuencia_tipica = frecuencia_tipica[0]

    rango_completo = pd.date_range(
        start=df_idx.index.min(),
        end=df_idx.index.max(),
        freq=frecuencia_tipica
    )

    esperados = len(rango_completo)

    huecos = esperados - len(df_idx)

    completitud = (
        max(0.0, 1 - (huecos / esperados))
        if esperados > 0
        else 0.0
    )

    Q1 = df["nivel"].quantile(0.25)
    Q3 = df["nivel"].quantile(0.75)

    IQR = Q3 - Q1

    lim_inf = Q1 - 1.5 * IQR
    lim_sup = Q3 + 1.5 * IQR

    es_outlier = (
        (df["nivel"] < lim_inf)
        | (df["nivel"] > lim_sup)
        | (df["nivel"] < 0)
    )

    proporcion_outliers = es_outlier.mean()

    indice = (
        completitud * 0.7
        + (1 - proporcion_outliers) * 0.3
    ) * 100

    return (
        round(indice, 1),
        int(huecos),
        int(es_outlier.sum())
    )


# ------------------------------------------------------------------
# FUNCIÓN PARA DETERMINAR EL ESTADO DEL NIVEL
# ------------------------------------------------------------------

def determinar_estado_nivel(nivel_actual, promedio):
    """
    Compara el último nivel registrado con el promedio.
    """

    if nivel_actual > promedio * 1.30:
        return "🔴 Nivel alto"

    elif nivel_actual < promedio * 0.70:
        return "🟡 Nivel bajo"

    else:
        return "🟢 Nivel normal"


# ------------------------------------------------------------------
# SIDEBAR — INFORMACIÓN DEL ESTUDIANTE
# ------------------------------------------------------------------

st.sidebar.header("👩‍🎓 Datos del estudiante")

nombre_estudiante = st.sidebar.text_input(
    "Nombre del estudiante",
    "Aylin"
)

municipio = st.sidebar.text_input(
    "Municipio",
    "Carmen del Viboral"
)

codigo_estacion = st.sidebar.text_input(
    "Código de estación",
    "44"
)

nombre_fuente = st.sidebar.text_input(
    "Nombre del río o quebrada",
    "Estación 44"
)

tipo_fuente = st.sidebar.selectbox(
    "Tipo de fuente hídrica",
    [
        "Río",
        "Quebrada",
        "Arroyo",
        "Otro"
    ]
)

# ------------------------------------------------------------------
# FECHAS Y CALIDAD
# ------------------------------------------------------------------

st.sidebar.header("📅 Parámetros de consulta")

fecha_desde = st.sidebar.date_input(
    "Desde",
    pd.to_datetime("2026-08-23")
).strftime("%Y-%m-%d")

fecha_hasta = st.sidebar.date_input(
    "Hasta",
    pd.to_datetime("2026-08-30")
).strftime("%Y-%m-%d")

calidad = st.sidebar.selectbox(
    "Calidad de los datos",
    [1, 0],
    index=0,
    help="1 = solo datos validados"
)

# ------------------------------------------------------------------
# INFORMACIÓN ADICIONAL
# ------------------------------------------------------------------

st.sidebar.header("📝 Información adicional")

observacion = st.sidebar.text_area(
    "Observación",
    "Consulta académica sobre el nivel del agua."
)

consultar = st.sidebar.button(
    "🔍 Consultar",
    type="primary"
)


# ------------------------------------------------------------------
# TÍTULO PRINCIPAL
# ------------------------------------------------------------------

st.title(
    "🌊 Nivel de ríos y quebradas — CORNARE"
)

st.caption(
    f"Estudiante: **{nombre_estudiante}** · "
    f"Municipio: **{municipio}** · "
    f"Estación: **{codigo_estacion}**"
)


# ------------------------------------------------------------------
# TARJETA DE INFORMACIÓN
# ------------------------------------------------------------------

info1, info2, info3, info4 = st.columns(4)

info1.info(
    f"👩‍🎓 **Estudiante**\n\n"
    f"{nombre_estudiante}"
)

info2.info(
    f"📍 **Municipio**\n\n"
    f"{municipio}"
)

info3.info(
    f"💧 **Fuente hídrica**\n\n"
    f"{nombre_fuente}"
)

info4.info(
    f"🔢 **Estación**\n\n"
    f"{codigo_estacion}"
)


# ------------------------------------------------------------------
# CONSULTA Y PROCESAMIENTO
# ------------------------------------------------------------------

if consultar:

    with st.spinner("Consultando la API de CORNARE..."):

        datos_crudos, error = obtener_serie_nivel(
            codigo_estacion,
            fecha_desde,
            fecha_hasta,
            calidad
        )

    # --------------------------------------------------------------
    # ERROR
    # --------------------------------------------------------------

    if error:

        st.error(
            f"❌ No fue posible realizar la consulta: {error}"
        )

    else:

        registros = obtener_todas_las_paginas(
            datos_crudos
        )

        # ----------------------------------------------------------
        # SIN DATOS
        # ----------------------------------------------------------

        if not registros:

            st.warning(
                "⚠️ No hay registros para esta estación "
                "y rango de fechas."
            )

            st.info(
                "Prueba modificando el código de estación "
                "o el rango de fechas."
            )

        # ----------------------------------------------------------
        # CON DATOS
        # ----------------------------------------------------------

        else:

            df = pd.DataFrame(registros)

            # ------------------------------------------------------
            # CAMBIO DE NOMBRES DE COLUMNAS
            # ------------------------------------------------------

            df = df.rename(
                columns={
                    LLAVE_FECHA: "fecha",
                    LLAVE_VALOR: "nivel"
                }
            )

            # ------------------------------------------------------
            # CONVERSIÓN DE DATOS
            # ------------------------------------------------------

            df["fecha"] = pd.to_datetime(
                df["fecha"],
                errors="coerce"
            )

            df["nivel"] = pd.to_numeric(
                df["nivel"],
                errors="coerce"
            )

            df = (
                df
                .dropna(subset=["fecha", "nivel"])
                .sort_values("fecha")
                .reset_index(drop=True)
            )

            # ------------------------------------------------------
            # COORDENADAS
            # ------------------------------------------------------

            lat, lon, coords_reales = detectar_coordenadas(
                datos_crudos
            )

            # ------------------------------------------------------
            # ÍNDICE DE CALIDAD
            # ------------------------------------------------------

            (
                indice_calidad,
                huecos,
                n_outliers
            ) = calcular_indice_calidad(df)

            # ======================================================
            # MÉTRICAS PRINCIPALES
            # ======================================================

            st.subheader("📊 Resultados de la consulta")

            nivel_promedio = df["nivel"].mean()
            nivel_maximo = df["nivel"].max()
            nivel_minimo = df["nivel"].min()
            nivel_actual = df["nivel"].iloc[-1]

            diferencia_niveles = (
                nivel_maximo - nivel_minimo
            )

            estado = determinar_estado_nivel(
                nivel_actual,
                nivel_promedio
            )

            col1, col2, col3, col4 = st.columns(4)

            col1.metric(
                "📖 Lecturas",
                len(df)
            )

            col2.metric(
                "📏 Nivel promedio",
                f"{nivel_promedio:.2f}"
            )

            col3.metric(
                "⬆️ Nivel máximo",
                f"{nivel_maximo:.2f}"
            )

            col4.metric(
                "⬇️ Nivel mínimo",
                f"{nivel_minimo:.2f}"
            )

            # ======================================================
            # SEGUNDA FILA DE MÉTRICAS
            # ======================================================

            st.subheader("🔎 Indicadores adicionales")

            col5, col6, col7, col8 = st.columns(4)

            col5.metric(
                "🕐 Último nivel",
                f"{nivel_actual:.2f}"
            )

            col6.metric(
                "↕️ Rango del nivel",
                f"{diferencia_niveles:.2f}"
            )

            col7.metric(
                "⭐ Índice de calidad",
                f"{indice_calidad} / 100"
            )

            col8.metric(
                "⚠️ Outliers",
                n_outliers
            )

            # ======================================================
            # ESTADO DEL NIVEL
            # ======================================================

            st.subheader("🚦 Estado actual")

            if "🔴" in estado:

                st.error(
                    f"{estado}: el último valor registrado "
                    f"está considerablemente por encima "
                    f"del promedio."
                )

            elif "🟡" in estado:

                st.warning(
                    f"{estado}: el último valor registrado "
                    f"está por debajo del promedio."
                )

            else:

                st.success(
                    f"{estado}: el último valor registrado "
                    f"se encuentra cercano al promedio."
                )

            # ======================================================
            # GRÁFICO DE LA SERIE
            # ======================================================

            st.subheader("📈 Serie histórica del nivel")

            st.line_chart(
                df.set_index("fecha")["nivel"]
            )

            # ======================================================
            # INFORMACIÓN DEL PERÍODO
            # ======================================================

            st.subheader("📅 Información del período")

            periodo1, periodo2, periodo3 = st.columns(3)

            periodo1.write(
                f"**Fecha inicial:** "
                f"{df['fecha'].min().strftime('%Y-%m-%d')}"
            )

            periodo2.write(
                f"**Fecha final:** "
                f"{df['fecha'].max().strftime('%Y-%m-%d')}"
            )

            periodo3.write(
                f"**Total de registros:** "
                f"{len(df)}"
            )

            # ======================================================
            # MAPA
            # ======================================================

            st.subheader(
                "📍 Ubicación de la estación"
            )

            if not coords_reales:

                st.caption(
                    "⚠️ La API no trajo latitud/longitud "
                    "de la estación. Se muestra la ubicación "
                    "por defecto configurada en la aplicación."
                )

            mapa = pd.DataFrame(
                {
                    "lat": [lat],
                    "lon": [lon]
                }
            )

            st.map(
                mapa,
                zoom=10
            )

            # ======================================================
            # DETALLE DEL ÍNDICE DE CALIDAD
            # ======================================================

            with st.expander(
                "📋 Detalle del índice de calidad"
            ):

                st.write(
                    f"- Huecos de reporte detectados: "
                    f"**{huecos}**"
                )

                st.write(
                    f"- Outliers detectados: "
                    f"**{n_outliers}** de "
                    f"**{len(df)}** lecturas"
                )

                st.write(
                    "- Completitud de la serie: **70%**"
                )

                st.write(
                    "- Datos sin outliers: **30%**"
                )

                st.write(
                    "El índice combina la completitud de "
                    "la serie y la proporción de datos sin "
                    "valores atípicos."
                )

            # ======================================================
            # INFORMACIÓN DE LA CONSULTA
            # ======================================================

            with st.expander(
                "ℹ️ Información de la consulta"
            ):

                st.write(
                    f"**Estudiante:** {nombre_estudiante}"
                )

                st.write(
                    f"**Municipio:** {municipio}"
                )

                st.write(
                    f"**Código de estación:** "
                    f"{codigo_estacion}"
                )

                st.write(
                    f"**Fuente hídrica:** "
                    f"{nombre_fuente}"
                )

                st.write(
                    f"**Tipo:** {tipo_fuente}"
                )

                st.write(
                    f"**Desde:** {fecha_desde}"
                )

                st.write(
                    f"**Hasta:** {fecha_hasta}"
                )

                st.write(
                    f"**Calidad seleccionada:** "
                    f"{calidad}"
                )

                st.write(
                    f"**Observación:** {observacion}"
                )

            # ======================================================
            # TABLA DE DATOS
            # ======================================================

            with st.expander(
                "📄 Ver datos obtenidos"
            ):

                st.dataframe(
                    df,
                    use_container_width=True
                )

            # ======================================================
            # DESCARGA CSV
            # ======================================================

            csv = df.to_csv(
                index=False
            ).encode("utf-8")

            st.download_button(
                "⬇️ Descargar datos en CSV",
                csv,
                file_name=(
                    f"nivel_estacion_"
                    f"{codigo_estacion}.csv"
                ),
                mime="text/csv"
            )

            # ======================================================
            # MENSAJE FINAL
            # ======================================================

            st.success(
                f"✅ Consulta realizada correctamente "
                f"para la estación {codigo_estacion} "
                f"en {municipio}."
            )

# ------------------------------------------------------------------
# MENSAJE INICIAL
# ------------------------------------------------------------------

else:

    st.info(
        "👈 Ajusta los parámetros en el menú lateral "
        "y presiona **🔍 Consultar** para obtener "
        "los datos de la estación."
    )

    st.markdown(
        """
        ### 🌱 Sobre esta aplicación

        Esta aplicación permite consultar y visualizar
        información sobre el nivel de ríos y quebradas
        utilizando datos proporcionados por CORNARE.

        **Información configurada:**

        - 👩‍🎓 Estudiante: **Aylin**
        - 📍 Municipio: **Carmen del Viboral**
        - 🔢 Estación: **44**
        - 🌊 Consulta de niveles de agua
        - 📊 Análisis de calidad de los datos
        - 📈 Gráfico histórico
        - 🗺️ Ubicación de la estación
        - 📥 Descarga de datos en formato CSV
        """
    )
