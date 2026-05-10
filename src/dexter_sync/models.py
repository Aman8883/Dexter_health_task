"""Internal data models.

Resident is the internal representation persisted to the repository.
SyncResult summarizes a sync run.

The provider's payload schema is documented in `docs/PROVIDER_API.md` —
read it before extending the mapping below.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from dexter_sync.exceptions import MalformedRecordError


class Resident(BaseModel):
    """Internal resident record."""

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    provider_id: str
    full_name: str
    date_of_birth: date | None = None
    room: str | None = None
    care_level: int | None = None
    updated_at: datetime
    is_active: bool = True

    @classmethod
    def from_provider_payload(cls, raw: dict[str, Any]) -> "Resident":
        """Map a raw provider payload into the internal Resident model."""
        provider_id = raw.get("residentId")
        if not provider_id:
            raise MalformedRecordError("missing residentId", raw=raw)

        # Name Mapping:
        first_name = str(raw.get("first_name", "")).strip()
        # API is inconsistent with last name keys, so we check both "lastName" and "last_name"
        last_name = str(raw.get("lastName") or raw.get("last_name") or "").strip()
        
        full_name = f"{first_name} {last_name}".strip()

         # Care level normalization: int, "3", or "level_3" (case-insensitive)
        raw_care_level = raw.get("care_level")
        care_level = None
        if raw_care_level is not None:
            if isinstance(raw_care_level, int):
                care_level = raw_care_level
            elif isinstance(raw_care_level, str):
                val = raw_care_level.lower()
                if val.startswith("level_"):
                    val = val.replace("level_", "", 1)
                try:
                    care_level = int(val)
                except ValueError:
                    raise MalformedRecordError(f"invalid care_level: {raw_care_level}", raw=raw)
            else:
                raise MalformedRecordError(f"unexpected care_level type: {type(raw_care_level)}", raw=raw)
            
        # DOB mapping
        dob_str = raw.get("dob")
        date_of_birth = None
        if dob_str:
            try:
                date_of_birth = date.fromisoformat(dob_str)
            except ValueError:
                raise MalformedRecordError(f"invalid dob format: {dob_str}", raw=raw)
            
         # Active status: deleted_at (when set) supersedes is_active
        is_active = raw.get("is_active", True)
        deleted_at = raw.get("deleted_at")
        if deleted_at:
            is_active = False

        # Updated at: canonical staleness key
        try:
            updated_at = datetime.fromisoformat(raw["last_updated"])
        except (KeyError, ValueError) as e:
            raise MalformedRecordError(f"invalid or missing last_updated", raw=raw)

        return cls(
            provider_id=str(provider_id),
            full_name=full_name,
            date_of_birth=date_of_birth,
            room=raw.get("room"),
            care_level=care_level,
            updated_at=updated_at,
            is_active=is_active,
        )


class SyncResult(BaseModel):
    """Outcome of a sync run."""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def total_processed(self) -> int:
        return self.created + self.updated + self.skipped + self.failed
