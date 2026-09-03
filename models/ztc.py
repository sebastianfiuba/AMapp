from dataclasses import dataclass


@dataclass(frozen=True)
class ResultadoZTC:
    vt_ztc: float
    i_ztc: float
    cantidad_mediciones: int
