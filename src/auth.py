from __future__ import annotations

import sqlite3
from pathlib import Path

import bcrypt
import streamlit as st
from cryptography.fernet import Fernet

from src.db import get_sqlite_connection


KEY_PATH = "secret.key"


# =========================================================
# ENCRIPTACIÓN / DESENCRIPTACIÓN DE CÓDIGOS
# =========================================================

def load_fernet() -> Fernet:
    """
    Carga la llave usada para encriptar y desencriptar códigos.
    La llave debe existir en la raíz del proyecto como secret.key.
    """
    key_file = Path(KEY_PATH)

    if not key_file.exists():
        raise FileNotFoundError(
            "No existe secret.key. Ejecuta primero: python init_db.py"
        )

    key = key_file.read_bytes()
    return Fernet(key)


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
    """
    usuario = usuario.strip()
    codigo = codigo.strip()

    if not usuario or not codigo:
        return None

    if not validate_code_format(codigo):
        return None

    conn = get_sqlite_connection()
    conn.row_factory = sqlite3.Row

    try:
        user = conn.execute("""
            SELECT
                id_usuario,
                usuario,
                codigo_hash,
                nombre,
                rol,
                estado_activo
            FROM usuarios
            WHERE usuario = ?
        """, (usuario,)).fetchone()
    finally:
        conn.close()

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

    conn = get_sqlite_connection()

    try:
        cursor = conn.execute("""
            INSERT INTO usuarios (
                usuario,
                codigo_hash,
                codigo_encriptado,
                nombre,
                rol,
                estado_activo
            )
            VALUES (?, ?, ?, ?, ?, 1)
        """, (
            usuario,
            codigo_hash,
            codigo_encriptado,
            nombre,
            rol,
        ))

        conn.commit()

        if cursor.rowcount == 1:
            return True, "Usuario creado correctamente."

        return False, "No se insertó ningún registro."

    except sqlite3.IntegrityError:
        return False, "Ya existe un usuario con ese nombre de usuario."

    except Exception as e:
        return False, f"Error creando usuario: {e}"

    finally:
        conn.close()


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

    conn = get_sqlite_connection()

    try:
        cursor = conn.execute("""
            UPDATE usuarios
            SET
                codigo_hash = ?,
                codigo_encriptado = ?
            WHERE id_usuario = ?
        """, (
            codigo_hash,
            codigo_encriptado,
            id_usuario,
        ))

        conn.commit()

        if cursor.rowcount > 0:
            return True, "Código actualizado correctamente."

        return False, "No se encontró el usuario."

    except Exception as e:
        return False, f"Error actualizando código: {e}"

    finally:
        conn.close()


def update_user_status(id_usuario: int, estado_activo: int) -> tuple[bool, str]:
    """
    Activa o desactiva un usuario.
    """
    estado_activo = 1 if int(estado_activo) == 1 else 0

    conn = get_sqlite_connection()

    try:
        cursor = conn.execute("""
            UPDATE usuarios
            SET estado_activo = ?
            WHERE id_usuario = ?
        """, (
            estado_activo,
            id_usuario,
        ))

        conn.commit()

        if cursor.rowcount > 0:
            return True, "Estado del usuario actualizado correctamente."

        return False, "No se encontró el usuario."

    except Exception as e:
        return False, f"Error actualizando usuario: {e}"

    finally:
        conn.close()


def get_all_users_with_codes() -> list[dict]:
    """
    Retorna todos los usuarios con el código desencriptado.
    Solo debería usarse en pantallas administrativas.
    """
    conn = get_sqlite_connection()
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute("""
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
        """).fetchall()
    finally:
        conn.close()

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
    conn = get_sqlite_connection()
    conn.row_factory = sqlite3.Row

    try:
        user = conn.execute("""
            SELECT
                id_usuario,
                usuario,
                nombre,
                rol,
                estado_activo,
                codigo_encriptado,
                fecha_creacion
            FROM usuarios
            WHERE usuario = ?
        """, (usuario.strip(),)).fetchone()
    finally:
        conn.close()

    return user