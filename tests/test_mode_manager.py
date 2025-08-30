import pytest

from src.services.mode_manager import get_mode_manager, Mode


@pytest.mark.asyncio
async def test_initial_state():
    manager = get_mode_manager()
    state = await manager.get_state()
    assert state.current_mode == Mode.DATA_MINING
    assert state.status in {"idle", "running"}
    assert state.data_policy == "gapfill_then_expansion"


@pytest.mark.asyncio
async def test_mode_transitions():
    manager = get_mode_manager()

    state = await manager.set_mode(Mode.DATA_MINING, message="start mining")
    assert state.current_mode == Mode.DATA_MINING
    assert state.status == "running"
    assert state.message == "start mining"
    assert state.gapfill_completed is False

    state = await manager.set_mode(Mode.BACKTESTING)
    assert state.current_mode == Mode.BACKTESTING
    assert state.status == "running"
    assert state.top_symbols == []

    state = await manager.set_mode(Mode.TRADING)
    assert state.current_mode == Mode.TRADING
    assert state.status == "running"
    # active_symbols seeds from top_symbols (empty by default)
    assert isinstance(state.active_symbols, list)

