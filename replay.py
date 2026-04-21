from game import Game, Board, Pacman, Blinky, Inky, Pinky, Clyde, GhostGroup
from collections import deque
from tkinter import messagebox
import pygame
import threading
import hashlib
import time


def updateQueue(queue, file):
    for x in file:
        queue.appendleft(x[:-1].split("@"))
    print("Fully loaded!")


def verifyFile(file):
    #Hashes file & compares to filename. If different then the file has been altered and is therefore considered corrupt
    try:
        BUFFER = 32000
        with open(file, "rb") as binaryReplay:
            h = hashlib.sha256()
            while True:
                data = binaryReplay.read(BUFFER)
                if not data:
                    break
                h.update(data)
            if str(str(file).split("/")[1]) != h.hexdigest():
                return False
            else:
                return True
    except:
        #File doesn't exist
        return False


def replay(file):
    if not verifyFile(file):
        messagebox.showerror("Error", "Replay File corrupted!")
        return
    pygame.init()
    screen = pygame.display.set_mode((720, 960))  # sets resolution to 3:4
    running = True
    LEVEL = 1
    ghostsCombo = 0
    pacman = Pacman()
    blinky = Blinky()
    inky = Inky()
    pinky = Pinky()
    clyde = Clyde()
    ghosts = GhostGroup(blinky, inky, pinky, clyde)
    dt = 0

    replayFile = open(file, "r")
    FPS = int(replayFile.readline()[:-1])
    boardString = replayFile.readline()[:-1]
    board = Board(boardString)
    positionQueue = deque()
    queueThread = threading.Thread(target=updateQueue, daemon=True, args=(positionQueue, replayFile))
    queueThread.start()

    clock = pygame.time.Clock()
    game = Game(-1, LEVEL, board, ghosts, pacman)

    queueItem = positionQueue.pop()  # loads the first queue item in
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        if game.checkIfLevelComplete():
            game.loadNextLevel()

        pacmanBox = pacman.getBoundBox()

        game.updateScore()

        for ghost in ghosts.getGhosts():
            if pacmanBox.colliderect(ghost.getBoundBox()):
                if ghost.isScared():
                    ghost.killGhost()
                    ghostsCombo += 1
                    game.addScore(100 * (2 ** ghostsCombo))
                elif not (ghost.isScared()):
                    game.loseLevel()

        if game.gameIsOver():
            print("Ran out of lives!")
            running = False

        if not ghosts.inScaredPhase() and ghostsCombo != 0:
            ghostsCombo = 0
        game.render(screen, dt)
        pygame.display.flip()

        entities = [pacman, blinky, inky, pinky, clyde]
        for item in entities:
            positionObject = queueItem[0][1:-2].split(", ")  # splits tuple into class and direction
            newPosition = pygame.Vector2(float(positionObject[1].strip("<(Vector>").replace("2(", "", 1)), float(
                positionObject[2].strip(">)")))  # returns position vector from file in form (x, y)
            item.setPosition(newPosition)
            try:
                queueItem = positionQueue.pop()
            except:
                messagebox.showinfo("Info", "End of Replay!")
                return
        clock.tick(FPS)
        dt = clock.tick(FPS) / 1000
