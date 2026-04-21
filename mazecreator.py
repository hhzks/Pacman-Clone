from tkinter import messagebox, simpledialog
import time
import pygame
import boards
from database import Leaderboard
from game import Board, Square
from collections import deque

class Creator(Board):
    def __init__(self, board):
        Board.__init__(self, board)
        self.__UndoStack = deque()
        self.__RedoStack = deque()
        self.__occupiedCells = [(14, 24), (16, 16), (16, 14), (13, 16), (13, 14)]
        self.__blankBoard = boards.boardsdict["blank"]

    def undo(self):
        try:
            changedCells = self.__UndoStack.pop()
            for item in changedCells:
                self._board[item[1]][item[0]] = changedCells[item][0]
                if self.isHorizontalBorder(item[1], item[0]):
                    self._board[item[1]][29 - item[0]] = changedCells[item][0]
            self.__RedoStack.push(changedCells)

        except:
            print("Cannot undo further")

    def redo(self):
        try:
            changedCells = self.__RedoStack.pop()
            for item in changedCells:
                self._board[item[1]][item[0]] = changedCells[item][1]
                if self.isHorizontalBorder(item[1], item[0]):
                    self._board[item[1]][29 - item[0]] = changedCells[item][1]
            self.__UndoStack.push(changedCells)

        except:
            print("Cannot redo further")

    def resetRedoStack(self):
        self.__RedoStack.empty()

    def pushToUndoStack(self, value):
        self.__UndoStack.push(value)

    def changeCell(self, x, y, val):
        try:
            self._board[y][x] = val
        except:
            print("Out of range!")

    @staticmethod
    def checkGridType(y, x):
        print(y, x)
        if y == 0 or y == 32:
            return 1
        if x == 0 or x == 29:
            return 2
        else:
            return 3

    def isVerticalBorder(self, y, x):
        if self.checkGridType(y, x) == 1:
            return True

    def isHorizontalBorder(self, y, x):
        if self.checkGridType(y, x) == 2:
            return True

    def createWarp(self, x, y):
        pass

    def clearBoard(self):
        self._board.clear()
        for item in self.__blankBoard:
            self._board.append(item)
        self.__UndoStack.empty()
        self.__RedoStack.empty()

    def render(self, screen):
        for i in range(len(self._board)):
            for j in range(len(self._board[i])):
                pos = self.getCoord(j, i)
                if self._board[i][j] == 1:
                    pygame.draw.circle(screen, "white", pos, 3)
                elif self._board[i][j] == 2:
                    pygame.draw.circle(screen, "white", pos, 6)
                elif self._board[i][j] == 3:
                    pygame.draw.rect(screen, "blue", Square(pos[0], pos[1], 24))

        for item in self.__occupiedCells:
            pygame.draw.circle(screen, "red", self.getCoord(item[0], item[1]), 12)

    @staticmethod
    def getButtonValue(button):  # 0 is left button, 1 is middle button, 2 is right button
        match button:
            case 0:
                return 3
            case 1:
                return 2
            case 2:
                return 0
            case 3:
                return 1

    def getCellType(self, cell):
        return self._board[cell[1]][cell[0]]

    def handleClick(self, button):
        currentPos = Creator.getGridRef(pygame.mouse.get_pos()[0], pygame.mouse.get_pos()[1])
        if not (0 <= currentPos[0] <= 29) or not (0 <= currentPos[1] <= 32):
            print("Out of bounds")
            return

        if currentPos in self.__occupiedCells:
            return

        buttonValue = self.getButtonValue(button)
        if not (self.isVerticalBorder(currentPos[1], currentPos[0])) and self.getCellType(currentPos) != buttonValue:
            currentPos = Creator.getGridRef(pygame.mouse.get_pos()[0], pygame.mouse.get_pos()[1])
            currentValue = self.getCellType(currentPos)
            self.changeCell(currentPos[0], currentPos[1], buttonValue)
            if self.isHorizontalBorder(currentPos[1], currentPos[0]):
                self.changeCell(29 - currentPos[0], currentPos[1], buttonValue)
            return {currentPos: (currentValue, buttonValue)}  # Returns changed cell

    def validateMaze(self):
        # Record position of wall cells and pellet cells
        wallCoords = []
        pelletCoords = []
        for j in range(len(self._board)):
            for i in range(len(self._board[j])):
                if self._board[j][i] == 3:
                    wallCoords.append((i, j))
                if self._board[j][i] == 1 or self._board[j][i] == 2:
                    pelletCoords.append((i, j))

        # automatically return invalid if no pellets in maze
        if len(pelletCoords) == 0:
            messagebox.showerror("Error", "No pellets in maze")
            return False

        # BFS to check if all pellets can be accessed
        visitedList = []
        startPosition = (14, 24)  # This is where the player always begins
        searchQueue = deque()
        searchQueue.appendleft(startPosition)
        validMoves = [(1, 0), (0, 1), (-1, 0), (0, -1)]
        while not (searchQueue.isEmpty()):  # keep on going until queue is empty (no more new nodes to discover)
            currentNode = searchQueue.pop()
            visitedList.append(currentNode)
            addTuples = lambda tuple, tuplesList: [((tuple[0] + i[0]) % 30, (tuple[1] + i[1]) % 33) for i in
                                                   tuplesList]  # map current node onto allowed movement vectors
            currentNeighbours = addTuples(currentNode, validMoves)
            for node in currentNeighbours:
                if (not (node in wallCoords)) and (not (node in visitedList)):
                    searchQueue.appendleft(node)
                    visitedList.append(node)
                    if node in pelletCoords:
                        pelletCoords.remove(node)
        # If all pellets are accessed, maze is valid
        if len(pelletCoords) == 0:
            return True
        else:
            messagebox.showerror("Error", "Some pellets are inaccessible")
            return False


