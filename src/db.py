from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool


DEFAULT_DB_PATH = "polla_mundialera.db"


def get_secret_value(key: str, default=None):
    try:
        return st.secrets.get(key, default)
    except FileNotFoundError:
        return default
    except Exception:
        return default


def get_db_mode() -> str:
    return str(get_secret_value("APP_DB_MODE", "sqlite")).lower()


def get_sqlite_db_path() -> str:
    return str(get_secret_value("SQLITE_DB_PATH", DEFAULT_DB_PATH))


def get_database_url() -> str:
    url = get_secret_value("DATABASE_URL", None)

    if not url:
        raise ValueError("No existe DATABASE_URL en secrets.toml o Streamlit Secrets.")

    return str(url)


def get_sqlite_connection() -> sqlite3.Connection:
    db_path = get_sqlite_db_path()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def get_postgres_engine():
    database_url = get_database_url()

    return create_engine(
        database_url,
        poolclass=NullPool,
    )


def database_exists() -> bool:
    if get_db_mode() == "sqlite":
        return Path(get_sqlite_db_path()).exists()

    return True


def init_sqlite_schema() -> None:
    return None


def fetch_df(sql: str, params: tuple | dict = ()) -> pd.DataFrame:
    db_mode = get_db_mode()

    if db_mode == "sqlite":
        conn = get_sqlite_connection()
        try:
            return pd.read_sql_query(sql, conn, params=params)
        finally:
            conn.close()

    if db_mode == "postgres":
        engine = get_postgres_engine()
        with engine.connect() as conn:
            return pd.read_sql_query(text(sql), conn, params=params)

    raise ValueError(f"Modo de base de datos no soportado: {db_mode}")


def fetch_all(sql: str, params: tuple | dict = ()) -> list:
    db_mode = get_db_mode()

    if db_mode == "sqlite":
        conn = get_sqlite_connection()
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    if db_mode == "postgres":
        engine = get_postgres_engine()
        with engine.connect() as conn:
            result = conn.execute(text(sql), params)
            return result.mappings().all()

    raise ValueError(f"Modo de base de datos no soportado: {db_mode}")


def fetch_one(sql: str, params: tuple | dict = ()):
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple | dict = ()) -> int:
    db_mode = get_db_mode()

    if db_mode == "sqlite":
        conn = get_sqlite_connection()
        try:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    if db_mode == "postgres":
        engine = get_postgres_engine()
        with engine.begin() as conn:
            result = conn.execute(text(sql), params)
            return result.rowcount

    raise ValueError(f"Modo de base de datos no soportado: {db_mode}")


def execute_query(sql: str, params: tuple | dict = ()) -> int:
    return execute(sql, params)


def execute_many(sql: str, params_list: list[tuple] | list[dict]) -> int:
    db_mode = get_db_mode()

    if db_mode == "sqlite":
        conn = get_sqlite_connection()
        try:
            cursor = conn.executemany(sql, params_list)
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    if db_mode == "postgres":
        engine = get_postgres_engine()
        total = 0
        with engine.begin() as conn:
            for params in params_list:
                result = conn.execute(text(sql), params)
                total += result.rowcount
        return total

    raise ValueError(f"Modo de base de datos no soportado: {db_mode}")


def query(sql: str, params: tuple | dict = ()) -> list:
    return fetch_all(sql, params)


def query_one(sql: str, params: tuple | dict = ()):
    return fetch_one(sql, params)


def get_connection():
    """
    Para compatibilidad. En modo SQLite retorna conexión SQLite.
    En modo Postgres no se recomienda usar conexión directa aquí.
    """
    if get_db_mode() == "sqlite":
        return get_sqlite_connection()

    raise ValueError("Usa fetch_df, fetch_all, fetch_one o execute en modo postgres.")