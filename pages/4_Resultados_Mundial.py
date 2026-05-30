from __future__ import annotations

import streamlit as st

from src.auth import require_login
from src.navigation import render_sidebar_navigation


require_login()
render_sidebar_navigation()

from src.api_results import FootballResultsClient
from src.db import fetch_df

#st.set_page_config(page_title="Resultados Mundial", page_icon="🌎", layout="wide")


st.title("🌎 Resultados y posiciones del Mundial")
st.caption("Pantalla preparada para integrarse con una API de resultados en tiempo real.")

client = FootballResultsClient()
if client.is_configured():
    st.success("API configurada. Puedes implementar sincronización automática en `src/api_results.py`.")
else:
    st.warning("API no configurada. Se muestran los partidos guardados en la base de datos.")

matches = fetch_df(
    """
    SELECT
        p.fase,
        p.grupo,
        el.nombre AS equipo_local,
        ev.nombre AS equipo_visitante,
        COALESCE(p.goles_local_real || '-' || p.goles_visitante_real, '-') AS marcador,
        p.estado_partido,
        p.fecha_hora_partido
    FROM partidos p
    JOIN equipos el ON el.id_equipo = p.id_equipo_local
    JOIN equipos ev ON ev.id_equipo = p.id_equipo_visitante
    ORDER BY p.fecha_hora_partido
    """
)
st.dataframe(matches, use_container_width=True, hide_index=True)
