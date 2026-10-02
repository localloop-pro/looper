# THROWAWAY (looper#32): proves a failing test turns CI red. Reverted next commit.
def test_ci_turns_red_on_failure():
    assert 1 == 2
