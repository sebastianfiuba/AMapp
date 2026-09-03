from dataclasses import dataclass


@dataclass(frozen=True)
class Medicion:
    id: int
    dispositivo_id: int
    campana_id: int
    archivo: str
    fecha: str = ""
    descripcion: str = ""
    clase: str = "normal"
    estado: str = "nada"
