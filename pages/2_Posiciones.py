from __future__ import annotations

import pandas as pd
import streamlit as st

from src.auth import require_login
from src.navigation import render_sidebar_navigation
from src.predictions import ensure_default_predictions_for_all_participants
from src.leaderboard import (
    get_leaderboard,
    get_today_predictions_matrix,
    recalculate_scores,
)


require_login()
render_sidebar_navigation()


user = st.session_state.get("user")

if user is None:
    st.error("No se encontró información del usuario en sesión.")
    st.stop()


st.title("🏆 Tabla de posiciones")
st.caption("Consulta la clasificación actual de los participantes de la Polla Mundialera.")


# =========================================================
# ACTUALIZAR 0-0 Y PUNTAJES
# =========================================================

with st.spinner("Actualizando predicciones por defecto y recalculando puntajes..."):
    ensure_default_predictions_for_all_participants()
    recalculate_scores()


# =========================================================
# FUNCIONES DE FILTRO
# =========================================================

def filter_leaderboard(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica filtros a la tabla general de posiciones.
    """
    if df is None or df.empty:
        return df

    filtered = df.copy()

    st.markdown("#### Filtros de posiciones")

    col1, col2, col3 = st.columns(3)

    with col1:
        search_text = st.text_input(
            "Buscar participante",
            placeholder="Nombre o usuario",
            key="filter_leaderboard_search"
        )

    with col2:
        if "puntos_totales" in filtered.columns:
            max_points = int(filtered["puntos_totales"].max()) if not filtered.empty else 0
            min_points = st.number_input(
                "Puntos mínimos",
                min_value=0,
                max_value=max_points if max_points > 0 else 999,
                value=0,
                step=1,
                key="filter_leaderboard_points"
            )
        else:
            min_points = 0

    with col3:
        ordenar_por = st.selectbox(
            "Ordenar por",
            options=[
                "Puntos totales",
                "Marcadores completos",
                "Aciertos ganador/empate",
                "Diferencia directa",
            ],
            key="filter_leaderboard_order"
        )

    if search_text:
        search_text = search_text.lower().strip()

        searchable_columns = [
            col for col in ["nombre", "usuario", "participante", "Participante"]
            if col in filtered.columns
        ]

        if searchable_columns:
            mask = False

            for col in searchable_columns:
                mask = mask | filtered[col].astype(str).str.lower().str.contains(search_text, na=False)

            filtered = filtered[mask]

    if "puntos_totales" in filtered.columns:
        filtered = filtered[filtered["puntos_totales"] >= min_points]

    order_map = {
        "Puntos totales": "puntos_totales",
        "Marcadores completos": "marcadores_completos",
        "Aciertos ganador/empate": "aciertos_ganador_empate",
        "Diferencia directa": "diferencias_directas",
    }

    order_column = order_map.get(ordenar_por)

    if order_column in filtered.columns:
        filtered = filtered.sort_values(by=order_column, ascending=False)

    return filtered


# =========================================================
# TABLA GENERAL DE POSICIONES
# =========================================================

st.subheader("Posiciones generales")

leaderboard = get_leaderboard()

if leaderboard is None or leaderboard.empty:
    st.info("Todavía no hay puntajes calculados para mostrar.")
else:
    filtered_leaderboard = filter_leaderboard(leaderboard)

    # Ocultar columnas internas que no deben mostrarse al usuario
    columns_to_hide = [
        "id_usuario",
        "usuario",
    ]

    filtered_leaderboard = filtered_leaderboard.drop(
        columns=[col for col in columns_to_hide if col in filtered_leaderboard.columns],
        errors="ignore",
    )

    st.write(f"Registros mostrados: **{len(filtered_leaderboard)}** de **{len(leaderboard)}**")

    st.dataframe(
        filtered_leaderboard,
        use_container_width=True,
        hide_index=True,
    )


# =========================================================
# PREDICCIONES DE LOS PARTIDOS DEL DÍA
# =========================================================

st.divider()

st.subheader("Predicciones de los partidos de hoy")

today_predictions_matrix = get_today_predictions_matrix()

if today_predictions_matrix is None or today_predictions_matrix.empty:
    st.info("Hoy no hay partidos con predicciones para mostrar.")
else:
    st.caption(
        "Cada fila corresponde a un participante. "
        "En cada bloque se muestra la predicción del usuario, el estado o marcador real del partido, "
        "y los puntos obtenidos."
    )

    participantes = sorted(
        today_predictions_matrix["Participante"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    participante_seleccionado = st.selectbox(
        "Filtrar por participante",
        options=["Todos"] + participantes,
        key="filtro_participante_predicciones_hoy",
    )

    filtered_today_matrix = today_predictions_matrix.copy()

    if participante_seleccionado != "Todos":
        filtered_today_matrix = filtered_today_matrix[
            filtered_today_matrix["Participante"].astype(str) == participante_seleccionado
        ]

    st.dataframe(
        filtered_today_matrix,
        use_container_width=True,
        hide_index=True,
    )