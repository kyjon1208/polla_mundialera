from __future__ import annotations

import pandas as pd
import streamlit as st

from src.auth import require_login
from src.db import fetch_df
from src.navigation import render_sidebar_navigation


require_login()
render_sidebar_navigation()


st.title("📋 Criterios, premios y condiciones")
st.caption("Consulta los criterios de puntuación, premios, desempates y reglas generales de la Polla Mundialera.")


# =========================================================
# CONFIGURACIÓN
# =========================================================

FASE_ORDER = [
    "Fase de Grupos",
    "Dieciseisavos",
    "Octavos",
    "Cuartos",
    "Semifinal",
    "Tercer Puesto",
    "Final",
]


# =========================================================
# CONSULTAS
# =========================================================

def get_criteria_df() -> pd.DataFrame:
    return fetch_df("""
        SELECT
            nombre_criterio,
            fase,
            puntos
        FROM criterios_puntuacion
    """)


def build_criteria_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construye una tabla donde:
    - Las filas son los criterios.
    - Las columnas son las fases en orden lógico.
    - Los criterios se ordenan de mayor a menor puntaje máximo.
    """
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

    pivot = pivot.rename(columns={
        "nombre_criterio": "Criterio"
    })

    return pivot


# =========================================================
# PREMIOS
# =========================================================

st.subheader("🏅 Premios")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Primero", "50.00%")

with col2:
    st.metric("Segundo", "30.00%")

with col3:
    st.metric("Tercero", "20.00%")


# =========================================================
# VALOR Y FECHAS DE PAGO
# =========================================================

st.divider()

st.subheader("💰 Valor y fechas límite de pago")

st.markdown("""
**Valor de inscripción:** $65.000

**Fecha límite de pago:**

- **50%:** martes, junio 11 de 2026 — Iniciación 1ª fecha Fase de Grupos.
- **50%:** domingo, junio 28 de 2026 — Iniciación Dieciseisavos de Final.
""")


# =========================================================
# CONDICIONES DE DESEMPATE
# =========================================================

st.divider()

st.subheader("⚖️ Condiciones de desempate")

st.markdown("""
En caso de empate en puntos, se aplicarán los siguientes criterios en orden:

1. Mayor cantidad de **marcadores completos acertados**.
2. Mayor cantidad de **aciertos de ganador o empate**.
3. Mayor cantidad de **diferencias de goles directas acertadas**.
4. Si el empate continúa, se juntan los premios correspondientes y se reparten por igual entre los empatados.
""")


# =========================================================
# NOTAS
# =========================================================

st.divider()

st.subheader("📝 Notas generales")

st.markdown("""
1. Se considera el marcador del partido **después del alargue y antes de los penaltis**.
2. Los marcadores se pueden ingresar máximo hasta las **11:59 p.m. del día anterior al partido**.
3. Cualquier inconveniente debe comunicarse al WhatsApp **3155638972**.
4. Quien no ingrese los marcadores oportunamente, juega con el marcador **0 – 0**.
5. Al finalizar los partidos, se podrán visualizar los puntos obtenidos en los partidos del día con la tabla de posiciones actualizada.
""")


# =========================================================
# TABLA DE CRITERIOS
# =========================================================

st.divider()

st.subheader("📊 Tabla de criterios de puntuación")

criteria_raw = get_criteria_df()

if criteria_raw is None or criteria_raw.empty:
    st.info("No hay criterios de puntuación registrados.")
else:
    criteria_table = build_criteria_table(criteria_raw)

    st.dataframe(
        criteria_table,
        use_container_width=True,
        hide_index=True,
    )