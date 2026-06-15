from __future__ import annotations

import streamlit as st

from src.auth import login, restore_session_from_cookie
from src.db import init_sqlite_schema
from src.navigation import render_sidebar_navigation
from src.predictions import ensure_default_predictions_for_all_participants


st.set_page_config(
    page_title="Polla Mundialista",
    page_icon="⚽",
    layout="wide"
)

restore_session_from_cookie()

init_sqlite_schema()


def render_login():
    st.title("🐓 Polla Mundialista 2026 ⚽")
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

    st.title("🐓 Polla Mundialista 2026 ⚽")
    st.info("""
    **AVISO DE PARTICIPACIÓN RESPONSABLE**

    La presente polla es una actividad estrictamente recreativa, social y sin ánimo de lucro, realizada entre familiares y/o amigos.

    La participación es voluntaria e implica la aceptación de sus reglas y resultados, bajo el entendido de que todos los participantes actúan como organizadores en igualdad de condiciones, sin intermediación profesional ni finalidad comercial.

    Los aportes tienen como único propósito la conformación del fondo común destinado a la premiación acordada de manera colectiva, sin que exista garantía de retorno o beneficio económico.

    Esta actividad no constituye una apuesta profesional ni una operación de juego comercial. Se recomienda participar de manera responsable y moderada.
    """)
   # st.success(f"Sesión iniciada como {user['nombre']} ({user['rol']})")

    st.info("Usa el menú lateral para ingresar a las opciones disponibles según tu rol.")

    st.divider()

    if user["rol"] == "admin":
        st.subheader("Panel de administrador")
        st.write(
            "Puedes consultar predicciones, posiciones, criterios, resultados, "
            "pantallas de prueba y administración de usuarios."
        )
    else:
        st.subheader("Panel de participante")
        st.write(
            "Puedes registrar tus predicciones, consultar posiciones, revisar criterios "
            "de puntuación y ver resultados del Mundial."
        )


if not st.session_state.get("authenticated"):
    render_login()
else:
    # Actualiza 0-0 para todos los participantes activos.
    # No incluye admins.
    ensure_default_predictions_for_all_participants()

    render_home()