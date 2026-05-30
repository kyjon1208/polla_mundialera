from __future__ import annotations

import sqlite3
from pathlib import Path

import streamlit as st


DEFAULT_DB_PATH = "polla_mundialera.db"


def get_db_mode() -> str:
    """
    Retorna el modo de base de datos configurado.

    Por ahora el proyecto trabaja con SQLite.
    Si no existe secrets.toml, usa sqlite por defecto.
    """
    try:
        return str(st.secrets.get("APP_DB_MODE", "sqlite")).lower()
    except FileNotFoundError:
        return "sqlite"
    except Exception:
        return "sqlite"


def get_sqlite_db_path() -> str:
    """
    Retorna la ruta de la base SQLite.

    Puede venir desde .streamlit/secrets.toml:

        SQLITE_DB_PATH = "polla_mundialera.db"

    Si no existe, usa polla_mundialera.db por defecto.
    """
    try:
        return str(st.secrets.get("SQLITE_DB_PATH", DEFAULT_DB_PATH))
    except FileNotFoundError:
        return DEFAULT_DB_PATH
    except Exception:
        return DEFAULT_DB_PATH


def get_sqlite_connection() -> sqlite3.Connection:
    """
    Crea y retorna una conexión SQLite.

    Se activa PRAGMA foreign_keys para respetar llaves foráneas.
    """
    db_path = get_sqlite_db_path()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    return conn


def get_connection() -> sqlite3.Connection:
    """
    Función general para obtener conexión a base de datos.

    Por ahora solo soporta SQLite.
    Más adelante aquí se puede agregar soporte para Supabase/PostgreSQL.
    """
    db_mode = get_db_mode()

    if db_mode == "sqlite":
        return get_sqlite_connection()

    raise ValueError(f"Modo de base de datos no soportado: {db_mode}")


def database_exists() -> bool:
    """
    Valida si existe físicamente el archivo SQLite.
    """
    db_path = Path(get_sqlite_db_path())
    return db_path.exists()


def init_sqlite_schema() -> None:
    """
    Esta función queda por compatibilidad con el app.py original.

    Antes el app.py llamaba init_sqlite_schema() para crear las tablas.
    Ahora la base de datos se crea ejecutando:

        python init_db.py

    Por eso esta función no hace nada.
    """
    return None


def fetch_all(sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
    """
    Ejecuta un SELECT y retorna todos los registros.
    """
    conn = get_sqlite_connection()
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute(sql, params).fetchall()
        return rows
    finally:
        conn.close()


def fetch_one(sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
    """
    Ejecuta un SELECT y retorna un solo registro.
    """
    conn = get_sqlite_connection()
    conn.row_factory = sqlite3.Row

    try:
        row = conn.execute(sql, params).fetchone()
        return row
    finally:
        conn.close()


def execute_query(sql: str, params: tuple | dict = ()) -> int:
    """
    Ejecuta INSERT, UPDATE o DELETE.

    Retorna el número de filas afectadas.
    """
    conn = get_sqlite_connection()

    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def execute_many(sql: str, params_list: list[tuple] | list[dict]) -> int:
    """
    Ejecuta varios INSERT, UPDATE o DELETE.

    Retorna el número de filas afectadas.
    """
    conn = get_sqlite_connection()

    try:
        cursor = conn.executemany(sql, params_list)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


# =========================================================
# FUNCIONES DE COMPATIBILIDAD CON LAS PÁGINAS ORIGINALES
# =========================================================

def execute(sql: str, params: tuple | dict = ()) -> int:
    """
    Función compatible con las páginas originales.

    Ejecuta INSERT, UPDATE o DELETE.
    Retorna filas afectadas.
    """
    conn = get_sqlite_connection()

    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def query(sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
    """
    Función compatible con las páginas originales.

    Ejecuta SELECT y retorna varios registros.
    """
    conn = get_sqlite_connection()
    conn.row_factory = sqlite3.Row

    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def query_one(sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
    """
    Función compatible con las páginas originales.

    Ejecuta SELECT y retorna un registro.
    """
    conn = get_sqlite_connection()
    conn.row_factory = sqlite3.Row

    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()

def fetch_df(sql: str, params: tuple | dict = ()):
    """
    Ejecuta un SELECT y retorna el resultado como DataFrame.

    Función de compatibilidad para módulos como leaderboard.py.
    """
    import pandas as pd

    conn = get_sqlite_connection()

    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()