import os
import boards
import pygame
import time
import database
import random
import math
import configparser


def Square(x, y, size):
    return pygame.Rect(x - size / 2, y - size / 2, size, size)


class Board:
    def __init__(self, boardStr):
        self._boardStr = boardStr
        self._board = boards.decodeMaze(boardStr) #creator inherits this
        self.__dotsLeft = 0
        self.__wallPositions = []
        self.__pelletPositions = []
        self.__ogPelletPositions = []
        self.__junctionPositions = []

        for j in range(len(self._board)):
            for i in range(len(self._board[j])):
                pos = self.getCoord(i, j)
                if self._board[j][i] == 1:
                    self.__ogPelletPositions.append(Square(pos[0], pos[1], 6))
                    self.__pelletPositions.append(Square(pos[0], pos[1], 6))
                    self.__dotsLeft += 1
                elif self._board[j][i] == 2:
                    self.__ogPelletPositions.append(Square(pos[0], pos[1], 12))
                    self.__pelletPositions.append(Square(pos[0], pos[1], 12))
                    self.__dotsLeft += 1
                elif self._board[j][i] == 3:
                    self.__wallPositions.append(Square(pos[0], pos[1], 24))

        for junctions in boards.mazeMapping(self._board):
            pos = self.getCoord(junctions[1], junctions[0])
            self.__junctionPositions.append(Square(pos[0], pos[1], 2))

    def getBoard(self):
        return self._board

    def getBoardStr(self):
        return self._boardStr

    def getJunctionPositions(self):
        return self.__junctionPositions

    def collidesWithWall(self, rect):
        for i in self.__wallPositions:
            if i.colliderect(rect):
                return True
        return False

    def collidesWithPellet(self, rect):  # returns 1 if there is a collision with small pellet, returns 2 if
        for i in self.__pelletPositions:  # collision with power pellet, returns 0 if no collision
            if i.colliderect(rect):
                self.__pelletPositions.remove(i)
                if i.width == 12:
                    return 2
                elif i.width == 6:
                    return 1
        return 0

    def getDotsLeft(self):
        return len(self.__pelletPositions)

    def coordInJunction(self, xcoord, ycoord):
        for junctions in self.getJunctionPositions():
            if junctions.collidepoint(xcoord, ycoord):
                return True
        return False

    def render(self, screen):
        for i in self.__wallPositions:
            pygame.draw.rect(screen, "blue", i, 1)
        for i in self.__pelletPositions:
            pygame.draw.rect(screen, "white", i)

    def resetBoard(self):  # method is implemented like this rather than a simple assignment statement
        for pellet in self.__ogPelletPositions:  # to avoid the original list being permanently associated with the modified list
            self.__pelletPositions.append(pellet)

    @staticmethod
    def getCoord(x, y):
        coordX = (24 * x) + 12
        coordY = (24 * y) + 12
        return coordX, coordY

    @staticmethod
    def getGridRef(x, y):
        refX = x // 24
        refY = y // 24
        return int(refX), int(refY)
    
    def isNextBlockWall(self, direction, position):
        virtualPosition = (position[0],position[1])
        match direction:
            case 1:
                virtualPosition = (position[0], position[1] + 12)
            case 2:
                virtualPosition = (position[0], position[1] - 12)
            case 3:
                virtualPosition = (position[0] + 12, position[1])
            case 4:
                virtualPosition = (position[0] - 12, position[1])
            case _:
                virtualPosition = (position[0], position[1])


        gridPosition = self.getGridRef(virtualPosition[0],virtualPosition[1])
        if direction == 1:
            if self._board[gridPosition[1] - 1][gridPosition[0]] == 3:
                return True
            else:
                return False

        if direction == 2:
            if self._board[gridPosition[1] + 1][gridPosition[0]] == 3:
                return True
            else:
                return False

        if direction == 3:
            if self._board[gridPosition[1]][gridPosition[0] - 1] == 3:
                return True
            else:
                return False

        try:
            if direction == 4:
                if self._board[gridPosition[1]][gridPosition[0] + 1] == 3:
                    return True
                else:
                    return False
        except IndexError:  # Error handling for the case where the player enters a right side warp; in this case there wouldn't be an incoming collision
            return False
            



