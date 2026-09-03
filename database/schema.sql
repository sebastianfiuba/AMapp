PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS dispositivos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE
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
    UNIQUE(campana_id, archivo)
);

CREATE TABLE IF NOT EXISTS puntos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicion_id INTEGER NOT NULL REFERENCES mediciones(id) ON DELETE CASCADE,
    v REAL NOT NULL,
    i REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS analisis_ztc (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campana_id INTEGER NOT NULL REFERENCES campanas(id) ON DELETE CASCADE,
    vt_ztc REAL NOT NULL,
    i_ztc REAL NOT NULL,
    UNIQUE(campana_id)
);
