import configparser
import os
import pygame
import pygame_menu
from pygame_menu import themes

import database
import game
import login
import mazecreator
import replay
import keyboard
import socket as _socket
import nethost
import netclient
import netgame
import boards as _boards
from netcommon import DEFAULT_PORT

pygame.init()
surface = pygame.display.set_mode((720, 960))
pygame.display.set_caption('PAC-MAN')
icon = pygame.image.load("images/icon.jpg")
pygame.display.set_icon(icon)
users = ["", "", "", "", ""]  # 5 players, if not logged in then username set to empty string

configObj = configparser.ConfigParser()
with open("config.ini", "r") as configFile:
    configObj.read_file(configFile)


# MAIN MENU BLOCK########################################################################################################
def start_the_game(players):
    game.runGame(players, users)


def openGameMenu():
    mainmenu._open(gamemenu)


def leaderboard_table():
    leaderboardmenu = pygame_menu.Menu('Choose Table', 720, 960, theme=themes.THEME_SOLARIZED)
    leaderboardmenu.add.button('Users',usersTable)
    leaderboardmenu.add.button('Matches',matchesTable)
    mainmenu._open(leaderboardmenu)

def maze_creator():
    mazecreator.main(users[0])


def openReplays():
    replaymenu = pygame_menu.Menu('Replays', 720, 960, theme=themes.THEME_SOLARIZED)
    leaderboard = database.Leaderboard()
    replayHashes = os.listdir('replays')
    loadedReplays = []
    for hash in replayHashes:
        details = leaderboard.getReplayDetails(hash)
        replaymenu.add.button(details, playReplay, hash)
        loadedReplays.append(details)
    leaderboard.close()
    mainmenu._open(replaymenu)



def openSettingsMenu():
    mainmenu._open(settingsmenu)


mainmenu = pygame_menu.Menu('Main Menu', 720, 960, theme=themes.THEME_SOLARIZED)
mainmenu.add.image('images/icon.jpg')
mainmenu.add.button('Play', openGameMenu)
mainmenu.add.button('Maze Creator', maze_creator)
mainmenu.add.button('Leaderboard', leaderboard_table)
mainmenu.add.button('Replays', openReplays)
mainmenu.add.button('Settings', openSettingsMenu)
mainmenu.add.button('Quit', pygame_menu.events.EXIT)


############################GAME(MAINMENU) BLOCK#####################################################################


def openMazeMenu():
    global mazemenu, mazeSelection
    mazesList = [("Default",
                  "++++++++++++++++++++ZlllnRlllvZ+T+TT+T+v-MT0TT0T3LZ+T+TT+T+vZllllllllvZ+TT++TT+vZ+TT++TT+vZlnRnRnRlv++T+PP+T++M0T+PP+T03M0TM003T03M0TPYfPT03++TP00PT++004300M400++TP00PT++M0TPYfPT03M0TM003T03M0TP++PT03++TP++PT++ZlllnRlllvZ+T+TT+T+vZ+T+TT+T+v-nRlk5lnRL+TTT++TTT++TTT++TTT+ZlnRnRnRlvZ+++TT+++vZ+++TT+++vZllllllllv++++++++++++++++++++")]
    leaderboard = database.Leaderboard()
    for item in leaderboard.getMazes():
        fullName = str(f'{item[0]} by {item[1]}')
        mazeString = item[2]
        mazesList.append((fullName, mazeString))
    leaderboard.close()
    mazeSelection.update_items(items=mazesList)
    gamemenu._open(mazemenu)


gamemenu = pygame_menu.Menu('Player Selection', 720, 960, theme=themes.THEME_SOLARIZED)
playerSelection = gamemenu.add.selector("Choose players: ",
                                        [('Single Player', 0), ('2 players', 1), ('3 players', 2), ('4 players', 3),
                                         ('5 players', 4)])
gamemenu.add.button('Enter', openMazeMenu)


def openOnlineMenu():
    gamemenu._open(onlinemenu)


gamemenu.add.button("Online", openOnlineMenu)


def _get_lan_ip():
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def openHostSetup():
    onlinemenu._open(hostsetupmenu)


def openJoinSetup():
    onlinemenu._open(joinsetupmenu)


