import sys
import types

from services.scheduler import TaskScheduler


def test_execute_account_snapshot_is_sync_and_removes_disconnected_account(monkeypatch):
    scheduler = TaskScheduler()
    removed_accounts = []

    monkeypatch.setattr(
        scheduler,
        "remove_account_snapshot_task",
        lambda account_id: removed_accounts.append(account_id),
    )

    fake_ws_module = types.SimpleNamespace(
        manager=types.SimpleNamespace(active_connections={})
    )
    monkeypatch.setitem(sys.modules, "api.ws", fake_ws_module)

    result = scheduler._execute_account_snapshot(99)

    assert result is None
    assert removed_accounts == [99]
