from __future__ import annotations

from pathlib import Path

import bcrypt
import streamlit as st
from cryptography.fernet import Fernet

from src.db import execute, fetch_all, fetch_one


KEY_PATH = "secret.key"


# =========================================================
# ENCRIPTACIÓN / DESENCRIPTACIÓN DE CÓDIGOS
# =========================================================

def load_fernet() -> Fernet:
    """
    Carga la llave usada para encriptar y desencriptar códigos.

    En Streamlit Cloud lee SECRET_KEY desde Secrets.
    En local, si no existe SECRET_KEY, lee el archivo secret.key.
    """
    try:
        secret_key = st.secrets.get("SECRET_KEY", None)
    except FileNotFoundError:
        secret_key = None
    except Exception:
        secret_key = None

    if secret_key:
        return Fernet(str(secret_key).encode("utf-8"))

    key_file = Path(KEY_PATH)

    if not key_file.exists():
        raise FileNotFoundError(
            "No existe secret.key ni SECRET_KEY. "
            "Ejecuta python init_db.py en local o configura SECRET_KEY en Streamlit."
        )

    return Fernet(key_file.read_bytes())


def encrypt_code(codigo: str) -> str:
    """
    Encripta el código para que el admin pueda consultarlo después.
    """
    fernet = load_fernet()
    return fernet.encrypt(codigo.encode("utf-8")).decode("utf-8")


def decrypt_code(codigo_encriptado: str) -> str:
    """
    Desencripta el código guardado en BD.
    """
    fernet = load_fernet()
    return fernet.decrypt(codigo_encriptado.encode("utf-8")).decode("utf-8")


# =========================================================
# HASH / VALIDACIÓN DE CÓDIGO
# =========================================================

