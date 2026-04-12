from pydantic import BaseModel, Field, field_validator


class EqSettingsRequest(BaseModel):
    preset: str | None = Field(
        default=None,
        max_length=50,
    )
    bands: list[float]

    @field_validator("bands")
    @classmethod
    def validate_bands(
        cls,
        value: list[float],
    ) -> list[float]:
        if len(value) != 8:
            raise ValueError("bands must have 8 values")
        for band in value:
            if not (-12 <= band <= 12):
                raise ValueError(
                    "each band must be between -12 and 12"
                )
        return value


class EqSettingsResponse(BaseModel):
    preset: str | None
    bands: list[float]
