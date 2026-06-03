from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from src.auth import create_user, require_admin
from src.db import execute, fetch_df, fetch_one
from src.navigation import render_sidebar_navigation


require_admin()
render_sidebar_navigation()

st.title("🧪 Pruebas de administrador")
st.caption("Pantalla temporal para crear datos de prueba y validar el funcionamiento de la app.")


# =========================================================
# FUNCIONES AUXILIARES
# =========================================================

def get_teams_df() -> pd.DataFrame:
    return fetch_df("""
        SELECT
            id_equipo,
            nombre,
            grupo,
            codigo_fifa
        FROM equipos
        ORDER BY nombre
    """)


def get_matches_df() -> pd.DataFrame:
    return fetch_df("""
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
            p.api_match_id,
            vp.fecha_apertura,
            vp.fecha_cierre
        FROM partidos p
        INNER JOIN equipos el
            ON p.id_equipo_local = el.id_equipo
        INNER JOIN equipos ev
            ON p.id_equipo_visitante = ev.id_equipo
        LEFT JOIN ventanas_prediccion vp
            ON p.id_partido = vp.id_partido
        ORDER BY p.fecha_hora_partido ASC
    """)


def insert_team(nombre: str, grupo: str, codigo_fifa: str) -> tuple[bool, str]:
    nombre = nombre.strip()
    grupo = grupo.strip() if grupo else None
    codigo_fifa = codigo_fifa.strip().upper()

    if not nombre:
        return False, "El nombre del equipo es obligatorio."

    if not codigo_fifa:
        return False, "El código FIFA es obligatorio."

    try:
        execute("""
            INSERT INTO equipos (
                nombre,
                grupo,
                codigo_fifa
            )
            VALUES (
                :nombre,
                :grupo,
                :codigo_fifa
            )
        """, {
            "nombre": nombre,
            "grupo": grupo,
            "codigo_fifa": codigo_fifa,
        })

        return True, "Equipo creado correctamente."

    except Exception as e:
        error_text = str(e).lower()

        if "unique" in error_text or "duplicate" in error_text:
            return False, "Ya existe un equipo con ese nombre o código FIFA."

        return False, f"Error creando equipo: {e}"


def insert_match(
    fase: str,
    grupo: str | None,
    id_equipo_local: int,
    id_equipo_visitante: int,
    fecha_hora_partido: datetime,
    estado_partido: str,
    goles_local_real: int | None,
    goles_visitante_real: int | None,
    fecha_apertura: datetime,
    fecha_cierre: datetime,
    api_match_id: str,
) -> tuple[bool, str]:
    if id_equipo_local == id_equipo_visitante:
        return False, "El equipo local y visitante no pueden ser el mismo."

    if fecha_apertura >= fecha_cierre:
        return False, "La fecha de apertura debe ser menor que la fecha de cierre."

    api_match_id = api_match_id.strip()

    if not api_match_id:
        return False, "El API Match ID es obligatorio."

    try:
        execute("""
            INSERT INTO partidos (
                fase,
                grupo,
                id_equipo_local,
                id_equipo_visitante,
                fecha_hora_partido,
                estado_partido,
                goles_local_real,
                goles_visitante_real,
                api_match_id
            )
            VALUES (
                :fase,
                :grupo,
                :id_equipo_local,
                :id_equipo_visitante,
                :fecha_hora_partido,
                :estado_partido,
                :goles_local_real,
                :goles_visitante_real,
                :api_match_id
            )
        """, {
            "fase": fase,
            "grupo": grupo,
            "id_equipo_local": id_equipo_local,
            "id_equipo_visitante": id_equipo_visitante,
            "fecha_hora_partido": fecha_hora_partido,
            "estado_partido": estado_partido,
            "goles_local_real": goles_local_real,
            "goles_visitante_real": goles_visitante_real,
            "api_match_id": api_match_id,
        })

        partido = fetch_one("""
            SELECT id_partido
            FROM partidos
            WHERE api_match_id = :api_match_id
        """, {
            "api_match_id": api_match_id,
        })

        if not partido:
            return False, "El partido se insertó, pero no se pudo recuperar su ID."

        id_partido = int(partido["id_partido"])

        execute("""
            INSERT INTO ventanas_prediccion (
                id_partido,
                fecha_apertura,
                fecha_cierre
            )
            VALUES (
                :id_partido,
                :fecha_apertura,
                :fecha_cierre
            )
        """, {
            "id_partido": id_partido,
            "fecha_apertura": fecha_apertura,
            "fecha_cierre": fecha_cierre,
        })

        return True, "Partido creado correctamente."

    except Exception as e:
        error_text = str(e).lower()

        if "unique" in error_text or "duplicate" in error_text:
            return False, "Ya existe un partido con ese API Match ID o una ventana asociada."

        return False, f"Error creando partido: {e}"


