"""Validated structured metadata supplied by vendor manifests and sidecars."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StructuredSourceMetadata(BaseModel):
    """Small common schema plus bounded vendor-specific attributes."""

    model_config = ConfigDict(from_attributes=True)

    metadata_formats: list[str] = Field(min_length=1)
    metadata_source_refs: list[str] = Field(min_length=1)
    external_asset_id: str | None = None
    title: str | None = None
    description: str | None = None
    primary_category: str | None = None
    tags: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    brand: str | None = None
    contributor_id: str | None = None
    additional_metadata: dict[str, Any] = Field(default_factory=dict)

    def to_orm_dict(self) -> dict:
        return self.model_dump()

    def to_event_dict(self) -> dict:
        return self.model_dump(mode="json")