class Game:
    def __init__(self, lives, Level, board, ghosts, pacman):
        self.__time = 0
        self.__originalTime = pygame.time.get_ticks()
        self.__score = 0
        self.__lives = lives
        self.__level = Level
        self._board = board
        self.__ghosts = ghosts
        self.__pacman = pacman
        self.__extraLifeAchieved = False

    def addLives(self, lives):
        self.__lives += lives

    def getLives(self):
        return self.__lives

    def getScore(self):
        return self.__score

    def addScore(self, score):
        self.__score += score

    def getLevel(self):
        return self.__level

    def loadNextLevel(self):
        self.__level += 1
        self._board.resetBoard()
        print(math.log(self.__level, 55.90169944) + 0.6)
        self.__ghosts.setNormalSpeeds(math.log(self.__level, 55.90169944) + 0.6)
        print(math.log(self.__level, 55.90169944) + 0.6)
        self.__ghosts.resetGhosts()
        self.__pacman.restart()
        pygame.time.delay(1000)

    def loseLevel(self):
        self.__lives -= 1
        self.__ghosts.resetGhosts()
        self.__pacman.restart()
        pygame.time.delay(1000)

    @staticmethod
    def drawValue(text, variable, pos, screen):
        my_font = pygame.font.SysFont('Jokerman', 30)
        valText = f"{text}: {variable}"
        val_surface = my_font.render(valText, False, "White")
        screen.blit(val_surface, pos)

    def render(self, screen, dt):
        screen.fill("black")
        self.__time = pygame.time.get_ticks() - self.__originalTime
        self._board.render(screen)
        self.__pacman.render(screen, dt)
        for ghost in self.__ghosts.getGhosts():
            ghost.render(screen, dt)

        self.drawValue("Score", self.__score, (0, 800), screen)
        self.drawValue("Time", self.__time / 1000, (300, 800), screen)
        self.drawValue("Lives", self.__lives, (600, 800), screen)
        self.drawValue("Level", self.__level, (600, 900), screen)

    def checkIfLevelComplete(self):
        if self._board.getDotsLeft() == 0:
            print("Level complete!")
            return True

    def updateScore(self):
        pelletCheck = self._board.collidesWithPellet(self.__pacman.getBoundBox())
        if pelletCheck == 1:
            self.addScore(10)
        elif pelletCheck == 2:
            self.addScore(50)
            self.__ghosts.scareGhosts()
        if self.__score >= 5000 and not(self.__extraLifeAchieved):    #Add extra life once 5000 points have been reached
            self.addLives(1)
            self.__extraLifeAchieved = True

    def gameIsOver(self):
        if self.__lives == 0:
            return True

    def getTime(self):
        return self.__time


class Entity:
    def __init__(self, img, position):
        self._imgJPG = img
        self._img = pygame.transform.scale(pygame.image.load(img), (24, 24))
        self._startPos = position
        self._position = pygame.Vector2(position)
        self._direction = 0
        self._speed = 1
        self._boundBox = Square(self._position.x, self._position.y, 24)
        self._name = 'Entity'


    def getBoundBox(self):
        return self._boundBox

    def getPosition(self):
        return self._position

    def addSpeed(self, newSpeed):
        self._speed += newSpeed
        if self._speed < 0:
            self._speed = 0

    def setDirection(self, direction):
        self._direction = direction

    def getDirection(self):
        return self._direction

    def setPosition(self, pos):
        self._position = pos

    def getSpeed(self):
        return self._speed

    def getName(self):
        return self._name

    def render(self, screen, dt):
        self.updatePos(dt)
        self._boundBox = Square(self._position.x, self._position.y, 18)
        screen.blit(self._img, (self._position.x - 12, self._position.y - 12))
        
    def updatePos(self, dt):  # Direction 1 is up, 2 is down, 3 is left, 4 is right
        if self._direction == 1:
            self._position.y -= self._speed * 300 * dt
        if self._direction == 2:
            self._position.y += self._speed * 300 * dt
        if self._direction == 3:
            self._position.x -= self._speed * 300 * dt
        if self._direction == 4:
            self._position.x += self._speed * 300 * dt

        if self._position.x < 0:
            self._position.x = 720
        if self._position.x > 720:
            self._position.x = 0

    @classmethod
    def getClass(cls):
        return cls


