from __future__ import annotations

import streamlit as st

from src.auth import require_login
from src.navigation import render_sidebar_navigation


require_login()
render_sidebar_navigation()
from src.db import fetch_df

#st.set_page_config(page_title="Criterios", page_icon="📊", layout="wide")


st.title("📊 Criterios de puntuación")
criteria = fetch_df(
    """
    SELECT nombre_criterio, fase, puntos
    FROM criterios_puntuacion
    ORDER BY nombre_criterio, fase
    """
)

if criteria.empty:
    st.info("No hay criterios cargados. Ejecuta el script `02_insert_criterios.sql`.")
else:
    pivot = criteria.pivot_table(index="nombre_criterio", columns="fase", values="puntos", aggfunc="first").reset_index()
    st.dataframe(pivot, use_container_width=True, hide_index=True)

st.subheader("Criterios de desempate")
st.markdown(
    """
1. Mayor cantidad de marcadores completos acertados.  
2. Mayor cantidad de aciertos de ganador o empate.  
3. Mayor cantidad de diferencias de goles directas acertadas.  
4. Si continúa el empate, los premios se juntan y se reparten por igual.
"""
)
