from dataclasses import dataclass, field
from datetime import datetime, timezone


def agora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Registro:
    fonte: str
    id_fonte: str
    nome: str
    cidade: str | None = None
    uf: str | None = None
    lat: float | None = None
    lon: float | None = None
    capacidade: int | None = None
    tipo_capacidade: str | None = None
    site: str | None = None
    telefone: str | None = None
    endereco: str | None = None
    url_fonte: str | None = None
    coletado_em: str = field(default_factory=agora)
