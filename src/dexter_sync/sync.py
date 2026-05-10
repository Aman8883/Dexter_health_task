"""Sync orchestrator.

Reads residents from a provider, writes them to a repository, and returns a
SyncResult describing what happened. The current implementation handles the
simplest case only — extend it.

Read `docs/PROVIDER_API.md` and the failing tests to understand what
production-quality means here.
"""
from __future__ import annotations

import time

from dexter_sync.exceptions import (
    MalformedRecordError,
    PermanentProviderError,
    ProviderError,
    RateLimitError,
    TransientProviderError,
)
from dexter_sync.models import Resident, SyncResult
from dexter_sync.provider_client import MockCareProvider
from dexter_sync.repository import InMemoryRepository

MAX_RETRIES = 3


def run_sync(
    provider: MockCareProvider,
    repository: InMemoryRepository,
) -> SyncResult:
    """Sync residents from the provider into the repository."""
    result = SyncResult()
    cursor = None
    seen_cursors = set()

    while True:
        # Loop trap protection: guard against providers returning the same cursor
        if cursor in seen_cursors:
            result.errors.append(f"Infinite loop detected at cursor: {cursor}")
            break
        seen_cursors.add(cursor)

        page_data = None
        attempts = 0
        while True:
            try:
                page_data = provider.list_residents(cursor=cursor)
                break
            except RateLimitError as e:
                attempts += 1
                if attempts > MAX_RETRIES:
                    result.errors.append(f"Max retries exceeded for rate limit at cursor {cursor}")
                    return result
                # Honor retry_after if present, but cap it to keep tests fast
                wait_time = min(getattr(e, "retry_after", 0), 1.0)
                if wait_time > 0:
                    time.sleep(wait_time)
            except TransientProviderError as e:
                attempts += 1
                if attempts > MAX_RETRIES:
                    result.errors.append(f"Max retries exceeded for transient error at cursor {cursor}")
                    return result
                # Small exponential backoff capped at 1s
                wait_time = min(0.1 * (2 ** (attempts - 1)), 1.0)
                time.sleep(wait_time)
            except PermanentProviderError as e:
                result.errors.append(f"Permanent provider error at cursor {cursor}: {e}")
                return result
            except ProviderError as e:
                result.errors.append(f"Provider error at cursor {cursor}: {e}")
                return result

        if page_data is None:
            break

        raw_residents = page_data.get("residents", [])
        for raw in raw_residents:
            try:
                incoming = Resident.from_provider_payload(raw)

                existing = repository.get_resident(incoming.provider_id)
                if existing:
                    # Stale-write protection: only update if incoming data is newer.
                    # We treat equal timestamps as 'skipped' (idempotent/no-op).
                    if incoming.updated_at > existing.updated_at:
                        repository.upsert_resident(incoming)
                        result.updated += 1
                    else:
                        result.skipped += 1
                else:
                    repository.upsert_resident(incoming)
                    result.created += 1

            except MalformedRecordError as e:
                result.failed += 1
                result.errors.append(f"Malformed record: {e}")
            except Exception as e:
                result.failed += 1
                result.errors.append(f"Unexpected error processing record: {e}")

        cursor = page_data.get("next_cursor")
        if cursor is None:
            break

    return result
