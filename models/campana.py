from dataclasses import dataclass


@dataclass(frozen=True)
class Campana:
    id: int
    dispositivo_id: int
    numero: str
