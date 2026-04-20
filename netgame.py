import os
import time
import hashlib
import configparser
import math

import pygame

import boards
import database
from game import (Board, Pacman, Blinky, Inky, Pinky, Clyde,
                  GhostGroup, PlayerGhosts, Bots, Movement, Game,
                  NetworkInputProvider, stepSimulation, getControls)
from netcommon import (PacketType, NET_HZ, buildSnapshot, diffPellets,
                       seq_next)


def runHostedGame(players, names, mazeString, host_session):
    """Authoritative simulation + 30Hz STATE broadcast.

    `players` — number of human ghosts (1-4).
    `names` — 5-slot list matching runGame semantics.
    `host_session` — started HostSession (already past start_match).
    """
    configObj = configparser.ConfigParser()
    with open("config.ini", "r") as configFile:
        configObj.read_file(configFile)

    pygame.init()
    screen = pygame.display.set_mode((720, 960))
    clock = pygame.time.Clock()
    running = True
    TIMEOFGAME = time.strftime("%Y-%m-%d %H:%M:%S")
    RECORDGAME = configObj.get("Performance", "replays") != "False"
    FPS = int(configObj.get("Performance", "fps"))
    dt = 0
    LEVEL = 1

    board = Board(mazeString)
    pacman = Pacman()
    blinky, inky, pinky, clyde = Blinky(), Inky(), Pinky(), Clyde()
    ghosts = GhostGroup(blinky, inky, pinky, clyde)
    movement = Movement(board, pacman, blinky)
    PLAYER1KEYS = getControls("Player 1", configObj)

    # Partition ghosts based on `players` count, same as runGame's match.
    all_ghosts = [blinky, inky, pinky, clyde]
    player_ghosts = all_ghosts[:players]
    bot_ghosts = all_ghosts[players:]
    playerGhosts = PlayerGhosts(*player_ghosts)
    botGhosts = Bots(*bot_ghosts)

    # Map ghostIndex (position in playerGhosts) -> clientId from the roster
    # at START time. Join order is stable.
    roster = host_session.get_roster()
    ghost_ownership = {i: roster[i]["clientId"]
                       for i in range(min(len(roster), players))}

    inputProvider = NetworkInputProvider(
        pacmanKeys=PLAYER1KEYS,
        clientInputsFn=host_session.get_client_inputs,
        ghostOwnership=ghost_ownership,
    )

    game = Game(3, LEVEL, board, ghosts, pacman)

    if RECORDGAME:
        fileName = time.time()
        replayFile = open(f"replays/{fileName}", "w")
        replayFile.write(f"{FPS}\n")
        replayFile.write(f"{board.getBoardStr()}\n")

    net_tick_interval = 1.0 / NET_HZ
    next_net_tick = time.monotonic()
    snapshot_seq = 0
    pellets_before = {i for i in range(len(board._Board__ogPelletPositions))}
    current_pellets_set = set(pellets_before)

    def _present_pellet_indices():
        # Map current __pelletPositions back to their index in __ogPelletPositions.
        og = board._Board__ogPelletPositions
        present = board._Board__pelletPositions
        # Rebuild indices by identity — positions are the same Rect objects
        return {og.index(p) for p in present}

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Drop clients that timed out; ghost slot stays (just stops receiving input)
        dropped = host_session.check_timeouts()
        for cid in dropped:
            for idx, owner in list(ghost_ownership.items()):
                if owner == cid:
                    ghost_ownership.pop(idx, None)
                    # Move ghost from PlayerGhosts to Bots so CPU drives it
                    g = player_ghosts[idx]
                    if g in playerGhosts.getGhosts():
                        playerGhosts.getGhosts().remove(g)
                        botGhosts.getGhosts().append(g)

        inputProvider.refresh(pygame.key.get_pressed())
        events = stepSimulation(game, movement, pacman, ghosts,
                                playerGhosts, botGhosts, inputProvider)

        if "level-complete" in events:
            game.loadNextLevel()
        if "game-over" in events:
            running = False

        game.render(screen, dt)
        pygame.display.flip()

        # Network tick: broadcast snapshot
        now = time.monotonic()
        if now >= next_net_tick:
            next_net_tick = now + net_tick_interval
            new_pellets = _present_pellet_indices()
            pellet_delta = diffPellets(len(board._Board__ogPelletPositions),
                                       new_pellets, current_pellets_set)
            current_pellets_set = new_pellets
            snapshot_seq = seq_next(snapshot_seq)
            snap = buildSnapshot(
                tick=int(now * 1000), seq=snapshot_seq,
                game=game, board=board, pacman=pacman, ghosts=ghosts,
                pelletDelta=pellet_delta, lastInputSeq={
                    cid: v["seq"] for cid, v
                    in host_session.get_client_inputs().items()},
            )
            host_session.broadcast_state(snap)
            for e in events:
                host_session.broadcast_event({"t": PacketType.EVENT, "event": e})

        if RECORDGAME:
            replayFile.write(f"{pacman.getClass(), pacman.getPosition()} @{game.getTime()}\n")
            for g in (blinky, inky, pinky, clyde):
                replayFile.write(f"{g.getClass(), g.getPosition()} @{game.getTime()}\n")

        clock.tick(FPS)
        dt = clock.tick(FPS) / 1000

    # Match end: write DB + replay (same as runGame)
    leaderboard = database.Leaderboard()
    leaderboard.inputScore(TIMEOFGAME, game.getTime() / 1000, game.getScore(),
                           leaderboard.getMazeName(mazeString))
    matchID = leaderboard.getMatchID()
    leaderboard.addToMatchBook(names[0], matchID, pacman.getName())
    for i, ghost in enumerate(ghosts.getGhosts()):
        if ghost in player_ghosts:
            idx = player_ghosts.index(ghost)
            leaderboard.addToMatchBook(
                names[1 + idx] if idx + 1 < len(names) else "",
                matchID, ghost.getName())

    if RECORDGAME:
        replayFile.close()
        BUFFER = 32000
        with open(f"replays/{fileName}", "rb") as binaryReplay:
            h = hashlib.sha256()
            while True:
                data = binaryReplay.read(BUFFER)
                if not data:
                    break
                h.update(data)
        os.rename(f"replays/{fileName}", f"replays/{h.hexdigest()}")
        leaderboard.addReplay(matchID, h.hexdigest())
        host_session.broadcast_event({"t": PacketType.EVENT,
                                      "event": "replay-hash",
                                      "hash": h.hexdigest()})

    leaderboard.close()
    host_session.broadcast_event({"t": PacketType.EVENT, "event": "game-over"})


