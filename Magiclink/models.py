from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class LocationIn(BaseModel):
    lat: Optional[float] = Field(default=None)
    lng: Optional[float] = Field(default=None)
    accuracy: Optional[float] = Field(default=None)
    timestamp: Optional[int] = Field(default=None, description="ms since epoch from browser")
    address: Optional[str] = Field(default=None)
    denied: Optional[bool] = Field(default=None)
    timeout: Optional[bool] = Field(default=None)
    user_agent: Optional[str] = Field(default=None)

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if not (-90.0 <= value <= 90.0):
            raise ValueError("lat must be between -90 and 90")
        return value

    @field_validator("lng")
    @classmethod
    def validate_lng(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if not (-180.0 <= value <= 180.0):
            raise ValueError("lng must be between -180 and 180")
        return value


class TokenOut(BaseModel):
    token: str
    exp: int
    jti: str


class ApiResponse(BaseModel):
    status: str
    idempotent: Optional[bool] = None
    reason: Optional[str] = None
    sid: Optional[str] = None 