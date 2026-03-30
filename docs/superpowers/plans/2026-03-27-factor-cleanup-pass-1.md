# Factor Cleanup Pass 1

Scope: remove bot runtime exposure from the application entry surface while preserving the factor-only product path.

Execution Status (2026-03-30):
- Completed in commit `baa0d0a`.
- `backend/main.py` no longer exposes bot runtime startup/shutdown hooks or `api.bot_routes` registration.
- Runtime dispatch tests were updated to assert factor-focused startup/shutdown behavior.
- Verification re-run after continuation:
  - `cd backend && uv run pytest tests/services/test_runtime_settings.py tests/services/test_startup_profiles.py tests/test_main_runtime_dispatch.py tests/services/test_program_execution_service.py tests/services/test_factor_research_service.py tests/services/test_factor_portfolio_service.py tests/services/test_factor_portfolio_deployment_service.py tests/services/test_factor_research_integration.py tests/api/test_factor_research_routes.py tests/api/test_factor_portfolio_routes.py -q` -> `80 passed`
  - `cd backend && uv run ruff check main.py tests/test_main_runtime_dispatch.py` -> `All checks passed!`
  - `cd backend && uv run python -m py_compile main.py tests/test_main_runtime_dispatch.py` -> exit `0`

Behavior Lock:
- `backend/tests/services/test_runtime_settings.py`
- `backend/tests/services/test_startup_profiles.py`
- `backend/tests/services/test_program_execution_service.py`
- `backend/tests/services/test_factor_research_service.py`
- `backend/tests/services/test_factor_portfolio_service.py`
- `backend/tests/services/test_factor_portfolio_deployment_service.py`
- `backend/tests/services/test_factor_research_integration.py`
- `backend/tests/api/test_factor_research_routes.py`
- `backend/tests/api/test_factor_portfolio_routes.py`

Cleanup Plan:
1. Dead code deletion
   - Remove bot startup/shutdown hooks from `backend/main.py`
   - Remove `api.bot_routes` import and router registration from `backend/main.py`
2. Test cleanup
   - Replace bot-specific runtime dispatch tests with assertions for the remaining factor startup/shutdown paths
3. Verification
   - Re-run the focused factor suite
   - Re-run ruff and py_compile for touched files

Deferred:
- Physical deletion of bot service modules and frontend Hyper AI/bot UI
- Binance deletion pass
