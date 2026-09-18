PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS dispositivos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    tag TEXT,
    numero TEXT
);

CREATE TABLE IF NOT EXISTS campanas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dispositivo_id INTEGER NOT NULL REFERENCES dispositivos(id) ON DELETE CASCADE,
    numero TEXT NOT NULL,
    UNIQUE(dispositivo_id, numero)
);

CREATE TABLE IF NOT EXISTS mediciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dispositivo_id INTEGER NOT NULL REFERENCES dispositivos(id) ON DELETE CASCADE,
    campana_id INTEGER NOT NULL REFERENCES campanas(id) ON DELETE CASCADE,
    archivo TEXT NOT NULL,
    fecha TEXT,
    descripcion TEXT,
    clase TEXT,
    estado TEXT,
    eliminado INTEGER NOT NULL DEFAULT 0 CHECK(eliminado IN (0, 1)),
    measurement_hash TEXT UNIQUE,
    UNIQUE(campana_id, archivo)
);

CREATE TABLE IF NOT EXISTS puntos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicion_id INTEGER NOT NULL REFERENCES mediciones(id) ON DELETE CASCADE,
    v REAL NOT NULL,
    i REAL NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_puntos_medicion_vi
    ON puntos(medicion_id, v, i);

CREATE TABLE IF NOT EXISTS tracks_vt (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dispositivo_id INTEGER NOT NULL REFERENCES dispositivos(id) ON DELETE CASCADE,
    campana_id INTEGER NOT NULL REFERENCES campanas(id) ON DELETE CASCADE,
    archivo TEXT NOT NULL,
    track_key TEXT NOT NULL,
    canal TEXT NOT NULL,
    fecha TEXT,
    descripcion TEXT,
    source_sheet TEXT,
    UNIQUE(dispositivo_id, track_key)
);

CREATE TABLE IF NOT EXISTS puntos_track_vt (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL REFERENCES tracks_vt(id) ON DELETE CASCADE,
    t REAL NOT NULL,
    vt REAL NOT NULL,
    UNIQUE(track_id, t, vt)
);

CREATE TABLE IF NOT EXISTS vistas_workbench (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    configuracion TEXT NOT NULL,
    creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS datos_sin_clasificar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    archivo_origen TEXT NOT NULL,
    hoja TEXT NOT NULL,
    tipo TEXT NOT NULL,
    filas INTEGER NOT NULL,
    columnas TEXT,
    datos_json TEXT NOT NULL,
    contenido_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS analisis_ztc (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campana_id INTEGER NOT NULL REFERENCES campanas(id) ON DELETE CASCADE,
    vt_ztc REAL NOT NULL,
    i_ztc REAL NOT NULL,
    UNIQUE(campana_id)
);

CREATE TABLE IF NOT EXISTS relaciones_campana (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    anterior_id INTEGER NOT NULL REFERENCES campanas(id) ON DELETE CASCADE,
    siguiente_id INTEGER NOT NULL REFERENCES campanas(id) ON DELETE CASCADE,
    orden INTEGER NOT NULL DEFAULT 1,
    motivo TEXT,
    UNIQUE(anterior_id, siguiente_id),
    CHECK(anterior_id <> siguiente_id)
);

CREATE TABLE IF NOT EXISTS grupos_medicion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS grupo_mediciones (
    grupo_id INTEGER NOT NULL REFERENCES grupos_medicion(id) ON DELETE CASCADE,
    medicion_id INTEGER NOT NULL REFERENCES mediciones(id) ON DELETE CASCADE,
    PRIMARY KEY(grupo_id, medicion_id)
);

CREATE TABLE IF NOT EXISTS grupo_tracks (
    grupo_id INTEGER NOT NULL REFERENCES grupos_medicion(id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES tracks_vt(id) ON DELETE CASCADE,
    PRIMARY KEY(grupo_id, track_id)
);