def main(username):
    board = boards.boardsdict["default"]
    pygame.init()
    screen = pygame.display.set_mode((720, 960))
    running = True
    customBoard = Creator(boards.encodeMaze(board))
    saveButton = pygame.Rect((600, 900), (100, 50))
    clearButton = pygame.Rect((300, 900), (200, 50))
    changedCells = {}
    keyHeld = False
    Save = False

    while running:
        keys = pygame.key.get_pressed()
        screen.fill("black")
        pygame.draw.rect(screen, "blue", saveButton)
        pygame.draw.rect(screen, "blue", clearButton)
        my_font = pygame.font.SysFont('Jokerman', 30)
        saveText = my_font.render("Save", False, "White")
        screen.blit(saveText, (610, 900))
        customBoard.render(screen)
        clearText = my_font.render("Clear Maze", False, "White")
        screen.blit(clearText, (310, 900))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.MOUSEBUTTONUP:
                customBoard.resetRedoStack()
                customBoard.pushToUndoStack(changedCells)
                changedCells = {}
            if event.type == pygame.KEYUP:
                keyHeld = False

        for i in range(5):
            if pygame.mouse.get_pressed(num_buttons=5)[i]:
                if saveButton.collidepoint(pygame.mouse.get_pos()):
                    if customBoard.validateMaze():
                        running = False
                        Save = True
                        break
                elif clearButton.collidepoint(pygame.mouse.get_pos()):
                    print("eag")
                    customBoard.clearBoard()
                try:
                    changedCells.update(customBoard.handleClick(i))
                    break
                except:
                    pass

        if saveButton.collidepoint(pygame.mouse.get_pos()):
            pygame.draw.rect(screen, (0, 0, 102), saveButton)
            saveText = my_font.render("Save", False, (200, 200, 200))
            screen.blit(saveText, (610, 900))

        if clearButton.collidepoint(pygame.mouse.get_pos()):
            pygame.draw.rect(screen, (0, 0, 102), clearButton)
            clearText = my_font.render("Clear Maze", False, (200, 200, 200))
            screen.blit(clearText, (310, 900))

        if keys[pygame.K_z] and not keyHeld:
            customBoard.undo()
            keyHeld = True

        if keys[pygame.K_r] and not keyHeld:
            customBoard.redo()
            keyHeld = True

        pygame.display.flip()

    ###SAVING####
    if Save:
        name = simpledialog.askstring("Saving", "Enter maze name: ")
        if name:
            leaderboard = Leaderboard()
            try:
                leaderboard.storeMaze(name, boards.encodeMaze(customBoard.getBoard()), username,
                                      time.strftime("%Y-%m-%d %H:%M:%S"))
            except:
                messagebox.showerror("Error", "Error occurred, could not store maze")
            leaderboard.close()


if __name__ == "__main__":
    main("")