class Pacman(Entity):
    def __init__(self):
        self.__startPoint = Board.getCoord(14, 24)
        Entity.__init__(self, "images/player.jpg", (self.__startPoint[0], self.__startPoint[1]))
        self._name = 'Pacman'

    def restart(self):
        self._position = pygame.Vector2(self.__startPoint[0], self.__startPoint[1])
        self._direction = 0


class Ghost(Entity):
    def __init__(self, ghostType):  # 0 is blinky, 1 is inky, 2 is pinky, 3 is clyde
        self._normalTick = 9999999999  # timer for scared phase, determines at what tick the ghost should stop being scared
        if ghostType == 0:
            Entity.__init__(self, "images/blinky.jpg", Board.getCoord(16,16))
        elif ghostType == 1:
            Entity.__init__(self, "images/inky.jpg", Board.getCoord(16,14))
        elif ghostType == 2:
            Entity.__init__(self, "images/pinky.jpg", Board.getCoord(13,16))
        elif ghostType == 3:
            Entity.__init__(self, "images/clyde.jpg", Board.getCoord(13,14))
        self._isScared = False
        self._isDead = False
        self._normalSpeed = 0.6 #starting speed
        self._speed = self._normalSpeed
        self._lastJunction = (0,0) #The last visited junction by the ghost, prevents double moving at junction

    def reset(self):
        self._position = pygame.Vector2(self._startPos)
        self._speed = self._normalSpeed
        self._normalTick = 9999999999
        self._isScared = False
        self._isDead = False
        self._img = pygame.transform.scale(pygame.image.load(self._imgJPG), (24, 24))

    def setNormalSpeed(self, speed):
        self._normalSpeed = speed

    def scareGhost(self):
        self._normalTick = pygame.time.get_ticks() + 5000
        self._isScared = True
        self._img = pygame.transform.scale(pygame.image.load("images/scared.jpg"), (24, 24))
        self._speed = 0.5

    def getLastJunction(self):
        return self._lastJunction

    def setLastJunction(self, coordinate):
        self._lastJunction = coordinate


    @staticmethod
    def getDirectionPreference(vector):
        directionPreference = []
        if abs(vector.x) > abs(vector.y):
            if vector.x < 0:
                directionPreference.append(3)
                if vector.y < 0:
                    directionPreference.append(1)
                    directionPreference.append(2)
                else:
                    directionPreference.append(2)
                    directionPreference.append(1)
                directionPreference.append(4)
            else:
                directionPreference.append(4)
                if vector.y < 0:
                    directionPreference.append(1)
                    directionPreference.append(2)
                else:
                    directionPreference.append(2)
                    directionPreference.append(1)
                directionPreference.append(3)
        else:
            if vector.y < 0:
                directionPreference.append(1)
                if vector.x < 0:
                    directionPreference.append(3)
                    directionPreference.append(4)
                else:
                    directionPreference.append(4)
                    directionPreference.append(3)
                directionPreference.append(2)
            else:
                directionPreference.append(2)
                if vector.x < 0:
                    directionPreference.append(3)
                    directionPreference.append(4)
                else:
                    directionPreference.append(4)
                    directionPreference.append(3)
                directionPreference.append(1)
        return directionPreference

    def runAway(self, vector):
        targetVector = self.getPosition() - vector  # When running away, this is the vector the ghosts target.
        return self.getDirectionPreference(targetVector)  # It is the vector opposite the vector facing pac-man

    def killGhost(self):
        self._position = pygame.Vector2(self._startPos)
        self._isDead = True
        self._isScared = False
        self._img = pygame.transform.scale(pygame.image.load("images/dead.jpg"), (24, 24))
        self._normalTick = pygame.time.get_ticks() + 5000
        self._direction = 0

    def updateState(self, dt):
        if pygame.time.get_ticks() >= self._normalTick:
            self._isScared = False
            self._isDead = False
            self._img = pygame.transform.scale(pygame.image.load(self._imgJPG), (24, 24))
            self._speed = self._normalSpeed
            self._normalTick = 9999999999

    def render(self, screen, dt):
        super().render(screen, dt)
        self.updateState(dt)

    def isScared(self):
        return self._isScared

    def isDead(self):
        return self._isDead


