"""Legacy eval harness skipped — production flow covered in integration tests."""

import pytest

pytest.skip("Use tests/integration/test_production_flow.py for production coverage", allow_module_level=True)