def runClientGame(client_session, mazeString):
    """Render-only client loop. Sends INPUT, renders from interpolated STATE."""
    configObj = configparser.ConfigParser()
    with open("config.ini", "r") as configFile:
        configObj.read_file(configFile)

    pygame.init()
    screen = pygame.display.set_mode((720, 960))
    clock = pygame.time.Clock()
    FPS = int(configObj.get("Performance", "fps"))
    PLAYER1KEYS = getControls("Player 1", configObj)

    board = Board(mazeString)
    # Load the sprites up front so rendering is snappy.
    from game import Pacman as PacmanCls, Blinky as BlinkyCls, \
        Inky as InkyCls, Pinky as PinkyCls, Clyde as ClydeCls
    sprites = {
        "Pacman": pygame.transform.scale(pygame.image.load("images/player.jpg"), (24, 24)),
        "Blinky": pygame.transform.scale(pygame.image.load("images/blinky.jpg"), (24, 24)),
        "Inky":   pygame.transform.scale(pygame.image.load("images/inky.jpg"),   (24, 24)),
        "Pinky":  pygame.transform.scale(pygame.image.load("images/pinky.jpg"),  (24, 24)),
        "Clyde":  pygame.transform.scale(pygame.image.load("images/clyde.jpg"),  (24, 24)),
        "scared": pygame.transform.scale(pygame.image.load("images/scared.jpg"), (24, 24)),
        "dead":   pygame.transform.scale(pygame.image.load("images/dead.jpg"),   (24, 24)),
    }
    my_font = pygame.font.SysFont("Jokerman", 30)

    running = True
    last_input_send = 0.0
    input_interval = 1.0 / 60  # 60 Hz input send
    snapshot_interval = 1.0 / NET_HZ
    pellets_present = {i for i in range(len(board._Board__ogPelletPositions))}

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        client_session.poll()

        # Apply pellet deltas from any newly arrived STATE
        if client_session.latest_state is not None:
            for idx in client_session.latest_state.get("pelletDelta", []):
                pellets_present.discard(idx)

        # Handle events (game-over, BYE)
        for e in client_session.events:
            ev = e.get("event") if e.get("t") == PacketType.EVENT else None
            if ev == "game-over" or e.get("t") == PacketType.BYE:
                running = False
        client_session.events = []

        # Send input at ~60Hz
        now = time.monotonic()
        if now - last_input_send >= input_interval:
            last_input_send = now
            pressed = pygame.key.get_pressed()
            dir_ = 0
            for i, key in enumerate(PLAYER1KEYS):
                if pressed[pygame.key.key_code(key)]:
                    dir_ = i + 1
                    break
            client_session.send_input(dir_)

        # Render
        screen.fill("black")
        # Walls
        for wall in board._Board__wallPositions:
            pygame.draw.rect(screen, "blue", wall, 1)
        # Pellets (static — eaten ones removed via pelletDelta)
        og = board._Board__ogPelletPositions
        for idx in pellets_present:
            if idx < len(og):
                pygame.draw.rect(screen, "white", og[idx])

        # Entities — interpolate between prev/latest
        latest = client_session.latest_state
        prev = client_session.prev_state
        if latest is not None:
            if prev is not None and client_session.latest_state_arrived_at > client_session.prev_state_arrived_at:
                span = client_session.latest_state_arrived_at - client_session.prev_state_arrived_at
                t = min(1.1, (now - client_session.latest_state_arrived_at) / max(span, 1e-6) + 1.0)
                t = max(0.0, min(1.1, t))
            else:
                t = 1.0

            def _interp(a, b, k):
                return a + (b - a) * k

            # Pac-Man
            if prev is not None and prev["pacman"] is not None:
                px = _interp(prev["pacman"]["x"], latest["pacman"]["x"], t)
                py = _interp(prev["pacman"]["y"], latest["pacman"]["y"], t)
            else:
                px, py = latest["pacman"]["x"], latest["pacman"]["y"]
            screen.blit(sprites["Pacman"], (px - 12, py - 12))

            # Ghosts
            prev_by_name = {g["name"]: g for g in (prev["ghosts"] if prev else [])}
            for g in latest["ghosts"]:
                if g["name"] in prev_by_name and prev is not None:
                    gx = _interp(prev_by_name[g["name"]]["x"], g["x"], t)
                    gy = _interp(prev_by_name[g["name"]]["y"], g["y"], t)
                else:
                    gx, gy = g["x"], g["y"]
                if g["dead"]:
                    sprite = sprites["dead"]
                elif g["scared"]:
                    sprite = sprites["scared"]
                else:
                    sprite = sprites[g["name"]]
                screen.blit(sprite, (gx - 12, gy - 12))

            # HUD
            def _draw(text, val, pos):
                s = my_font.render(f"{text}: {val}", False, "White")
                screen.blit(s, pos)
            _draw("Score", latest["score"], (0, 800))
            _draw("Lives", latest["lives"], (600, 800))
            _draw("Level", latest["level"], (600, 900))

        pygame.display.flip()
        clock.tick(FPS)

    client_session.send_bye()
    client_session.close()
