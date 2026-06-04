from __future__ import annotations

import pandas as pd
import streamlit as st

from src.auth import require_login
from src.navigation import render_sidebar_navigation
from src.predictions import ensure_default_predictions_for_all_participants
from src.leaderboard import (
    get_leaderboard,
    get_recent_predictions,
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
    # Crea 0-0 para todos los participantes activos, excluyendo admins.
    ensure_default_predictions_for_all_participants()

    # Recalcula la tabla de posiciones.
    recalculate_scores()


# =========================================================
# FUNCIONES DE FILTRO
# =========================================================

def filter_leaderboard(df: pd.DataFrame) -> pd.DataFrame:
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
            col for col in ["nombre", "usuario", "participante"]
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


def filter_recent_predictions(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    filtered = df.copy()

    st.markdown("#### Filtros de últimos partidos")

    col1, col2, col3 = st.columns(3)

    with col1:
        if "fase" in filtered.columns:
            fases = sorted(filtered["fase"].dropna().unique().tolist())
            fase_selected = st.multiselect(
                "Fase",
                options=fases,
                default=[],
                key="filter_recent_fase"
            )
        else:
            fase_selected = []

    with col2:
        if "estado_partido" in filtered.columns:
            estados = sorted(filtered["estado_partido"].dropna().unique().tolist())
            estado_selected = st.multiselect(
                "Estado partido",
                options=estados,
                default=[],
                key="filter_recent_estado"
            )
        else:
            estado_selected = []

    with col3:
        equipo_text = st.text_input(
            "Buscar equipo",
            placeholder="Colombia, Brasil...",
            key="filter_recent_equipo"
        )

    if fase_selected and "fase" in filtered.columns:
        filtered = filtered[filtered["fase"].isin(fase_selected)]

    if estado_selected and "estado_partido" in filtered.columns:
        filtered = filtered[filtered["estado_partido"].isin(estado_selected)]

    if equipo_text:
        equipo_text = equipo_text.lower().strip()

        equipo_columns = [
            col for col in ["equipo_local", "equipo_visitante"]
            if col in filtered.columns
        ]

        if equipo_columns:
            mask = False

            for col in equipo_columns:
                mask = mask | filtered[col].astype(str).str.lower().str.contains(equipo_text, na=False)

            filtered = filtered[mask]

    return filtered


# =========================================================
# TABLA DE POSICIONES
# =========================================================

st.subheader("Posiciones generales")

leaderboard = get_leaderboard()

if leaderboard is None or leaderboard.empty:
    st.info("Todavía no hay puntajes calculados para mostrar.")
else:
    filtered_leaderboard = filter_leaderboard(leaderboard)

    st.write(f"Registros mostrados: **{len(filtered_leaderboard)}** de **{len(leaderboard)}**")

    st.dataframe(
        filtered_leaderboard,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# ÚLTIMAS PREDICCIONES / RESULTADOS
# =========================================================

st.divider()

st.subheader("Últimos partidos con predicciones")

recent_predictions = get_recent_predictions()

if recent_predictions is None or recent_predictions.empty:
    st.info("Todavía no hay predicciones recientes para mostrar.")
else:
    filtered_recent_predictions = filter_recent_predictions(recent_predictions)

    st.write(
        f"Registros mostrados: **{len(filtered_recent_predictions)}** "
        f"de **{len(recent_predictions)}**"
    )

    st.dataframe(
        filtered_recent_predictions,
        use_container_width=True,
        hide_index=True
    )