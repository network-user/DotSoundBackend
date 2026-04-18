from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class ComponentHealth(BaseModel):
    status: str
    detail: str | None = None
    latency_ms: float | None = None


class DeepHealthResponse(BaseModel):
    status: str
    components: dict[str, ComponentHealth]


class ErrorResponse(BaseModel):
    detail: str
