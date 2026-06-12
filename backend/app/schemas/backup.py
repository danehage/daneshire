from pydantic import BaseModel, ConfigDict


class BackupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    success: bool
    filename: str
    gcs_path: str
    size_bytes: int
    duration_seconds: float
    error: str | None = None
