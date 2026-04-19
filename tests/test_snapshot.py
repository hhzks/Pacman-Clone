from netcommon import buildSnapshot, applySnapshot, diffPellets, PacketType


class FakeBox:
    def __init__(self, x, y, w):
        self.x = x
        self.y = y
        self.width = w
    def colliderect(self, other):
        return False


class FakePacman:
    def __init__(self):
        self._position = type("V", (), {"x": 100.0, "y": 200.0})()
        self._direction = 4
    def getPosition(self):
        return self._position
    def getDirection(self):
        return self._direction


class FakeGhost:
    def __init__(self, name, x, y, d, scared=False, dead=False):
        self._name = name
        self._position = type("V", (), {"x": x, "y": y})()
        self._direction = d
        self._scared = scared
        self._dead = dead
    def getName(self): return self._name
    def getPosition(self): return self._position
    def getDirection(self): return self._direction
    def isScared(self): return self._scared
    def isDead(self): return self._dead


class FakeGhostGroup:
    def __init__(self, ghosts):
        self._ghosts = ghosts
    def getGhosts(self):
        return self._ghosts


class FakeGame:
    def __init__(self):
        self._score = 150
        self._lives = 3
        self._level = 1
    def getScore(self): return self._score
    def getLives(self): return self._lives
    def getLevel(self): return self._level


class FakeBoard:
    def __init__(self, pellets_left):
        self._pellets_left = pellets_left
    def getDotsLeft(self):
        return self._pellets_left


def test_build_snapshot_basic():
    pac = FakePacman()
    ghosts = FakeGhostGroup([FakeGhost("Blinky", 10, 20, 1)])
    snap = buildSnapshot(
        tick=42, seq=7,
        game=FakeGame(), board=FakeBoard(pellets_left=30),
        pacman=pac, ghosts=ghosts,
        pelletDelta=[3, 9],
        lastInputSeq={"client-a": 5},
    )
    assert snap["t"] == PacketType.STATE
    assert snap["s"] == 7
    assert snap["tick"] == 42
    assert snap["pacman"] == {"x": 100.0, "y": 200.0, "dir": 4, "alive": True}
    assert snap["ghosts"] == [{"name": "Blinky", "x": 10, "y": 20,
                               "dir": 1, "scared": False, "dead": False}]
    assert snap["score"] == 150
    assert snap["lives"] == 3
    assert snap["level"] == 1
    assert snap["dotsLeft"] == 30
    assert snap["pelletDelta"] == [3, 9]
    assert snap["lastInputSeq"] == {"client-a": 5}


def test_diff_pellets_returns_indices_eaten_since_last():
    # Indices refer to positions in the original pellet list
    ate = diffPellets(original_count=10, present_now={0, 1, 2, 3, 4, 5, 6, 7, 9},
                      present_before={0, 1, 2, 3, 4, 5, 6, 7, 8, 9})
    assert ate == [8]


def test_apply_snapshot_updates_render_state():
    state = {"pacman": None, "ghosts": {}, "score": 0, "lives": 0,
             "level": 0, "dotsLeft": 0, "pelletsPresent": set(range(5))}
    snap = {
        "t": PacketType.STATE, "s": 1, "tick": 1,
        "pacman": {"x": 1.0, "y": 2.0, "dir": 3, "alive": True},
        "ghosts": [{"name": "Blinky", "x": 4, "y": 5, "dir": 2,
                    "scared": False, "dead": False}],
        "score": 500, "lives": 2, "level": 1, "dotsLeft": 3,
        "pelletDelta": [1, 3], "lastInputSeq": {},
    }
    applySnapshot(state, snap)
    assert state["pacman"] == snap["pacman"]
    assert state["ghosts"]["Blinky"] == snap["ghosts"][0]
    assert state["score"] == 500
    assert state["pelletsPresent"] == {0, 2, 4}
