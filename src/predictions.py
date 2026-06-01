from __future__ import annotations

import pandas as pd

from src.db import execute, fetch_df


# =========================================================
# FUNCIONES AUXILIARES SQL
# =========================================================

def _get_current_timestamp_sql() -> str:
    """
    Devuelve expresión SQL compatible con PostgreSQL.

    En Supabase/PostgreSQL:
    - CURRENT_TIMESTAMP obtiene la fecha y hora actual.
    """
    return "CURRENT_TIMESTAMP"


def _get_match_day_start_sql(column_name: str = "p.fecha_hora_partido") -> str:
    """
    Devuelve la fecha del partido truncada a las 00:00 del mismo día.

    Ejemplo:
    Partido: 2026-06-15 20:00:00
    Resultado: 2026-06-15 00:00:00
    """
    return f"DATE_TRUNC('day', {column_name})"


# =========================================================
# CONSULTA DE PARTIDOS DISPONIBLES
# =========================================================

def get_available_matches(id_usuario: int) -> pd.DataFrame:
    """
    Retorna los partidos visibles para predicción.

    Reglas:
    - El partido se muestra si ya llegó la fecha de apertura.
    - El cierre automático es a las 00:00 del día del partido.
    - Si el usuario ya registró una predicción, no puede editarla.
    - Si no registró y ya cerró el tiempo, juega con 0-0 por defecto.
    """

    sql = """
        SELECT
            p.id_partido,
            p.fase,
            p.grupo,
            el.nombre AS equipo_local,
            ev.nombre AS equipo_visitante,
            p.fecha_hora_partido,
            p.estado_partido,
            p.goles_local_real,
            p.goles_visitante_real,

            vp.fecha_apertura,

            DATE_TRUNC('day', p.fecha_hora_partido) AS fecha_cierre_automatica,

            pr.id_prediccion,
            COALESCE(pr.goles_local_predicho, 0) AS goles_local_predicho,
            COALESCE(pr.goles_visitante_predicho, 0) AS goles_visitante_predicho,
            COALESCE(pr.bloqueada, 0) AS bloqueada,

            CASE
                WHEN pr.id_prediccion IS NOT NULL THEN 1
                ELSE 0
            END AS ya_registro,

            CASE
                WHEN CURRENT_TIMESTAMP < vp.fecha_apertura
                    THEN 'No disponible'

                WHEN CURRENT_TIMESTAMP >= DATE_TRUNC('day', p.fecha_hora_partido)
                    THEN 'Cerrada'

                WHEN pr.id_prediccion IS NOT NULL
                    THEN 'Registrada'

                ELSE 'Abierta'
            END AS estado_ventana,

            CASE
                WHEN CURRENT_TIMESTAMP >= vp.fecha_apertura
                 AND CURRENT_TIMESTAMP < DATE_TRUNC('day', p.fecha_hora_partido)
                 AND pr.id_prediccion IS NULL
                    THEN 1
                ELSE 0
            END AS puede_editar

        FROM partidos p
        INNER JOIN equipos el
            ON p.id_equipo_local = el.id_equipo
        INNER JOIN equipos ev
            ON p.id_equipo_visitante = ev.id_equipo
        INNER JOIN ventanas_prediccion vp
            ON p.id_partido = vp.id_partido
        LEFT JOIN predicciones pr
            ON p.id_partido = pr.id_partido
           AND pr.id_usuario = :id_usuario

        WHERE CURRENT_TIMESTAMP >= vp.fecha_apertura

        ORDER BY
            p.fecha_hora_partido ASC,
            p.id_partido ASC
    """

    return fetch_df(sql, {
        "id_usuario": id_usuario
    })


# =========================================================
# VALIDACIÓN DE GUARDADO
# =========================================================

def can_create_prediction(id_usuario: int, id_partido: int) -> tuple[bool, str]:
    """
    Valida si el usuario puede crear una predicción.

    Reglas:
    - Debe estar dentro del tiempo permitido.
    - El cierre es a las 00:00 del día del partido.
    - Si ya existe predicción, no permite actualizar.
    """

    sql = """
        SELECT
            p.id_partido,
            p.fecha_hora_partido,
            vp.fecha_apertura,
            DATE_TRUNC('day', p.fecha_hora_partido) AS fecha_cierre_automatica,
            pr.id_prediccion,

            CASE
                WHEN CURRENT_TIMESTAMP < vp.fecha_apertura
                    THEN 'La ventana de predicción aún no está abierta.'

                WHEN CURRENT_TIMESTAMP >= DATE_TRUNC('day', p.fecha_hora_partido)
                    THEN 'La predicción ya está cerrada. Solo se podía registrar hasta las 00:00 del día del partido.'

                WHEN pr.id_prediccion IS NOT NULL
                    THEN 'Ya registraste una predicción para este partido y no se puede modificar.'

                ELSE 'OK'
            END AS validacion

        FROM partidos p
        INNER JOIN ventanas_prediccion vp
            ON p.id_partido = vp.id_partido
        LEFT JOIN predicciones pr
            ON p.id_partido = pr.id_partido
           AND pr.id_usuario = :id_usuario
        WHERE p.id_partido = :id_partido
    """

    df = fetch_df(sql, {
        "id_usuario": id_usuario,
        "id_partido": id_partido,
    })

    if df.empty:
        return False, "No se encontró el partido."

    mensaje = str(df.iloc[0]["validacion"])

    if mensaje == "OK":
        return True, "Predicción permitida."

    return False, mensaje


