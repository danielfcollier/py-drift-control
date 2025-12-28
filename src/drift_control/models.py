from pydantic import BaseModel, Field, field_validator
from typing import Optional

class DesiredState(BaseModel):
    app_name: str = Field(..., description="Unique identifier for the workload")
    image: str = Field(..., description="Docker image tag to enforce")
    status: str = Field("running", pattern="^(running|stopped)$")
    host_port: int = Field(..., ge=1, le=65535, description="Primary public port")
    fallback_host_port: Optional[int] = Field(None, ge=1, le=65535, description="Backup port if primary is taken")
    container_port: int = Field(..., ge=1, le=65535, description="Internal container port")

    @field_validator("image")
    @classmethod
    def validate_image_tag(cls, v: str) -> str:
        if ":" not in v: return f"{v}:latest"
        return v