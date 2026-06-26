from __future__ import annotations

import streamlit as st

from src.auth import logout


def render_sidebar_navigation():
    """
    Muestra la navegación lateral según el rol del usuario.
    Debe llamarse en app.py y en cada archivo dentro de pages/.
    """
    user = st.session_state.get("user")

    if not user:
        return

    rol = user["rol"]

    st.sidebar.title("⚽ Polla Mundialista⚽")
    st.sidebar.write(f"Usuario: **{user['nombre']}**")
    st.sidebar.write(f"Rol: **{rol}**")

    st.sidebar.divider()

    st.sidebar.page_link("app.py", label="Inicio", icon="🏠")
    st.sidebar.page_link("pages/1_Predicciones.py", label="Predicciones", icon="📝")
    st.sidebar.page_link("pages/7_Mis_Resultados.py", label="📊 Mis resultados")
    st.sidebar.page_link("pages/2_Posiciones.py", label="Posiciones", icon="🏆")
    st.sidebar.page_link("pages/3_Criterios.py", label="Reglamento", icon="📊")
    st.sidebar.page_link("pages/4_Resultados_Mundial.py", label="Resultados Mundial", icon="🌎")

    if rol == "admin":
        st.sidebar.divider()
        st.sidebar.subheader("Administración")
        st.sidebar.page_link("pages/5_Pruebas_Admin.py", label="Pruebas Admin", icon="🧪")
        st.sidebar.page_link("pages/6_Admin_Usuarios.py", label="Usuarios", icon="👥")

    st.sidebar.divider()

    if st.sidebar.button("Cerrar sesión"):
        logout()
        st.rerun()