def update_match_result(
    id_partido: int,
    estado_partido: str,
    goles_local_real: int | None,
    goles_visitante_real: int | None,
) -> tuple[bool, str]:
    if estado_partido in ("En juego", "Terminado"):
        if goles_local_real is None or goles_visitante_real is None:
            return False, "Para partidos en juego o terminados debes ingresar marcador real."

    try:
        execute("""
            UPDATE partidos
            SET
                estado_partido = :estado_partido,
                goles_local_real = :goles_local_real,
                goles_visitante_real = :goles_visitante_real
            WHERE id_partido = :id_partido
        """, {
            "estado_partido": estado_partido,
            "goles_local_real": goles_local_real,
            "goles_visitante_real": goles_visitante_real,
            "id_partido": id_partido,
        })

        return True, "Resultado actualizado correctamente."

    except Exception as e:
        return False, f"Error actualizando resultado: {e}"


# =========================================================
# TABS
# =========================================================

tab_usuarios, tab_equipos, tab_partidos, tab_resultados = st.tabs([
    "Crear usuario",
    "Crear equipo",
    "Crear partido",
    "Actualizar resultado",
])


# =========================================================
# TAB: CREAR USUARIO
# =========================================================

with tab_usuarios:
    st.subheader("Crear usuario de prueba")

    with st.form("form_crear_usuario_admin_test"):
        usuario = st.text_input("Usuario único")
        nombre = st.text_input("Nombre")
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


# =========================================================
# TAB: CREAR EQUIPO
# =========================================================

with tab_equipos:
    st.subheader("Crear equipo")

    with st.form("form_crear_equipo"):
        nombre_equipo = st.text_input("Nombre del equipo")
        grupo_equipo = st.text_input("Grupo", placeholder="A, B, C...")
        codigo_fifa = st.text_input("Código FIFA", max_chars=3, placeholder="COL")

        submitted = st.form_submit_button("Crear equipo")

    if submitted:
        ok, mensaje = insert_team(
            nombre=nombre_equipo,
            grupo=grupo_equipo,
            codigo_fifa=codigo_fifa,
        )

        if ok:
            st.success(mensaje)
            st.rerun()
        else:
            st.error(mensaje)

    st.divider()
    st.subheader("Equipos registrados")

    equipos_df = get_teams_df()

    if equipos_df.empty:
        st.info("No hay equipos registrados.")
    else:
        st.dataframe(
            equipos_df,
            use_container_width=True,
            hide_index=True,
        )


# =========================================================
# TAB: CREAR PARTIDO
# =========================================================