onlinemenu = pygame_menu.Menu("Online", 720, 960, theme=themes.THEME_SOLARIZED)
onlinemenu.add.button("Host", openHostSetup)
onlinemenu.add.button("Join", openJoinSetup)


# Host setup — player count, maze, port
def _buildHostMazesList():
    result = [("Default",
               "++++++++++++++++++++ZlllnRlllvZ+T+TT+T+v-MT0TT0T3LZ+T+TT+T+vZllllllllvZ+TT++TT+vZ+TT++TT+vZlnRnRnRlv++T+PP+T++M0T+PP+T03M0TM003T03M0TPYfPT03++TP00PT++004300M400++TP00PT++M0TPYfPT03M0TM003T03M0TP++PT03++TP++PT++ZlllnRlllvZ+T+TT+T+vZ+T+TT+T+v-nRlk5lnRL+TTT++TTT++TTT++TTT+ZlnRnRnRlvZ+++TT+++vZ+++TT+++vZllllllllv++++++++++++++++++++")]
    lb = database.Leaderboard()
    for item in lb.getMazes():
        result.append((f"{item[0]} by {item[1]}", item[2]))
    lb.close()
    return result


hostsetupmenu = pygame_menu.Menu("Host Setup", 720, 960, theme=themes.THEME_SOLARIZED)
hostsetupmenu.add.label(f"Your LAN IP: {_get_lan_ip()}")
hostPlayerSelector = hostsetupmenu.add.selector(
    "Players: ",
    [("2 players", 1), ("3 players", 2), ("4 players", 3), ("5 players", 4)],
)
hostMazeSelector = hostsetupmenu.add.selector(
    "Maze: ", items=_buildHostMazesList())
hostPortInput = hostsetupmenu.add.text_input(
    "Port: ", default=str(DEFAULT_PORT), maxchar=5,
    textinput_id="host_port", input_type=pygame_menu.locals.INPUT_INT,
)
hostsetupmenu.add.label("(Forward this UDP port on your router for internet play)")
hostStatusLabel = hostsetupmenu.add.label("", label_id="host_status")


def startHostingFromMenu():
    if users[0] == "":
        hostStatusLabel.set_title("Host must be logged in.")
        return
    port = int(hostsetupmenu.get_widget("host_port").get_value())
    maze_string = hostMazeSelector.get_value()[0][1]
    max_clients = hostPlayerSelector.get_value()[0][1]  # 1..4
    session = nethost.HostSession(
        bind_port=port, maze_string=maze_string, max_clients=max_clients)
    try:
        session.start()
    except OSError as err:
        hostStatusLabel.set_title(f"Port busy: {err}")
        return
    runHostLobbyLoop(session, max_clients, maze_string)


hostsetupmenu.add.button("Start hosting", startHostingFromMenu)


#################MAZECHOICE(GAME) BLOCK###########################################################################

def playGame(names):
    print(mazeSelection.get_value()[0])
    game.runGame(playerSelection.get_value()[1], names, mazeSelection.get_value()[0][1])
    mazemenu._back()  # Move back to main menu
    gamemenu._back()


mazesList = [("Default",
              "++++++++++++++++++++ZlllnRlllvZ+T+TT+T+v-MT0TT0T3LZ+T+TT+T+vZllllllllvZ+TT++TT+vZ+TT++TT+vZlnRnRnRlv++T+PP+T++M0T+PP+T03M0TM003T03M0TPYfPT03++TP00PT++004300M400++TP00PT++M0TPYfPT03M0TM003T03M0TP++PT03++TP++PT++ZlllnRlllvZ+T+TT+T+vZ+T+TT+T+v-nRlk5lnRL+TTT++TTT++TTT++TTT+ZlnRnRnRlvZ+++TT+++vZ+++TT+++vZllllllllv++++++++++++++++++++")]

mazemenu = pygame_menu.Menu('Maze Selection', 720, 960, theme=themes.THEME_SOLARIZED)
mazeSelection = mazemenu.add.selector('Choose Maze: ', items=mazesList)
mazemenu.add.button('Play game', playGame, users)