def hash_code(codigo: str) -> str:
    """
    Genera hash bcrypt para el código.
    Este hash se usa para validar el login.
    """
    return bcrypt.hashpw(
        codigo.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")


def check_code(codigo: str, codigo_hash: str) -> bool:
    """
    Valida el código ingresado contra el hash guardado.
    """
    return bcrypt.checkpw(
        codigo.encode("utf-8"),
        codigo_hash.encode("utf-8")
    )


def validate_code_format(codigo: str) -> bool:
    """
    Valida que el código sea numérico de 4 dígitos.
    """
    return codigo.isdigit() and len(codigo) == 4


# =========================================================
# LOGIN / SESIÓN
# =========================================================

def authenticate_user(usuario: str, codigo: str):
    """
    Autentica un usuario usando usuario + código de 4 dígitos.

    Importante:
    Esta función NO usa SQLite directo.
    Usa fetch_one(), así funciona con SQLite o Supabase/PostgreSQL.
    """
    usuario = usuario.strip()
    codigo = codigo.strip()

    if not usuario or not codigo:
        return None

    if not validate_code_format(codigo):
        return None

    user = fetch_one("""
        SELECT
            id_usuario,
            usuario,
            codigo_hash,
            nombre,
            rol,
            estado_activo
        FROM usuarios
        WHERE usuario = :usuario
    """, {
        "usuario": usuario
    })

    if not user:
        return None

    if int(user["estado_activo"]) != 1:
        return None

    if not check_code(codigo, user["codigo_hash"]):
        return None

    return {
        "id_usuario": user["id_usuario"],
        "usuario": user["usuario"],
        "nombre": user["nombre"],
        "rol": user["rol"],
    }


def login(usuario: str, codigo: str) -> bool:
    """
    Inicia sesión con usuario + código.
    """
    user = authenticate_user(usuario, codigo)

    if not user:
        return False

    st.session_state["authenticated"] = True
    st.session_state["user"] = user

    return True


def logout() -> None:
    """
    Cierra sesión.
    """
    st.session_state.pop("authenticated", None)
    st.session_state.pop("user", None)


def login_form() -> None:
    """
    Formulario reutilizable de inicio de sesión.
    """
    st.subheader("Iniciar sesión")

    with st.form("login_form"):
        usuario = st.text_input("Usuario")
        codigo = st.text_input("Código de 4 dígitos", type="password", max_chars=4)
        submitted = st.form_submit_button("Ingresar")

    if submitted:
        if login(usuario, codigo):
            st.rerun()
        else:
            st.error("Usuario o código inválido, o usuario inactivo.")


def logout_button() -> None:
    """
    Botón de cierre de sesión.
    """
    if st.sidebar.button("Cerrar sesión"):
        logout()
        st.rerun()


def require_login() -> None:
    """
    Obliga a que el usuario haya iniciado sesión.
    """
    if not st.session_state.get("authenticated"):
        login_form()
        st.stop()


def require_admin() -> None:
    """
    Obliga a que el usuario sea administrador.
    """
    require_login()

    user = st.session_state.get("user")

    if not user or user.get("rol") != "admin":
        st.error("No tienes permisos para acceder a esta pantalla.")
        st.stop()


# =========================================================
# ADMINISTRACIÓN DE USUARIOS
# =========================================================

def create_user(
    usuario: str,
    codigo: str,
    nombre: str,
    rol: str = "participante"
) -> tuple[bool, str]:
    """
    Crea un usuario nuevo con código numérico de 4 dígitos.

    Guarda:
    - codigo_hash: para validar login.
    - codigo_encriptado: para que el admin pueda consultar el código.
    """

    usuario = usuario.strip()
    codigo = codigo.strip()
    nombre = nombre.strip()
    rol = rol.strip()

    if not usuario:
        return False, "El usuario es obligatorio."

    if not nombre:
        return False, "El nombre es obligatorio."

    if not codigo:
        return False, "El código es obligatorio."

    if not validate_code_format(codigo):
        return False, "El código debe ser numérico de 4 dígitos."

    if rol not in ("admin", "participante"):
        return False, "Rol inválido."

    codigo_hash = hash_code(codigo)

    try:
        codigo_encriptado = encrypt_code(codigo)
    except Exception as e:
        return False, f"Error encriptando código: {e}"

    try:
        rows = execute("""
            INSERT INTO usuarios (
                usuario,
                codigo_hash,
                codigo_encriptado,
                nombre,
                rol,
                estado_activo
            )
            VALUES (
                :usuario,
                :codigo_hash,
                :codigo_encriptado,
                :nombre,
                :rol,
                1
            )
        """, {
            "usuario": usuario,
            "codigo_hash": codigo_hash,
            "codigo_encriptado": codigo_encriptado,
            "nombre": nombre,
            "rol": rol,
        })

        if rows >= 0:
            return True, "Usuario creado correctamente."

        return False, "No se insertó ningún registro."

    except Exception as e:
        error_text = str(e).lower()

        if "unique" in error_text or "duplicate" in error_text:
            return False, "Ya existe un usuario con ese nombre de usuario."

        return False, f"Error creando usuario: {e}"


def update_user_code(id_usuario: int, nuevo_codigo: str) -> tuple[bool, str]:
    """
    Actualiza el código de un usuario.
    """
    nuevo_codigo = nuevo_codigo.strip()

    if not validate_code_format(nuevo_codigo):
        return False, "El código debe ser numérico de 4 dígitos."

    codigo_hash = hash_code(nuevo_codigo)

    try:
        codigo_encriptado = encrypt_code(nuevo_codigo)
    except Exception as e:
        return False, f"Error encriptando código: {e}"

    try:
        rows = execute("""
            UPDATE usuarios
            SET
                codigo_hash = :codigo_hash,
                codigo_encriptado = :codigo_encriptado
            WHERE id_usuario = :id_usuario
        """, {
            "codigo_hash": codigo_hash,
            "codigo_encriptado": codigo_encriptado,
            "id_usuario": id_usuario,
        })

        if rows > 0:
            return True, "Código actualizado correctamente."

        return False, "No se encontró el usuario."

    except Exception as e:
        return False, f"Error actualizando código: {e}"


def update_user_status(id_usuario: int, estado_activo: int) -> tuple[bool, str]:
    """
    Activa o desactiva un usuario.
    """
    estado_activo = 1 if int(estado_activo) == 1 else 0

    try:
        rows = execute("""
            UPDATE usuarios
            SET estado_activo = :estado_activo
            WHERE id_usuario = :id_usuario
        """, {
            "estado_activo": estado_activo,
            "id_usuario": id_usuario,
        })

        if rows > 0:
            return True, "Estado del usuario actualizado correctamente."

        return False, "No se encontró el usuario."

    except Exception as e:
        return False, f"Error actualizando usuario: {e}"


def get_all_users_with_codes() -> list[dict]:
    """
    Retorna todos los usuarios con el código desencriptado.
    Solo debería usarse en pantallas administrativas.
    """
    rows = fetch_all("""
        SELECT
            id_usuario,
            usuario,
            nombre,
            rol,
            estado_activo,
            codigo_encriptado,
            fecha_creacion
        FROM usuarios
        ORDER BY id_usuario
    """)

    users = []

    for row in rows:
        try:
            codigo = decrypt_code(row["codigo_encriptado"])
        except Exception:
            codigo = "No disponible"

        users.append({
            "id_usuario": row["id_usuario"],
            "usuario": row["usuario"],
            "nombre": row["nombre"],
            "rol": row["rol"],
            "estado_activo": row["estado_activo"],
            "codigo": codigo,
            "fecha_creacion": row["fecha_creacion"],
        })

    return users


def get_user_by_username(usuario: str):
    """
    Busca un usuario por nombre de usuario.
    """
    return fetch_one("""
        SELECT
            id_usuario,
            usuario,
            nombre,
            rol,
            estado_activo,
            codigo_encriptado,
            fecha_creacion
        FROM usuarios
        WHERE usuario = :usuario
    """, {
        "usuario": usuario.strip()
    })