with tab_partidos:
    st.subheader("Crear partido de prueba")

    equipos_df = get_teams_df()

    if equipos_df.empty:
        st.warning("Primero debes crear equipos.")
    else:
        equipos_options = {
            f"{row['nombre']} ({row['codigo_fifa']})": int(row["id_equipo"])
            for _, row in equipos_df.iterrows()
        }

        now = datetime.now()

        with st.form("form_crear_partido"):
            fase = st.selectbox(
                "Fase",
                [
                    "Fase de Grupos",
                    "Dieciseisavos",
                    "Octavos",
                    "Cuartos",
                    "Semifinal",
                    "Tercer Puesto",
                    "Final",
                ],
            )

            grupo = st.text_input("Grupo", placeholder="Opcional")

            equipo_local_label = st.selectbox(
                "Equipo local",
                list(equipos_options.keys()),
                key="crear_partido_local",
            )

            equipo_visitante_label = st.selectbox(
                "Equipo visitante",
                list(equipos_options.keys()),
                key="crear_partido_visitante",
            )

            fecha_partido_date = st.date_input(
                "Fecha del partido",
                value=now.date(),
            )

            fecha_partido_time = st.time_input(
                "Hora del partido",
                value=(now + timedelta(hours=2)).time().replace(second=0, microsecond=0),
            )

            estado_partido = st.selectbox(
                "Estado del partido",
                ["Sin comenzar", "En juego", "Terminado"],
            )

            col_gl, col_gv = st.columns(2)

            with col_gl:
                goles_local_real = st.number_input(
                    "Goles reales local",
                    min_value=0,
                    max_value=99,
                    value=0,
                    step=1,
                )

            with col_gv:
                goles_visitante_real = st.number_input(
                    "Goles reales visitante",
                    min_value=0,
                    max_value=99,
                    value=0,
                    step=1,
                )

            ventana_tipo = st.selectbox(
                "Tipo de ventana",
                [
                    "Abierta ahora",
                    "Cerrada",
                    "Futura",
                    "Personalizada",
                ],
            )

            if ventana_tipo == "Personalizada":
                fecha_apertura_date = st.date_input(
                    "Fecha apertura",
                    value=now.date(),
                    key="fecha_apertura_custom_date",
                )

                fecha_apertura_time = st.time_input(
                    "Hora apertura",
                    value=(now - timedelta(hours=1)).time().replace(second=0, microsecond=0),
                    key="fecha_apertura_custom_time",
                )

                fecha_cierre_date = st.date_input(
                    "Fecha cierre",
                    value=now.date(),
                    key="fecha_cierre_custom_date",
                )

                fecha_cierre_time = st.time_input(
                    "Hora cierre",
                    value=(now + timedelta(hours=1)).time().replace(second=0, microsecond=0),
                    key="fecha_cierre_custom_time",
                )
            else:
                fecha_apertura_date = None
                fecha_apertura_time = None
                fecha_cierre_date = None
                fecha_cierre_time = None

            api_match_id = st.text_input(
                "API Match ID",
                value=f"TEST_{int(datetime.now().timestamp())}",
            )

            submitted = st.form_submit_button("Crear partido")

        if submitted:
            fecha_hora_partido = datetime.combine(fecha_partido_date, fecha_partido_time)

            if ventana_tipo == "Abierta ahora":
                fecha_apertura = now - timedelta(hours=1)
                fecha_cierre = now + timedelta(hours=1)
            elif ventana_tipo == "Cerrada":
                fecha_apertura = now - timedelta(days=1)
                fecha_cierre = now - timedelta(minutes=30)
            elif ventana_tipo == "Futura":
                fecha_apertura = now + timedelta(days=1)
                fecha_cierre = now + timedelta(days=2)
            else:
                fecha_apertura = datetime.combine(fecha_apertura_date, fecha_apertura_time)
                fecha_cierre = datetime.combine(fecha_cierre_date, fecha_cierre_time)

            goles_local = int(goles_local_real) if estado_partido in ("En juego", "Terminado") else None
            goles_visitante = int(goles_visitante_real) if estado_partido in ("En juego", "Terminado") else None

            ok, mensaje = insert_match(
                fase=fase,
                grupo=grupo.strip() if grupo.strip() else None,
                id_equipo_local=equipos_options[equipo_local_label],
                id_equipo_visitante=equipos_options[equipo_visitante_label],
                fecha_hora_partido=fecha_hora_partido,
                estado_partido=estado_partido,
                goles_local_real=goles_local,
                goles_visitante_real=goles_visitante,
                fecha_apertura=fecha_apertura,
                fecha_cierre=fecha_cierre,
                api_match_id=api_match_id,
            )

            if ok:
                st.success(mensaje)
                st.rerun()
            else:
                st.error(mensaje)

    st.divider()
    st.subheader("Partidos registrados")

    matches_df = get_matches_df()

    if matches_df.empty:
        st.info("No hay partidos registrados.")
    else:
        st.dataframe(
            matches_df,
            use_container_width=True,
            hide_index=True,
        )


# =========================================================
# TAB: ACTUALIZAR RESULTADO
# =========================================================

with tab_resultados:
    st.subheader("Actualizar resultado de partido")

    matches_df = get_matches_df()

    if matches_df.empty:
        st.info("No hay partidos registrados.")
    else:
        match_options = {
            f"{row['id_partido']} - {row['equipo_local']} vs {row['equipo_visitante']} ({row['estado_partido']})": int(row["id_partido"])
            for _, row in matches_df.iterrows()
        }

        selected_label = st.selectbox(
            "Selecciona partido",
            list(match_options.keys()),
        )

        selected_id = match_options[selected_label]

        current = matches_df[matches_df["id_partido"] == selected_id].iloc[0]

        with st.form("form_actualizar_resultado"):
            estado = st.selectbox(
                "Estado",
                ["Sin comenzar", "En juego", "Terminado"],
                index=["Sin comenzar", "En juego", "Terminado"].index(current["estado_partido"]),
            )

            col1, col2 = st.columns(2)

            with col1:
                goles_local = st.number_input(
                    "Goles reales local",
                    min_value=0,
                    max_value=99,
                    value=int(current["goles_local_real"]) if pd.notna(current["goles_local_real"]) else 0,
                    step=1,
                )

            with col2:
                goles_visitante = st.number_input(
                    "Goles reales visitante",
                    min_value=0,
                    max_value=99,
                    value=int(current["goles_visitante_real"]) if pd.notna(current["goles_visitante_real"]) else 0,
                    step=1,
                )

            submitted = st.form_submit_button("Actualizar resultado")

        if submitted:
            goles_local_value = int(goles_local) if estado in ("En juego", "Terminado") else None
            goles_visitante_value = int(goles_visitante) if estado in ("En juego", "Terminado") else None

            ok, mensaje = update_match_result(
                id_partido=selected_id,
                estado_partido=estado,
                goles_local_real=goles_local_value,
                goles_visitante_real=goles_visitante_value,
            )

            if ok:
                st.success(mensaje)
                st.rerun()
            else:
                st.error(mensaje)