PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT NOT NULL UNIQUE,
    clave_hash TEXT NOT NULL,
    nombre TEXT NOT NULL,
    rol TEXT NOT NULL CHECK (rol IN ('admin', 'participante')),
    estado_activo INTEGER NOT NULL DEFAULT 1,
    fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS equipos (
    id_equipo INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    grupo TEXT,
    codigo_fifa TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS partidos (
    id_partido INTEGER PRIMARY KEY AUTOINCREMENT,
    fase TEXT NOT NULL,
    grupo TEXT,
    id_equipo_local INTEGER NOT NULL,
    id_equipo_visitante INTEGER NOT NULL,
    fecha_hora_partido TEXT NOT NULL,
    estado_partido TEXT NOT NULL DEFAULT 'Sin comenzar' CHECK (estado_partido IN ('Sin comenzar', 'En juego', 'Terminado')),
    goles_local_real INTEGER,
    goles_visitante_real INTEGER,
    api_match_id TEXT UNIQUE,
    FOREIGN KEY (id_equipo_local) REFERENCES equipos(id_equipo),
    FOREIGN KEY (id_equipo_visitante) REFERENCES equipos(id_equipo)
);

CREATE TABLE IF NOT EXISTS ventanas_prediccion (
    id_ventana INTEGER PRIMARY KEY AUTOINCREMENT,
    id_partido INTEGER NOT NULL UNIQUE,
    fecha_apertura TEXT NOT NULL,
    fecha_cierre TEXT NOT NULL,
    FOREIGN KEY (id_partido) REFERENCES partidos(id_partido)
);

CREATE TABLE IF NOT EXISTS predicciones (
    id_prediccion INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario INTEGER NOT NULL,
    id_partido INTEGER NOT NULL,
    goles_local_predicho INTEGER NOT NULL DEFAULT 0,
    goles_visitante_predicho INTEGER NOT NULL DEFAULT 0,
    fecha_registro TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    bloqueada INTEGER NOT NULL DEFAULT 0,
    UNIQUE (id_usuario, id_partido),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario),
    FOREIGN KEY (id_partido) REFERENCES partidos(id_partido)
);

CREATE TABLE IF NOT EXISTS criterios_puntuacion (
    id_criterio INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_criterio TEXT NOT NULL,
    fase TEXT NOT NULL,
    puntos INTEGER NOT NULL,
    UNIQUE (nombre_criterio, fase)
);

CREATE TABLE IF NOT EXISTS puntajes_partido (
    id_puntaje INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario INTEGER NOT NULL,
    id_partido INTEGER NOT NULL,
    criterio_aplicado TEXT NOT NULL,
    puntos INTEGER NOT NULL DEFAULT 0,
    marcador_completo INTEGER NOT NULL DEFAULT 0,
    acierto_ganador_empate INTEGER NOT NULL DEFAULT 0,
    diferencia_directa INTEGER NOT NULL DEFAULT 0,
    fecha_calculo TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id_usuario, id_partido),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario),
    FOREIGN KEY (id_partido) REFERENCES partidos(id_partido)
);

CREATE TABLE IF NOT EXISTS configuracion (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL,
    descripcion TEXT
);
