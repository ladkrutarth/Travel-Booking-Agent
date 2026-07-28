"""Eval runner for offline fixture cases (mocked providers)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure src and repo root on path when run as script
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("AMADEUS_MOCK", "true")
os.environ.setdefault("OPENWEATHER_MOCK", "true")
os.environ.setdefault("GOOGLE_PLACES_MOCK", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///./eval.db")

from travel_agent.config import get_settings
from travel_agent.db import init_db, session_factory
from travel_agent.service import TripService
from tests.evals.fixtures import EVAL_CASES


def main() -> int:
    get_settings.cache_clear()
    init_db()
    service = TripService()
    passed = 0
    failed = 0

    for case in EVAL_CASES:
        session = session_factory()
        try:
            result = service.create_trip(session, case["message"])
            session.commit()
            if case.get("expect_blocked"):
                ok = result.state.value == "FAILED" and "input_blocked" in (result.error or "")
            else:
                ok = result.state.value == case.get("expect_state", "AWAIT_APPROVAL")
                if ok and "expect_within_budget" in case and result.proposal:
                    ok = result.proposal.within_budget is case["expect_within_budget"]
            status = "PASS" if ok else "FAIL"
            if ok:
                passed += 1
            else:
                failed += 1
            print(
                f"[{status}] {case['id']} state={result.state.value} "
                f"error={result.error} within_budget="
                f"{getattr(result.proposal, 'within_budget', None)}"
            )
        finally:
            session.close()

    print(f"\nSummary: {passed} passed, {failed} failed, {len(EVAL_CASES)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