class Blinky(Ghost):
    def __init__(self):
        Ghost.__init__(self, 0)
        self._name = 'Blinky'

    def getChaseDirections(self, playerPos):
        displacementVector = pygame.Vector2(playerPos - self.getPosition())
        return self.getDirectionPreference(displacementVector)


class Inky(Ghost):
    def __init__(self):
        Ghost.__init__(self, 1)
        self._name = 'Inky'

    def getChaseDirections(self, playerPos, playerDir, blinkyPos):
        posArr = list(playerPos)
        if playerDir == 1:
            posArr[1] -= 2 * 24
        elif playerDir == 2:
            posArr[1] += 2 * 24
        elif playerDir == 3:
            posArr[0] -= 2 * 24
        elif playerDir == 4:
            posArr[0] += 2 * 24

        displacementVector = [0, 0]
        invDisplacementVector = list(blinkyPos - posArr)
        displacementVector[0] = -1 * invDisplacementVector[0]
        displacementVector[1] = -1 * invDisplacementVector[1]
        targetVector = [0, 0]
        targetVector[0] = displacementVector[0] + posArr[0]
        targetVector[1] = displacementVector[1] + posArr[1]
        return self.getDirectionPreference(pygame.Vector2(targetVector))


class Pinky(Ghost):
    def __init__(self):
        Ghost.__init__(self, 2)
        self._name = 'Pinky'

    def getChaseDirections(self, playerPos, playerDir):
        targetVector = list(playerPos)
        if playerDir == 1:
            targetVector[1] -= 4 * 24
        elif playerDir == 2:
            targetVector[1] += 4 * 24
        elif playerDir == 3:
            targetVector[0] -= 4 * 24
        elif playerDir == 4:
            targetVector[0] += 4 * 24
        displacementVector = list(targetVector - self.getPosition())
        return self.getDirectionPreference(pygame.Vector2(displacementVector))


class Clyde(Ghost):
    def __init__(self):
        Ghost.__init__(self, 3)
        self._name = 'Clyde'

    def getChaseDirections(self, playerPos):
        targetVector = list(playerPos)
        displacementVector = (targetVector - self.getPosition())
        if displacementVector[0] ** 2 + displacementVector[1] ** 2 < (
                8 * 24) ** 2:  # only chase if magnitude less than 8 tiles
            return self.getDirectionPreference(displacementVector)
        else:
            directionPreference = [1, 2, 3, 4]
            random.shuffle(directionPreference)
            return directionPreference


class GhostGroup:
    def __init__(self, *ghosts):
        self.__ghosts = []
        for entity in ghosts:
            self.__ghosts.append(entity)

    def normalGhostCollision(self, boundBox):
        for ghost in self.__ghosts:
            if boundBox.colliderect(ghost.getBoundBox()):
                if ghost.isScared():
                    return True

    def scaredGhostCollision(self, boundBox):
        for ghost in self.__ghosts:
            if boundBox.colliderect(ghost.getBoundBox()):
                if not (ghost.isScared()):
                    return True

    def setNormalSpeeds(self, speed):
        for ghost in self.__ghosts:
            ghost.setNormalSpeed(speed)

    def resetGhosts(self):
        for ghost in self.__ghosts:
            ghost.reset()

    def scareGhosts(self):
        for ghost in self.__ghosts:
            if not (ghost.isDead()):
                ghost.scareGhost()

    def inScaredPhase(self):
        for ghost in self.__ghosts:
            if ghost.isScared():
                return True

    def getGhosts(self):
        return self.__ghosts

    def getIndex(self, ghost):
        return self.__ghosts.index(ghost)

    def render(self, screen, dt):
        for ghost in self.__ghosts:
            ghost.render(screen, dt)


class Bots(GhostGroup):

    def addBot(self, bot):
        self.__ghosts.append(bot)


class PlayerGhosts(GhostGroup):  # This class is useful for multiplayer

    def removePlayer(self, player):
        self.__ghosts.remove(player)