############################LEADERBOARD BLOCK#################################################
def matchesTable():
    leaderboard = database.Leaderboard()
    matchesList = leaderboard.getAllMatchInfo()
    leaderboard.close()
    matchesmenu = pygame_menu.Menu('Matches', 720, 960, theme=themes.THEME_SOLARIZED)
    matchesTable = matchesmenu.add.table('Leaderboard Table')
    matchesTable.add_row(("Time Played","Match Length","Score","Players", "Ghosts", "Maze Name"))
    for match in matchesList:
        match = list(match)
        for i in range(len(match)):
            if match[i] == None:
                match[i] = ""
        matchesTable.add_row(match)
    mainmenu._open(matchesmenu)

def usersTable():
    leaderboard = database.Leaderboard()
    userList = leaderboard.getAllUserInfo()
    leaderboard.close()
    playersmenu = pygame_menu.Menu('Players', 720, 960, theme=themes.THEME_SOLARIZED)
    playersTable = playersmenu.add.table('Players Table')
    playersTable.add_row(("Username","Creation Date", "Pacman games ","Ghost games", "Average Score", "High Score"))

    for player in userList:
        playerDetails = list(player) #tuple converted to list to change items as tuples are immutable
        for i in range(len(playerDetails)):
            if playerDetails[i] == None:
                playerDetails[i] = ""
        playersTable.add_row(playerDetails)
    mainmenu._open(playersmenu)


leaderboardmenu = pygame_menu.Menu('Choose Table', 720, 960, theme=themes.THEME_SOLARIZED)
leaderboardmenu.add.button('Users', usersTable)
leaderboardmenu.add.button('Matches', matchesTable)

matchesmenu = pygame_menu.Menu('Matches', 720, 960, theme=themes.THEME_SOLARIZED)
playersmenu = pygame_menu.Menu('Players', 720, 960, theme=themes.THEME_SOLARIZED)


#REPLAYS(MAINMENU) BLOCK#############################################
replayHashes = [' ']

def playReplay(replayHash):
    replay.replay(f'replays/{replayHash}')
    replaymenu._close()

replaymenu = pygame_menu.Menu('Replays', 720, 960, theme=themes.THEME_SOLARIZED)


# SETTINGS(MAINMENU) BLOCK ######################################################################################
def openPerformanceSettings():
    settingsmenu._open(performancesettings)


def openControlSettings():
    settingsmenu._open(controlsettings)


def playerChoiceMenu(mode):
    if mode == 'c':
        settingsmenu._open(playercontrolmenu)
    if mode == 'a':
        settingsmenu._open(playeraccountmenu)


settingsmenu = pygame_menu.Menu('Settings', 720, 960, theme=themes.THEME_SOLARIZED)
settingsmenu.add.button('Performance', openPerformanceSettings)
settingsmenu.add.button('Controls', playerChoiceMenu, 'c')  # player choice leads to controls
settingsmenu.add.button('Accounts', playerChoiceMenu, 'a')  # player choice leads to account management
playerNum = 1  # Keeps track of the player for config file editing


# PERFORMANCE(SETTINGS) BLOCK ###################################################################
def savePerformanceSettings(configObj):
    newFPS = performancesettings.get_widget("FPS").get_value()
    if newFPS <= 0:
        performancesettings.get_widget("FPS").set_value(60)
        newFPS = 60
    replayChoice = performancesettings.get_widget("replays_choice").get_value()
    configObj['Performance']['fps'] = str(newFPS)
    configObj['Performance']['replays'] = str(replayChoice)
    with open('config.ini', 'w') as configFile:
        configObj.write(configFile)
    performancesettings._back()


performancesettings = pygame_menu.Menu('Performance', 720, 960, theme=themes.THEME_SOLARIZED)
performancesettings.add.text_input(
    'FPS: ',
    default=int(configObj.get('Performance', 'fps')),
    maxchar=3,
    maxwidth=4,
    textinput_id='FPS',
    input_type=pygame_menu.locals.INPUT_INT,
    cursor_selection_enable=False
)
performancesettings.add.toggle_switch('Record replays', True,
                                      toggleswitch_id='replays_choice',
                                      state_text=('False', 'True'))

performancesettings.add.button('Save choice', savePerformanceSettings, configObj)


# CONTROLS(SETTINGS) BLOCK ###################################################################

