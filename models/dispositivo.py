from dataclasses import dataclass


@dataclass(frozen=True)
class Dispositivo:
    id: int
    nombre: str
