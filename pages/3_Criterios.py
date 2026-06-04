from __future__ import annotations

import pandas as pd
import streamlit as st

from src.auth import require_login
from src.db import fetch_df
from src.navigation import render_sidebar_navigation


require_login()
render_sidebar_navigation()


st.title("📋 Criterios de puntuación")
st.caption("Consulta los criterios usados para calcular los puntos de la Polla Mundialera.")


FASE_ORDER = [
    "Fase de Grupos",
    "Dieciseisavos",
    "Octavos",
    "Cuartos",
    "Semifinal",
    "Tercer Puesto",
    "Final",
]


def get_criteria_df() -> pd.DataFrame:
    return fetch_df("""
        SELECT
            nombre_criterio,
            fase,
            puntos
        FROM criterios_puntuacion
    """)


def build_criteria_table(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    pivot = df.pivot_table(
        index="nombre_criterio",
        columns="fase",
        values="puntos",
        aggfunc="max",
        fill_value=0,
    )

    for fase in FASE_ORDER:
        if fase not in pivot.columns:
            pivot[fase] = 0

    pivot = pivot[FASE_ORDER]

    pivot["max_puntos"] = pivot.max(axis=1)

    pivot = pivot.sort_values(
        by="max_puntos",
        ascending=False,
    )

    pivot = pivot.drop(columns=["max_puntos"])

    pivot = pivot.reset_index()

    return pivot


criteria_raw = get_criteria_df()

if criteria_raw is None or criteria_raw.empty:
    st.info("No hay criterios de puntuación registrados.")
    st.stop()


criteria_table = build_criteria_table(criteria_raw)

st.dataframe(
    criteria_table,
    use_container_width=True,
    hide_index=True,
)