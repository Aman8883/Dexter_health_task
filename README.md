# Backend Assignment: Provider Sync Reliability Challenge

## Context

At Dexter Health, our backend connects with third-party healthcare software
providers and synchronizes operational care data into our internal systems.

In this assignment, you will work with a small existing Python codebase that
simulates a resident data sync from a third-party provider into a Firestore-like
repository.

The current implementation is a thin happy-path skeleton. Your job is to make
it production-grade enough to be trusted with real care data.

## Setup

Python 3.11 or newer required. On macOS and many Linux distros the system
`python3` is older than 3.11 and the editable install will fail with a
confusing setuptools error — use `python3.11` explicitly to be safe.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
pytest
```

No cloud accounts, Docker, Postgres, Redis, or external services. Everything
runs locally and deterministically.

After setup, `pytest` should report **6 passed, 5 failed**. That is your
starting line — the failing public tests are part of the spec.

## Your Task

Make the running sync trustworthy. The failing public tests and
`docs/PROVIDER_API.md` together describe the gap between what the starter
does and what we need.

In broad strokes:

1. **Reliability** — pagination, retries, rate-limit handling, no infinite
   loops, no silent error swallowing.
2. **Data integrity** — idempotent re-runs, no duplicate residents, no stale
   data overwriting newer internal records, partial failures must not corrupt
   valid data.
3. **Validation & mapping** — read the provider docs carefully. Some fields
   are messier than the starter assumes. Surface validation errors with
   enough context to debug. Map provider `first_name` + `lastName` into the
   internal `full_name` field.
4. **Tests** — add at least 3 meaningful tests beyond the public suite.
   Cover edge cases that aren't already exercised.
5. **Notes & decision memo** — write up your approach, tradeoffs, and the
   design decisions you made when the docs were ambiguous (see
   "Decision memo" at the bottom of this file).

## Assumptions you can make

These corners are intentionally underspecified — exactly like real provider
integrations. Pick a defensible answer and document it. You will not be
punished for a reasonable choice.

- **Stale-write protection:** treating `existing.updated_at >= incoming.updated_at`
  as "skip" is acceptable. Strict `>` is also acceptable. Be consistent.
- **Counter semantics:** `created` for fresh inserts, `updated` for
  newer-overwrites, `skipped` for stale-protected, `failed` for malformed or
  validation errors. A stale-skip increments `skipped`, not `updated=0`.
- **Retry budget:** ≥ 3 attempts on transient / 429 errors is expected.
  Exponential backoff is a plus but not required.
- **Retry timing:** the test simulator uses `retry_after = 0` so retries do
  not wait. If your retry helper layers its own backoff on top, keep the
  per-attempt sleep small (≤ ~1s) — the test grader has a per-test timeout
  and a backoff that ignores `retry_after` may flake.
- **Permanent error mid-pagination:** record it in `result.errors` and stop
  the run cleanly. Do not retry. Do not silently continue.
- **Sync entrypoint signature:** keep
  `run_sync(provider, repository) -> SyncResult` so the grading harness can
  call your code unchanged.

## Timebox

Please block a focused **4-hour window** for the assignment. The timer starts
when you open the PandaDoc briefing we sent you.

It is fine — and expected — that you make tradeoffs to fit the timebox. If
setup issues or life interruptions materially affect your available time, just
note that in your submission. Tell us what you chose to prioritise and what
you would improve with more time.

## AI Tools

You are encouraged to use Claude Code, Codex, Cursor, Copilot, ChatGPT, or
similar tools. Use whatever you would use in a real job.

We evaluate the **final outcome**: reliability, data integrity, tests,
judgment, and your ability to explain the solution. We do not penalise AI
usage.

We will, however, ask you to walk through and defend your solution in the
next interview round, so make sure you understand what you submitted.

## What We Care About

- Correctness and end-to-end reliability
- Data integrity and idempotency
- Validation and graceful failure handling
- Meaningful tests, including for edge cases
- Simple, maintainable code
- Clear tradeoffs, documented decisions, and honest communication

## What We Don't Care About

- Avoiding AI tools
- Perfect architecture
- Unnecessary frameworks
- Real cloud deployment
- Building a full production system
- Adding unrelated features

## Codebase Tour

```
src/dexter_sync/
  models.py            # Pydantic models + provider->internal mapping
  exceptions.py        # Error hierarchy: provider, rate-limit, malformed-record
  provider_client.py   # Mock provider — reads JSON fixtures, simulates failures
  repository.py        # In-memory Firestore-like store, no business logic
  sync.py              # Orchestrator — your main focus
tests/
  conftest.py
  test_public_sync.py            # behavioural tests — several are red
  test_public_provider_client.py # simulator sanity checks (already green)
docs/
  PROVIDER_API.md      # synthetic provider docs — read this carefully
data/
  provider_page_*.json           # paginated provider fixtures
  provider_page_with_errors.json # malformed records
  provider_page_judgment.json    # ambiguity fixtures (see PROVIDER_API.md)
  existing_residents.json        # pre-seeded internal state for staleness test
logs/
  failed_sync.log                # example log shape — read for context
