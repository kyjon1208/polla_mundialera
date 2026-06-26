from __future__ import annotations

import streamlit as st

from src.auth import require_login
from src.navigation import render_sidebar_navigation
from src.predictions import (
    delete_admin_predictions,
    ensure_default_predictions_for_all_participants,
    get_available_matches,
    lock_expired_predictions,
    save_prediction,
)


require_login()
render_sidebar_navigation()


user = st.session_state.get("user")

if user is None:
    st.error("No se encontró información del usuario en sesión.")
    st.stop()


st.title("📝 Predicciones")
st.caption("Registra tus marcadores. Una vez confirmados, no podrán modificarse.")


# =========================================================
# BLOQUEO PARA ADMIN
# =========================================================

if user.get("rol") != "participante":
    st.info("El administrador puede visualizar el sistema, pero no participa en la polla.")
    st.stop()


# =========================================================
# ACTUALIZAR BLOQUEOS Y 0-0
# =========================================================

lock_expired_predictions()

if "predicciones_default_aseguradas" not in st.session_state:
    delete_admin_predictions()
    ensure_default_predictions_for_all_participants()

    st.session_state["predicciones_default_aseguradas"] = True


# =========================================================
# FUNCIONES AUXILIARES
# =========================================================

def get_prediction_state_key(id_partido: int, side: str) -> str:
    return f"prediccion_{user['id_usuario']}_{id_partido}_{side}"


def initialize_prediction_state(
    id_partido: int,
    goles_local: int,
    goles_visitante: int,
) -> None:
    """
    Inicializa el borrador solo si no existe en session_state.

    Esto evita que al guardar un partido se borren los borradores
    que el usuario ya había escrito en otros partidos.
    """
    key_local = get_prediction_state_key(id_partido, "local")
    key_visitante = get_prediction_state_key(id_partido, "visitante")

    if key_local not in st.session_state:
        st.session_state[key_local] = int(goles_local)

    if key_visitante not in st.session_state:
        st.session_state[key_visitante] = int(goles_visitante)


def clear_prediction_state_for_match(id_partido: int) -> None:
    """
    Limpia solo las llaves del partido confirmado.
    No toca los borradores de otros partidos.
    """
    key_local = get_prediction_state_key(id_partido, "local")
    key_visitante = get_prediction_state_key(id_partido, "visitante")

    st.session_state.pop(key_local, None)
    st.session_state.pop(key_visitante, None)


def set_pending_confirmation(id_partido: int) -> None:
    st.session_state["pending_prediction_confirm"] = id_partido


def clear_pending_confirmation() -> None:
    st.session_state.pop("pending_prediction_confirm", None)


def get_pending_confirmation() -> int | None:
    value = st.session_state.get("pending_prediction_confirm")

    if value is None:
        return None

    try:
        return int(value)
    except Exception:
        return None


# =========================================================
# CARGA DE PARTIDOS
# =========================================================

matches = get_available_matches(user["id_usuario"])

if matches is None or matches.empty:
    st.info("No hay partidos con ambos equipos definidos para registrar predicciones.")
    st.stop()


st.info(
    "Todos los partidos con ambos equipos definidos están disponibles para predecir. "
    "Cada partido se bloquea automáticamente a las 00:00 del día del partido, hora Colombia. "
    "Si no registras marcador antes del cierre, jugarás con 0-0 por defecto."
)


# =========================================================
# LISTADO DE PARTIDOS
# =========================================================

pending_confirmation = get_pending_confirmation()

for _, match in matches.iterrows():
    id_partido = int(match["id_partido"])

    equipo_local = match["equipo_local"]
    equipo_visitante = match["equipo_visitante"]

    goles_local_actual = int(match["goles_local_predicho"])
    goles_visitante_actual = int(match["goles_visitante_predicho"])

    puede_editar = int(match["puede_editar"]) == 1
    ya_registro = int(match["ya_registro"]) == 1
    estado_ventana = match["estado_ventana"]

    initialize_prediction_state(
        id_partido=id_partido,
        goles_local=goles_local_actual,
        goles_visitante=goles_visitante_actual,
    )

    key_local = get_prediction_state_key(id_partido, "local")
    key_visitante = get_prediction_state_key(id_partido, "visitante")

    with st.container(border=True):
        col_info, col_pred = st.columns([2, 1])

        with col_info:
            st.markdown(f"### {equipo_local} vs {equipo_visitante}")

            st.write(f"**Fase:** {match['fase']}")
            st.write(f"**Grupo:** {match['grupo'] if match['grupo'] else 'N/A'}")
            st.write(f"**Fecha partido:** {match['fecha_hora_partido']}")
            st.write(f"**Estado partido:** {match['estado_partido']}")
            st.write(f"**Estado predicción:** {estado_ventana}")
            st.write(f"**Cierre automático:** {match['fecha_cierre_automatica']}")

            if match["goles_local_real"] is not None and match["goles_visitante_real"] is not None:
                st.write(
                    f"**Resultado real:** "
                    f"{equipo_local} {match['goles_local_real']} - "
                    f"{match['goles_visitante_real']} {equipo_visitante}"
                )

        with col_pred:
            st.markdown("#### Tu predicción")

            col_local, col_visitante = st.columns(2)

            with col_local:
                st.number_input(
                    label=equipo_local,
                    min_value=0,
                    max_value=99,
                    step=1,
                    key=key_local,
                    disabled=not puede_editar,
                )

            with col_visitante:
                st.number_input(
                    label=equipo_visitante,
                    min_value=0,
                    max_value=99,
                    step=1,
                    key=key_visitante,
                    disabled=not puede_editar,
                )

            marcador_local = int(st.session_state[key_local])
            marcador_visitante = int(st.session_state[key_visitante])

            st.write(
                f"Marcador seleccionado: **{equipo_local} {marcador_local} - "
                f"{marcador_visitante} {equipo_visitante}**"
            )

            if ya_registro:
                st.success("Predicción registrada. No se puede modificar.")

            elif estado_ventana == "Cerrada":
                st.warning("La predicción está cerrada. Si no registraste marcador, aplica 0-0.")

            else:
                if pending_confirmation == id_partido:
                    st.warning(
                        "¿Está seguro que quiere confirmar? "
                        "Una vez hecho no se pueden modificar los marcadores."
                    )

                    st.write(
                        f"Vas a confirmar: **{equipo_local} {marcador_local} - "
                        f"{marcador_visitante} {equipo_visitante}**"
                    )

                    col_yes, col_no = st.columns(2)

                    with col_yes:
                        if st.button(
                            "Sí, confirmar",
                            key=f"confirmar_definitivo_{id_partido}",
                            type="primary",
                        ):
                            ok, mensaje = save_prediction(
                                id_usuario=user["id_usuario"],
                                id_partido=id_partido,
                                goles_local_predicho=marcador_local,
                                goles_visitante_predicho=marcador_visitante,
                            )

                            if ok:
                                clear_pending_confirmation()
                                clear_prediction_state_for_match(id_partido)
                                st.success(mensaje)
                                st.rerun()
                            else:
                                st.error(mensaje)

                    with col_no:
                        st.button(
                            "Cancelar",
                            key=f"cancelar_confirmacion_{id_partido}",
                            on_click=clear_pending_confirmation,
                        )

                else:
                    st.button(
                        "Confirmar predicción",
                        key=f"abrir_confirmacion_{id_partido}",
                        disabled=not puede_editar,
                        on_click=set_pending_confirmation,
                        args=(id_partido,),
                    )