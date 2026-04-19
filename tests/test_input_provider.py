from game import readDirectionFromKeys


class FakePressed(dict):
    """pygame.key.get_pressed() returns an object indexable by key code.
    We fake it with a plain dict keyed by the integer code."""
    def __getitem__(self, key):
        return super().get(key, False)


def _code(ch):
    # Map 'up','down','left','right' config tokens to deterministic fake codes.
    return {"up": 1, "down": 2, "left": 3, "right": 4,
            "w": 11, "s": 12, "a": 13, "d": 14}[ch]


def test_no_keys_pressed_returns_zero(monkeypatch):
    monkeypatch.setattr("pygame.key.key_code", _code)
    pressed = FakePressed()
    assert readDirectionFromKeys(["up", "down", "left", "right"], pressed) == 0


def test_up_key_returns_one(monkeypatch):
    monkeypatch.setattr("pygame.key.key_code", _code)
    pressed = FakePressed({_code("up"): True})
    assert readDirectionFromKeys(["up", "down", "left", "right"], pressed) == 1


def test_right_key_returns_four(monkeypatch):
    monkeypatch.setattr("pygame.key.key_code", _code)
    pressed = FakePressed({_code("d"): True})
    assert readDirectionFromKeys(["w", "s", "a", "d"], pressed) == 4


def test_first_matching_key_wins(monkeypatch):
    """Mirror the 'for key in movementKeys: if pressed: return ... break'
    ordering of the existing movePlayer code."""
    monkeypatch.setattr("pygame.key.key_code", _code)
    pressed = FakePressed({_code("up"): True, _code("down"): True})
    assert readDirectionFromKeys(["up", "down", "left", "right"], pressed) == 1


from game import LocalInputProvider


class FakeEntity:
    def __init__(self, name):
        self._name = name
    def getName(self):
        return self._name


def test_local_input_provider_pacman(monkeypatch):
    monkeypatch.setattr("pygame.key.key_code", _code)
    pressed = FakePressed({_code("up"): True})
    p = LocalInputProvider(
        pacmanKeys=["up", "down", "left", "right"],
        ghostKeyLists=[],
    )
    p.refresh(pressed)
    assert p.directionFor(FakeEntity("Pacman"), ghostIndex=None) == 1


def test_local_input_provider_ghost_by_index(monkeypatch):
    monkeypatch.setattr("pygame.key.key_code", _code)
    pressed = FakePressed({_code("d"): True})
    p = LocalInputProvider(
        pacmanKeys=["up", "down", "left", "right"],
        ghostKeyLists=[["w", "s", "a", "d"]],
    )
    p.refresh(pressed)
    assert p.directionFor(FakeEntity("Blinky"), ghostIndex=0) == 4


def test_local_input_provider_ghost_without_slot_returns_zero(monkeypatch):
    monkeypatch.setattr("pygame.key.key_code", _code)
    p = LocalInputProvider(
        pacmanKeys=["up", "down", "left", "right"],
        ghostKeyLists=[],
    )
    p.refresh(FakePressed())
    assert p.directionFor(FakeEntity("Blinky"), ghostIndex=0) == 0
