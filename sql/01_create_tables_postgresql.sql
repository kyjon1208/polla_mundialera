CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario BIGSERIAL PRIMARY KEY,
    usuario VARCHAR(80) NOT NULL UNIQUE,
    clave_hash TEXT NOT NULL,
    nombre VARCHAR(150) NOT NULL,
    rol VARCHAR(30) NOT NULL CHECK (rol IN ('admin', 'participante')),
    estado_activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS equipos (
    id_equipo BIGSERIAL PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL UNIQUE,
    grupo VARCHAR(10),
    codigo_fifa VARCHAR(10) UNIQUE
);

CREATE TABLE IF NOT EXISTS partidos (
    id_partido BIGSERIAL PRIMARY KEY,
    fase VARCHAR(40) NOT NULL,
    grupo VARCHAR(10),
    id_equipo_local BIGINT NOT NULL REFERENCES equipos(id_equipo),
    id_equipo_visitante BIGINT NOT NULL REFERENCES equipos(id_equipo),
    fecha_hora_partido TIMESTAMP NOT NULL,
    estado_partido VARCHAR(30) NOT NULL DEFAULT 'Sin comenzar' CHECK (estado_partido IN ('Sin comenzar', 'En juego', 'Terminado')),
    goles_local_real INTEGER,
    goles_visitante_real INTEGER,
    api_match_id VARCHAR(100) UNIQUE
);

CREATE TABLE IF NOT EXISTS ventanas_prediccion (
    id_ventana BIGSERIAL PRIMARY KEY,
    id_partido BIGINT NOT NULL UNIQUE REFERENCES partidos(id_partido),
    fecha_apertura TIMESTAMP NOT NULL,
    fecha_cierre TIMESTAMP NOT NULL,
    CONSTRAINT chk_ventana_prediccion CHECK (fecha_cierre > fecha_apertura)
);

CREATE TABLE IF NOT EXISTS predicciones (
    id_prediccion BIGSERIAL PRIMARY KEY,
    id_usuario BIGINT NOT NULL REFERENCES usuarios(id_usuario),
    id_partido BIGINT NOT NULL REFERENCES partidos(id_partido),
    goles_local_predicho INTEGER NOT NULL DEFAULT 0 CHECK (goles_local_predicho >= 0),
    goles_visitante_predicho INTEGER NOT NULL DEFAULT 0 CHECK (goles_visitante_predicho >= 0),
    fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    bloqueada BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (id_usuario, id_partido)
);

CREATE TABLE IF NOT EXISTS criterios_puntuacion (
    id_criterio BIGSERIAL PRIMARY KEY,
    nombre_criterio VARCHAR(120) NOT NULL,
    fase VARCHAR(40) NOT NULL,
    puntos INTEGER NOT NULL CHECK (puntos >= 0),
    UNIQUE (nombre_criterio, fase)
);

CREATE TABLE IF NOT EXISTS puntajes_partido (
    id_puntaje BIGSERIAL PRIMARY KEY,
    id_usuario BIGINT NOT NULL REFERENCES usuarios(id_usuario),
    id_partido BIGINT NOT NULL REFERENCES partidos(id_partido),
    criterio_aplicado VARCHAR(120) NOT NULL,
    puntos INTEGER NOT NULL DEFAULT 0,
    marcador_completo INTEGER NOT NULL DEFAULT 0,
    acierto_ganador_empate INTEGER NOT NULL DEFAULT 0,
    diferencia_directa INTEGER NOT NULL DEFAULT 0,
    fecha_calculo TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id_usuario, id_partido)
);

CREATE TABLE IF NOT EXISTS configuracion (
    clave VARCHAR(100) PRIMARY KEY,
    valor TEXT NOT NULL,
    descripcion TEXT
);