```

## Submission

Submit either:
1. A GitHub repository link (private or public, both fine), or
2. A zip file with your solution.

Please include in your README:
- What you changed and why
- Tradeoffs you made
- What you would improve with more time
- How you used AI tools (if applicable) and how you verified output
- How you ran and validated your solution
- Your honest time spent

---

## Your Notes (fill this in)

> Replace this section with your approach, assumptions, tradeoffs, known
> gaps, AI tool usage, and how you verified the solution.

### Decision memo

Briefly answer (4-8 sentences total):

1. How did you handle the polymorphic `care_level` field documented in
   `docs/PROVIDER_API.md`?
->I implemented an Anti-Corruption Layer(ACL) within the Resident.from_provider_payload factory method.
  The provider API returns 'care_level' in multiple formats.To handle this,I added a normalization step in the Resident model.It converts any valid string or prefixed value into a clean integer before saving it.I also made the prefix check case-insensitive to ensure the code doesn't break if the API sends "Level_3" instead of "level_3". This keeps our internal data consistent and easy to work with.

2. When a record carries both `is_active` and `deleted_at`, which wins, and
   why?
-> 'deleted_at' takes preference(wins)
   According to the changelog, 'deleted_at' is the more modern and authoritative field (v2.0) for removing
   a resident.In my implementation, if it contains a valid value, the resident is always treated as inactive internally, regardless of the value of is_active.This prevents edge cases where stale or inconsistent legacy flags could accidentally expose deleted residents as active records.

3. Did you use `last_updated` or `last_modified_by_caregiver` for stale-write
   protection? Why?
-> I have used 'last_updated'as the canonical key for staleness protection and idempotency 
   It represents the official timestamp of when the record was last saved on the server.
   'last_modified_by_caregiver' is informational and comes from the client-side,which can be unreliable due to time-sync issues. Using the server-side timestamp ensures that we always process updates in the correct order and don't overwrite new data with older responses.

4. **Past the table.** The Binding rules section of `docs/PROVIDER_API.md`
   resolves the documented cases. For each of the three above, name **one
   edge case the docs do NOT pin down** (e.g., an unknown `care_level`
   variant; `deleted_at` arriving in the future or being un-set on a later
   sync; a real situation in which `last_modified_by_caregiver` should
   matter for staleness) and how your code handles it.

-> Infinite Pagination Loop Traps:The docs warned about the same next_cursor being returned during errors. I used a set to track every cursor we've already processed. If we see the same token again, the sync stops with an error. This prevents the system from getting stuck in an infinite loop and wasting resources.

->  API Casing Inconsistency: I noticed the API is inconsistent with field names, specifically using lastName in some places. I added a fallback check for both lastName and last_name during mapping. This makes our integration more stable if the provider team changes their field casing.

-> Fault isolation :  If one resident's data is malformed (e.g., missing an ID), I catch that specific error and move to the next record instead of letting the whole sync fail. This ensures we ingest as much valid data as possible even if a few records are broken.

-> Validation for Unknown Formats: If 'care_level' comes in a format we don't recognize (like a random string or a list), the code raises a validation error for that record. It's better to fail the individual record than to save corrupted data into our database.

We will challenge these decisions with a fresh provider example in the
technical interview.


 Implementation Details

  What you changed and why

  1. models.py: Refactored Resident.from_provider_payload to handle data normalization (name concatenation, polymorphic care_level parsing, and deleted_at precedence). This ensures the domain layer only handles clean, validated data.
  2. sync.py: Replaced the happy-path skeleton with a robust engine featuring a pagination loop, retry logic for 429/5xx errors, and exponential backoff.
  3. Staleness Protection: Added a check to only upsert if incoming last_updated is strictly newer than existing data, ensuring system idempotency.

  Tradeoffs you made
  1. Strict Comparison: I used > for timestamps. Equal timestamps are skipped to reduce redundant database I/O, though it means no "refresh" for identical records.
  2. Retry Caps: Capped retries at 3 attempts with a 1s maximum wait to prevent the sync process from hanging and to meet SLA windows.
  3. In-memory tracking: Used a Python set for seen cursors. Efficient for current data volumes, but would require external state (Redis) for extremely large datasets.

  What you would improve with more time
   1. Observability: Implement structured JSON logging (e.g., structlog) to make production debugging easier.
   2. Concurrency: Implement parallel page fetching to increase throughput for large datasets.
   3. Circuit Breaker: Add a circuit breaker to stop the sync early if the error rate exceeds a certain threshold.

  How you used AI tools and verified output
   1. Used AI to generate mapping boilerplate and brainstorm edge-case test scenarios.
   2. Verification: Validated all outputs by running the full pytest suite and cross-referencing implementation against PROVIDER_API.md binding rules.
   

  How you ran and validated your solution
   1. Setup: pip install -e ".[dev]"
   2. Execution: Ran pytest to validate against 11 public tests.
   3. Extended Validation: Authored 3 additional tests in tests/test_my_sync.py to verify loop protection, transient error recovery, and complex mapping logic.

  Your honest time spent
  Approximately 3.5 hours of focused development and testing.