##Player choice######
def changePlayerControl(playerNum):
    global upButton, downButton, leftButton, rightButton
    upkey = configObj.get(f'Player {playerNum}', 'up')
    downkey = configObj.get(f'Player {playerNum}', 'down')
    leftkey = configObj.get(f'Player {playerNum}', 'left')
    rightkey = configObj.get(f'Player {playerNum}', 'right')
    upButton.set_title(f'Up key: {upkey}')
    downButton.set_title(f'Down key: {downkey}')
    leftButton.set_title(f'Left key: {leftkey}')
    rightButton.set_title(f'Right key: {rightkey}')

    playercontrolmenu._open(controlsettings)


playercontrolmenu = pygame_menu.Menu('Controls', 720, 960, theme=themes.THEME_SOLARIZED)
playercontrolmenu.add.button("Player 1", changePlayerControl, 1)
playercontrolmenu.add.button("Player 2", changePlayerControl, 2)
playercontrolmenu.add.button("Player 3", changePlayerControl, 3)
playercontrolmenu.add.button("Player 4", changePlayerControl, 4)
playercontrolmenu.add.button("Player 5", changePlayerControl, 5)


def setKey(direction):
    while True:
        if keyboard.read_key():
            newKey = keyboard.read_key()
            break

    match direction:
        case 'up':
            global upkey
            upkey = newKey
            upButton.set_title(f'Up key: {upkey}')
        case 'down':
            global downkey
            downkey = newKey
            downButton.set_title(f'Down key: {downkey}')
        case 'left':
            global leftkey
            leftkey = newKey
            leftButton.set_title(f'Left key: {leftkey}')
        case 'right':
            global rightkey
            rightkey = newKey
            rightButton.set_title(f'Right key: {rightkey}')


def saveNewControls(configObj):
    configObj[f'Player {playerNum}']['up'] = upkey
    configObj[f'Player {playerNum}']['down'] = downkey
    configObj[f'Player {playerNum}']['left'] = leftkey
    configObj[f'Player {playerNum}']['right'] = rightkey
    with open('config.ini', 'w') as configFile:
        configObj.write(configFile)
    controlsettings._back()


controlsettings = pygame_menu.Menu('Controls', 720, 960, theme=themes.THEME_SOLARIZED)
upkey = configObj.get(f'Player {playerNum}', 'up')
downkey = configObj.get(f'Player {playerNum}', 'down')
leftkey = configObj.get(f'Player {playerNum}', 'left')
rightkey = configObj.get(f'Player {playerNum}', 'right')
upButton = controlsettings.add.button(f'Up key: {upkey}', setKey, 'up')
downButton = controlsettings.add.button(f'Down key: {downkey}', setKey, 'down')
leftButton = controlsettings.add.button(f'Left key: {leftkey}', setKey, 'left')
rightButton = controlsettings.add.button(f'Right key: {rightkey}', setKey, 'right')
controlsettings.add.button("Save", saveNewControls, configObj)


# ACCOUNT MANAGER(SETTINGS) BLOCK ###################################################################

def changePlayerAccount(player):
    openAccountManager(player)


playeraccountmenu = pygame_menu.Menu('Accounts', 720, 960, theme=themes.THEME_SOLARIZED)
accountButton1 = playeraccountmenu.add.button(f'Player 1: {users[0]}', changePlayerAccount, 1)
accountButton2 = playeraccountmenu.add.button(f'Player 2: {users[1]}', changePlayerAccount, 2)
accountButton3 = playeraccountmenu.add.button(f'Player 3: {users[2]}', changePlayerAccount, 3)
accountButton4 = playeraccountmenu.add.button(f'Player 4: {users[3]}', changePlayerAccount, 4)
accountButton5 = playeraccountmenu.add.button(f'Player 5: {users[4]}', changePlayerAccount, 5)


def openAccountManager(userNum):
    global users
    returnedUsername = login.openTab(users[userNum - 1])
    users[userNum - 1] = returnedUsername
    playeraccountmenu.get_selected_widget().set_title(f'Player {userNum}: {users[userNum - 1]}')


#################################################################################################

arrow = pygame_menu.widgets.LeftArrowSelection(arrow_size=(10, 15))

update_loading = pygame.USEREVENT + 0

while True:
    events = pygame.event.get()
    for event in events:
        if event.type == pygame.QUIT:
            exit()

    if mainmenu.is_enabled():
        mainmenu.update(events)
        mainmenu.draw(surface)
        if mainmenu.get_current().get_selected_widget():
            arrow.draw(surface, mainmenu.get_current().get_selected_widget())
    pygame.display.update()
