# Factor Cleanup Pass 1

Scope: remove bot runtime exposure from the application entry surface while preserving the factor-only product path.

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
