from __future__ import annotations

import streamlit as st

from src.auth import login
from src.db import init_sqlite_schema
from src.navigation import render_sidebar_navigation


st.set_page_config(
    page_title="Polla Mundialista",
    page_icon="🐔",
    layout="wide"
)

init_sqlite_schema()


def render_login():
    st.title("🐔 Polla Mundialista 2026 ⚽")
    st.caption("Ingreso al sistema de predicciones del Mundial 2026.")

    st.subheader("Iniciar sesión")

    with st.form("login_form"):
        username = st.text_input("Usuario")
        codigo = st.text_input("Código de 4 dígitos", type="password", max_chars=4)
        submitted = st.form_submit_button("Ingresar")

    if submitted:
        if login(username, codigo):
            st.rerun()
        else:
            st.error("Usuario o código inválido, o usuario inactivo.")


def render_home():
    user = st.session_state["user"]

    render_sidebar_navigation()

    st.title("🐔 Polla Mundialista 2026 ⚽")
    st.caption("Polla Mundial 2026. 11 De Junio del 2026 al 19 de Julio del 2026")
    st.caption("JUEGA RESPONSABLEMENTE. Las apuestas pueden generar adicción y afectar su salud emocional, familiar y financiera. Prohibida la participación de menores de edad. No apueste dinero que no pueda permitirse perder. El juego es entretenimiento, no una fuente de ingresos.")
    #st.success(f"Sesión iniciada como {user['nombre']} ({user['rol']})")

    st.info("Usa el menú lateral para ingresar a las opciones disponibles.")

    st.divider()

    #if user["rol"] == "admin":
    #    st.subheader("Panel de administrador")
    #    st.write("Puedes consultar predicciones, posiciones, criterios de puntuación, resultados, pruebas y usuarios.")
    #else:
    #    st.subheader("Panel de participante")
    #    st.write("Puedes registrar predicciones, consultar posiciones, criterios de puntuación y resultados.")


if not st.session_state.get("authenticated"):
    render_login()
else:
    render_home()