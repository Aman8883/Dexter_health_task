from __future__ import annotations

import pytest
from dexter_sync.sync import run_sync
from dexter_sync.provider_client import MockCareProvider, FailurePlan

def test_infinite_loop_protection(data_dir, repository):
    """If a provider returns the same cursor, we must stop and record error."""
    provider = MockCareProvider(
        data_dir=data_dir,
        page_files=["provider_page_1.json"],
        duplicate_cursor_trap=True
    )
    result = run_sync(provider, repository)
    assert any("Infinite loop" in err for err in result.errors)
    # It should have processed the first page once
    assert repository.count() == 5

def test_retry_on_transient_failure(data_dir, repository):
    """If provider hits transient errors, we should retry and succeed if within budget."""
    plan = FailurePlan(
        transient_failures_per_cursor={None: 2} # First call fails twice
    )
    provider = MockCareProvider(
        data_dir=data_dir,
        page_files=["provider_page_1.json"],
        failure_plan=plan
    )
    result = run_sync(provider, repository)
    assert result.created == 5
    assert len(result.errors) == 0
    # Provider was called 3 times for the first page (2 fails + 1 success)
    assert provider.call_count == 3

def test_judgment_mapping_logic(data_dir, repository):
    """Verify complex mapping rules from the judgment fixture."""
    provider = MockCareProvider(
        data_dir=data_dir,
        page_files=["provider_page_judgment.json"],
    )
    run_sync(provider, repository)
    
    # RES-2001: care_level="3" -> 3, name mapping
    res_2001 = repository.get_resident("RES-2001")
    assert res_2001.care_level == 3
    assert res_2001.full_name == "Harper Quinn"
    
    # RES-2002: care_level="level_2" -> 2
    res_2002 = repository.get_resident("RES-2002")
    assert res_2002.care_level == 2
    
    # RES-2003: care_level=null -> None
    res_2003 = repository.get_resident("RES-2003")
    assert res_2003.care_level is None

    # RES-2004: is_active=true, deleted_at set -> is_active=false
    res_2004 = repository.get_resident("RES-2004")
    assert res_2004.is_active is False

    # RES-2005: is_active=false -> is_active=false
    res_2005 = repository.get_resident("RES-2005")
    assert res_2005.is_active is False