class Movement:
    def __init__(self, board, pacman, blinky):
        self._board = board
        self.__pacman = pacman
        self._blinky = blinky

    def moveCPU(self, ghost):
        if ghost.isDead():
            return
        if ((self._board.coordInJunction(ghost.getPosition()[0], ghost.getPosition()[1]) and Board.getGridRef(ghost.getPosition()[0], ghost.getPosition()[1]) != ghost.getLastJunction())
                or (self._board.isNextBlockWall(ghost.getDirection(),ghost.getPosition()))):
            if ghost.isScared():
                chaseDirections = ghost.runAway(self.__pacman.getPosition())
            else:
                try:
                    chaseDirections = ghost.getChaseDirections(self.__pacman.getPosition())
                except:
                    try:
                        chaseDirections = ghost.getChaseDirections(self.__pacman.getPosition(),
                                                                   self.__pacman.getDirection())
                    except:
                        chaseDirections = ghost.getChaseDirections(self.__pacman.getPosition(),
                                                                   self.__pacman.getDirection(),
                                                                   self._blinky.getPosition())
            position = ghost.getPosition()
            gridPosition = Board.getGridRef(position[0], position[1])
            for direction in chaseDirections:
                if not (self._board.isNextBlockWall(direction, ghost.getPosition())):
                    if math.ceil(ghost.getDirection() / 2) != math.ceil(
                            direction / 2) or ghost.getDirection() == direction:  # prevents backwards movement
                        ghost.setDirection(direction)
                        ghost.setLastJunction(gridPosition)
                        break


    def movePlayer(self, player, movementKeys):
        try:
            isDead = player.isDead()
        except:
            isDead = False

        if not isDead:
            position = player.getPosition()
            gridPosition = Board.getGridRef(position[0], position[1])
            keys = pygame.key.get_pressed()
            newDirection = 0
            for key in movementKeys:
                if keys[pygame.key.key_code(key)]:
                    newDirection = movementKeys.index(key) + 1
                    break
            if player.getDirection() == 0 or math.ceil(newDirection / 2) == math.ceil(
                    player.getDirection() / 2) or self._board.coordInJunction(player.getPosition()[0],
                                                                              player.getPosition()[
                                                                                  1]):  # 1-2 returns 1, 3-4 returns 2, 0 returns 0
                if not (self._board.isNextBlockWall(newDirection, position)):
                    if newDirection != 0:
                        if newDirection != player.getDirection():
                            player.setDirection(newDirection)

            if self._board.isNextBlockWall(
                player.getDirection(), position):
                player.setDirection(0)

def getControls(player, configObject):
    keys = []
    keys.append(configObject.get(player, 'up'))
    keys.append(configObject.get(player, 'down'))
    keys.append(configObject.get(player, 'left'))
    keys.append(configObject.get(player, 'right'))
    return keys


def readDirectionFromKeys(movementKeys, pressed):
    """Pure function: given the ordered [up, down, left, right] config tokens
    and a pygame key-pressed snapshot, return 1/2/3/4 for the first matching
    direction or 0 if none pressed. Mirrors the original Movement.movePlayer
    key scan, with the pressed-state injectable for testing."""
    for i, key in enumerate(movementKeys):
        if pressed[pygame.key.key_code(key)]:
            return i + 1
    return 0