# =========================================================
# GUARDAR PREDICCIÓN
# =========================================================

def save_prediction(
    id_usuario: int,
    id_partido: int,
    goles_local_predicho: int,
    goles_visitante_predicho: int,
) -> tuple[bool, str]:
    """
    Guarda la predicción del usuario.

    Importante:
    - Solo permite INSERT.
    - No permite UPDATE.
    - Una vez registrada, queda bloqueada.
    """

    goles_local_predicho = int(goles_local_predicho)
    goles_visitante_predicho = int(goles_visitante_predicho)

    if goles_local_predicho < 0 or goles_visitante_predicho < 0:
        return False, "Los goles no pueden ser negativos."

    puede_guardar, mensaje = can_create_prediction(
        id_usuario=id_usuario,
        id_partido=id_partido,
    )

    if not puede_guardar:
        return False, mensaje

    sql = """
        INSERT INTO predicciones (
            id_usuario,
            id_partido,
            goles_local_predicho,
            goles_visitante_predicho,
            fecha_registro,
            fecha_actualizacion,
            bloqueada
        )
        VALUES (
            :id_usuario,
            :id_partido,
            :goles_local_predicho,
            :goles_visitante_predicho,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP,
            1
        )
    """

    try:
        execute(sql, {
            "id_usuario": id_usuario,
            "id_partido": id_partido,
            "goles_local_predicho": goles_local_predicho,
            "goles_visitante_predicho": goles_visitante_predicho,
        })

        return True, "Predicción registrada correctamente. Ya no podrá ser modificada."

    except Exception as e:
        error_text = str(e).lower()

        if "unique" in error_text or "duplicate" in error_text:
            return False, "Ya existe una predicción registrada para este partido."

        return False, f"No se pudo guardar la predicción: {e}"


# =========================================================
# PREDICCIONES 0-0 POR DEFECTO
# =========================================================

def ensure_default_predictions(id_usuario: int) -> None:
    """
    Crea predicciones 0-0 por defecto para partidos cuyo tiempo de predicción ya cerró
    y en los cuales el usuario no registró marcador.

    Regla:
    Si el partido es el 15 de junio, desde el 15 de junio a las 00:00
    se crea 0-0 si no existe predicción.
    """

    sql = """
        INSERT INTO predicciones (
            id_usuario,
            id_partido,
            goles_local_predicho,
            goles_visitante_predicho,
            fecha_registro,
            fecha_actualizacion,
            bloqueada
        )
        SELECT
            :id_usuario AS id_usuario,
            p.id_partido,
            0 AS goles_local_predicho,
            0 AS goles_visitante_predicho,
            CURRENT_TIMESTAMP AS fecha_registro,
            CURRENT_TIMESTAMP AS fecha_actualizacion,
            1 AS bloqueada
        FROM partidos p
        INNER JOIN ventanas_prediccion vp
            ON p.id_partido = vp.id_partido
        WHERE CURRENT_TIMESTAMP >= DATE_TRUNC('day', p.fecha_hora_partido)
          AND NOT EXISTS (
                SELECT 1
                FROM predicciones pr
                WHERE pr.id_usuario = :id_usuario
                  AND pr.id_partido = p.id_partido
          )
    """

    execute(sql, {
        "id_usuario": id_usuario
    })


def create_default_predictions_for_closed_matches(id_usuario: int | None = None) -> None:
    """
    Alias de compatibilidad para páginas anteriores.
    """
    if id_usuario is None:
        return

    ensure_default_predictions(id_usuario)


# =========================================================
# BLOQUEO DE PREDICCIONES VENCIDAS
# =========================================================

def lock_expired_predictions() -> None:
    """
    Bloquea predicciones cuando ya llegó la fecha del partido a las 00:00.
    """

    sql = """
        UPDATE predicciones
        SET bloqueada = 1
        WHERE id_partido IN (
            SELECT id_partido
            FROM partidos
            WHERE CURRENT_TIMESTAMP >= DATE_TRUNC('day', fecha_hora_partido)
        )
    """

    execute(sql)


# =========================================================
# CONSULTA DE PREDICCIONES DEL USUARIO
# =========================================================

def get_user_predictions(id_usuario: int) -> pd.DataFrame:
    """
    Retorna todas las predicciones registradas por un usuario.
    """

    sql = """
        SELECT
            pr.id_prediccion,
            pr.id_usuario,
            pr.id_partido,
            p.fase,
            p.grupo,
            el.nombre AS equipo_local,
            ev.nombre AS equipo_visitante,
            p.fecha_hora_partido,
            p.estado_partido,
            pr.goles_local_predicho,
            pr.goles_visitante_predicho,
            pr.fecha_registro,
            pr.fecha_actualizacion,
            pr.bloqueada
        FROM predicciones pr
        INNER JOIN partidos p
            ON pr.id_partido = p.id_partido
        INNER JOIN equipos el
            ON p.id_equipo_local = el.id_equipo
        INNER JOIN equipos ev
            ON p.id_equipo_visitante = ev.id_equipo
        WHERE pr.id_usuario = :id_usuario
        ORDER BY p.fecha_hora_partido ASC
    """

    return fetch_df(sql, {
        "id_usuario": id_usuario
    })