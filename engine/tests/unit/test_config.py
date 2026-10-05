from bob_resolve import config


def test_paid_modes_are_off_by_default() -> None:
    assert config.DEFAULT_JEV_MODE == "replay"
    assert config.LLM_ARM_ENABLED is False
