from pydantic import BaseModel, ConfigDict


class WeakPointUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolved: bool | None = None
