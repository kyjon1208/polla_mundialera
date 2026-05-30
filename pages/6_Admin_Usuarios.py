import pandas as pd
import streamlit as st

from src.auth import (
    create_user,
    get_all_users_with_codes,
    require_admin,
    update_user_code,
    update_user_status,
)
from src.navigation import render_sidebar_navigation


require_admin()
render_sidebar_navigation()

st.title("👥 Administración de usuarios")
st.caption("Consulta, crea y administra usuarios de la Polla Mundialera.")


# =========================================================
# CREAR USUARIO
# =========================================================

st.subheader("Crear nuevo usuario")

with st.form("form_crear_usuario_admin"):
    col1, col2 = st.columns(2)

    with col1:
        usuario = st.text_input("Usuario único")
        nombre = st.text_input("Nombre completo")

    with col2:
        codigo = st.text_input("Código de 4 dígitos", max_chars=4, type="password")
        rol = st.selectbox("Rol", ["participante", "admin"])

    submitted = st.form_submit_button("Crear usuario")

if submitted:
    ok, mensaje = create_user(
        usuario=usuario,
        codigo=codigo,
        nombre=nombre,
        rol=rol,
    )

    if ok:
        st.success(mensaje)
        st.rerun()
    else:
        st.error(mensaje)


st.divider()


# =========================================================
# LISTADO DE USUARIOS
# =========================================================

st.subheader("Usuarios registrados")

users = get_all_users_with_codes()

if not users:
    st.info("No hay usuarios registrados.")
    st.stop()

df_users = pd.DataFrame(users)

# Para mostrar más bonito el estado
df_show = df_users.copy()
df_show["estado"] = df_show["estado_activo"].apply(
    lambda x: "Activo" if int(x) == 1 else "Inactivo"
)

columns_to_show = [
    "id_usuario",
    "usuario",
    "nombre",
    "rol",
    "estado",
    "codigo",
    "fecha_creacion",
]

st.dataframe(
    df_show[columns_to_show],
    use_container_width=True,
    hide_index=True,
)


st.divider()


# =========================================================
# ACTUALIZAR CÓDIGO
# =========================================================

st.subheader("Actualizar código de usuario")

user_options = {
    f"{row['id_usuario']} - {row['nombre']} ({row['usuario']})": int(row["id_usuario"])
    for _, row in df_users.iterrows()
}

with st.form("form_actualizar_codigo_usuario"):
    selected_user_label = st.selectbox(
        "Usuario",
        list(user_options.keys()),
        key="select_update_code_user",
    )

    nuevo_codigo = st.text_input(
        "Nuevo código de 4 dígitos",
        max_chars=4,
        type="password",
    )

    submitted_update_code = st.form_submit_button("Actualizar código")

if submitted_update_code:
    id_usuario_selected = user_options[selected_user_label]

    ok, mensaje = update_user_code(
        id_usuario=id_usuario_selected,
        nuevo_codigo=nuevo_codigo,
    )

    if ok:
        st.success(mensaje)
        st.rerun()
    else:
        st.error(mensaje)


st.divider()


# =========================================================
# ACTIVAR / DESACTIVAR USUARIO
# =========================================================

st.subheader("Activar o desactivar usuario")

with st.form("form_actualizar_estado_usuario"):
    selected_status_user_label = st.selectbox(
        "Usuario",
        list(user_options.keys()),
        key="select_update_status_user",
    )

    estado = st.selectbox(
        "Estado",
        ["Activo", "Inactivo"],
    )

    submitted_update_status = st.form_submit_button("Actualizar estado")

if submitted_update_status:
    id_usuario_selected = user_options[selected_status_user_label]
    estado_activo = 1 if estado == "Activo" else 0

    ok, mensaje = update_user_status(
        id_usuario=id_usuario_selected,
        estado_activo=estado_activo,
    )

    if ok:
        st.success(mensaje)
        st.rerun()
    else:
        st.error(mensaje)