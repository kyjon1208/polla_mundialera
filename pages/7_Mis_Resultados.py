from __future__ import annotations

import pandas as pd
import streamlit as st

from src.auth import require_login
from src.db import fetch_df
from src.navigation import render_sidebar_navigation


require_login()
render_sidebar_navigation()


user = st.session_state.get("user")

if user is None:
    st.error("No se encontró información del usuario en sesión.")
    st.stop()


st.title("📊 Mis predicciones y resultados")
st.caption(
    "Consulta todos los partidos, tu predicción, el marcador real y los puntos obtenidos."
)


# =========================================================
# BLOQUEO PARA ADMIN
# =========================================================

if user.get("rol") != "participante":
    st.info("El administrador puede visualizar el sistema, pero no participa en la polla.")
    st.stop()


# =========================================================
# CONSULTA
# =========================================================

def get_my_results(id_usuario: int) -> pd.DataFrame:
    return fetch_df("""
        SELECT
            p.id_partido,
            p.fecha_hora_partido,
            p.fase,
            p.grupo,
            el.nombre AS equipo_local,
            ev.nombre AS equipo_visitante,

            p.goles_local_real,
            p.goles_visitante_real,

            pr.goles_local_predicho,
            pr.goles_visitante_predicho,

            pp.puntos,
            pp.criterio_aplicado,
            p.estado_partido

        FROM partidos p
        INNER JOIN equipos el
            ON p.id_equipo_local = el.id_equipo
        INNER JOIN equipos ev
            ON p.id_equipo_visitante = ev.id_equipo
        LEFT JOIN predicciones pr
            ON pr.id_partido = p.id_partido
           AND pr.id_usuario = :id_usuario
        LEFT JOIN puntajes_partido pp
            ON pp.id_partido = p.id_partido
           AND pp.id_usuario = :id_usuario
        WHERE p.id_equipo_local IS NOT NULL
          AND p.id_equipo_visitante IS NOT NULL
        ORDER BY p.fecha_hora_partido ASC, p.id_partido ASC
    """, {
        "id_usuario": id_usuario,
    })


results_df = get_my_results(int(user["id_usuario"]))


# =========================================================
# VALIDACIÓN
# =========================================================

if results_df.empty:
    st.info("Aún no hay partidos registrados.")
    st.stop()


# =========================================================
# FORMATEO
# =========================================================

display_df = results_df.copy()

display_df["Fecha"] = pd.to_datetime(
    display_df["fecha_hora_partido"]
).dt.strftime("%Y-%m-%d %H:%M")

display_df["Partido"] = (
    display_df["equipo_local"].astype(str)
    + " vs "
    + display_df["equipo_visitante"].astype(str)
)

display_df["Marcador real"] = display_df.apply(
    lambda row: (
        f"{row['equipo_local']} {int(row['goles_local_real'])} - "
        f"{int(row['goles_visitante_real'])} {row['equipo_visitante']}"
        if pd.notna(row["goles_local_real"]) and pd.notna(row["goles_visitante_real"])
        else "Pendiente"
    ),
    axis=1,
)

display_df["Mi predicción"] = display_df.apply(
    lambda row: (
        f"{int(row['goles_local_predicho'])} - {int(row['goles_visitante_predicho'])}"
        if pd.notna(row["goles_local_predicho"]) and pd.notna(row["goles_visitante_predicho"])
        else "No registrado"
    ),
    axis=1,
)

display_df["Puntos"] = display_df["puntos"].apply(
    lambda value: int(value) if pd.notna(value) else 0
)

display_df["Criterio aplicado"] = display_df["criterio_aplicado"].apply(
    lambda value: value if pd.notna(value) else "Sin calcular"
)

display_df = display_df.rename(columns={
    "fase": "Fase",
    "grupo": "Grupo",
    "estado_partido": "Estado",
})

display_df = display_df[[
    "Fecha",
    "Fase",
    "Grupo",
    "Partido",
    "Estado",
    "Marcador real",
    "Mi predicción",
    "Puntos",
    "Criterio aplicado",
]]


# =========================================================
# FILTROS
# =========================================================

st.subheader("Filtros")

col_f1, col_f2, col_f3 = st.columns(3)

with col_f1:
    grupos = sorted([
        grupo for grupo in display_df["Grupo"].dropna().unique().tolist()
        if grupo != ""
    ])

    grupo_seleccionado = st.selectbox(
        "Grupo",
        ["Todos"] + grupos,
    )

with col_f2:
    estados = sorted(display_df["Estado"].dropna().unique().tolist())

    estado_seleccionado = st.selectbox(
        "Estado",
        ["Todos"] + estados,
    )

with col_f3:
    estado_prediccion = st.selectbox(
        "Predicción",
        ["Todos", "Registrados", "No registrados"],
    )


filtered_df = display_df.copy()

if grupo_seleccionado != "Todos":
    filtered_df = filtered_df[filtered_df["Grupo"] == grupo_seleccionado]

if estado_seleccionado != "Todos":
    filtered_df = filtered_df[filtered_df["Estado"] == estado_seleccionado]

if estado_prediccion == "Registrados":
    filtered_df = filtered_df[filtered_df["Mi predicción"] != "No registrado"]

elif estado_prediccion == "No registrados":
    filtered_df = filtered_df[filtered_df["Mi predicción"] == "No registrado"]


# =========================================================
# RESUMEN
# =========================================================

total_puntos = int(filtered_df["Puntos"].sum())
total_partidos = len(filtered_df)
total_registrados = int((filtered_df["Mi predicción"] != "No registrado").sum())
total_no_registrados = int((filtered_df["Mi predicción"] == "No registrado").sum())

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Puntos", total_puntos)

with col2:
    st.metric("Partidos", total_partidos)

with col3:
    st.metric("Registrados", total_registrados)

with col4:
    st.metric("No registrados", total_no_registrados)


# =========================================================
# TABLA
# =========================================================

st.dataframe(
    filtered_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Partido": st.column_config.TextColumn(
            "Partido",
            pinned=True,
            width="medium",
        ),
        "Mi predicción": st.column_config.TextColumn(
            "Mi predicción",
            width="small",
        ),
        "Puntos": st.column_config.NumberColumn(
            "Puntos",
            width="small",
        ),
    },
)