########################################################MAIN PROGRAM####################################################
def runGame(players, names, mazeString):
    names = names #ordered list of currently logged in account for each entity (empty string if no account)

    configObj = configparser.ConfigParser()
    with open ("config.ini","r") as configFile:
        configObj.read_file(configFile)
        print(configObj.sections())
        configObj.sections()

    pygame.init()
    screen = pygame.display.set_mode((720, 960))  #sets resolution to 3:4
    clock = pygame.time.Clock()
    running = True
    TIMEOFGAME = time.strftime("%Y-%m-%d %H:%M:%S")
    if configObj.get('Performance','replays') == 'False':
        RECORDGAME = False
    else:
        RECORDGAME = True
    FPS = int(configObj.get('Performance','fps'))
    dt = 0
    LEVEL = 1
    extraPlayers = players
    selectedBoard = mazeString
    board = Board(selectedBoard)
    pacman = Pacman()
    blinky = Blinky()
    inky = Inky()
    pinky = Pinky()
    clyde = Clyde()
    ghosts = GhostGroup(blinky, inky, pinky, clyde)
    movement = Movement(board, pacman, blinky)
    PLAYER1KEYS = getControls('Player 1', configObj)
    ghostsCombo = 0


    match extraPlayers:
        case 0:
            playerGhosts = PlayerGhosts()
            botGhosts = Bots(blinky, inky, pinky, clyde)
            ghostKeyList = []

        case 1:
            PLAYER2KEYS = getControls('Player 2', configObj)
            playerGhosts = PlayerGhosts(blinky)
            botGhosts = Bots(inky, pinky, clyde)
            ghostKeyList = [PLAYER2KEYS]

        case 2:
            PLAYER2KEYS = getControls('Player 2', configObj)
            PLAYER3KEYS = getControls('Player 3', configObj)
            playerGhosts = PlayerGhosts(blinky, inky)
            botGhosts = Bots(pinky, clyde)
            ghostKeyList = [PLAYER2KEYS, PLAYER3KEYS]
        case 3:
            PLAYER2KEYS = getControls('Player 2', configObj)
            PLAYER3KEYS = getControls('Player 3', configObj)
            PLAYER4KEYS = getControls('Player 4', configObj)
            playerGhosts = PlayerGhosts(blinky, inky, pinky)
            botGhosts = Bots(pinky, clyde)
            ghostKeyList = [PLAYER2KEYS, PLAYER3KEYS, PLAYER4KEYS]

        case 4:
            PLAYER2KEYS = getControls('Player 2', configObj)
            PLAYER3KEYS = getControls('Player 3', configObj)
            PLAYER4KEYS = getControls('Player 4', configObj)
            PLAYER5KEYS = getControls('Player 5', configObj)
            playerGhosts = PlayerGhosts(blinky, inky, pinky, clyde)
            botGhosts = Bots()
            ghostKeyList = [PLAYER2KEYS, PLAYER3KEYS, PLAYER4KEYS, PLAYER5KEYS]

    game = Game(3, LEVEL, board, ghosts, pacman)

    if RECORDGAME:
        fileName = time.time() #makes overlapping temp file names virtually impossible
        replayFile = open(f'replays/{fileName}',"w")
        replayFile.write(f'{FPS}\n')
        replayFile.write(f'{board.getBoardStr()}\n')

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        if game.checkIfLevelComplete():
            game.loadNextLevel()



        ###MOVEMENT###
        for ghost in ghosts.getGhosts():
            if ghost in playerGhosts.getGhosts():
                movement.movePlayer(ghost, ghostKeyList[ghosts.getIndex(ghost)])
            elif ghost in botGhosts.getGhosts():
                movement.moveCPU(ghost)

        movement.movePlayer(pacman, PLAYER1KEYS)
        ###############


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

        game.updateScore()
        game.render(screen, dt)
        pygame.display.flip()
        if RECORDGAME :
            replayFile.write(f'{pacman.getClass(), pacman.getPosition()} @{game.getTime()}\n')
            replayFile.write(f'{blinky.getClass(), blinky.getPosition()} @{game.getTime()}\n')
            replayFile.write(f'{inky.getClass(), inky.getPosition()} @{game.getTime()}\n')
            replayFile.write(f'{pinky.getClass(), pinky.getPosition()} @{game.getTime()}\n')
            replayFile.write(f'{clyde.getClass(), clyde.getPosition()} @{game.getTime()}\n')


        clock.tick(FPS)
        dt = clock.tick(FPS) / 1000

    ###INPUT TO DATABASE###

    leaderboard = database.Leaderboard()

    leaderboard.inputScore(TIMEOFGAME, game.getTime()/1000, game.getScore(), leaderboard.getMazeName(mazeString))

    matchID = leaderboard.getMatchID()
    leaderboard.addToMatchBook(names[0], matchID, pacman.getName())


    for ghost in ghosts.getGhosts():
        names = names[1:]
        if ghost in playerGhosts.getGhosts():
            leaderboard.addToMatchBook(names[0], matchID, ghost.getName())


    #REPLAY FILE STORAGE#
    if RECORDGAME:
        replayFile.close()
        import hashlib
        BUFFER = 32000
        with open(f'replays/{fileName}',"rb") as binaryReplay:
            h = hashlib.sha256()
            while True:
                data = binaryReplay.read(BUFFER)
                if not data:
                    break
                h.update(data)
        os.rename(f'replays/{fileName}', f'replays/{h.hexdigest()}')
        leaderboard.addReplay(matchID, h.hexdigest())

    leaderboard.close()

########################################################################################################################

if __name__ == "__main__":
    runGame(0, ["","","","",""], boards.encodeMaze(boards.boardsdict["default"]))
