import tkinter
import database
from tkinter import messagebox


class AccountManager:
    def __init__(self, user):
        self.__window = tkinter.Tk()
        self.__window.title("Account Manager")
        self.__window.geometry('300x400')
        self.__leaderboard = database.Leaderboard()
        self.__user = user

    @staticmethod
    def displayWidgets(*widgets):
        for widget in widgets:
            widget.grid()

    def getUser(self):
        return self.__user

    def attemptLogin(self, username, password):
        if self.__leaderboard.checkValidLogin(username, password) == 0:
            self.__leaderboard.close()
            self.__user = username
            messagebox.showinfo("Successful login", f'Successfully logged in as {self.__user}')
        elif self.__leaderboard.checkValidLogin(username, password) == 1:
            messagebox.showwarning("Unsuccessful login", "Incorrect password")
        elif self.__leaderboard.checkValidLogin(username, password) == 2:
            messagebox.showwarning("Unsuccessful login", "User does not exist")

    def createAccount(self, username, password):
        if not username:
            messagebox.showwarning("Issue", "Username is blank")
            return
        try:
            self.__leaderboard.addUserToDatabase(username, password)
            self.__leaderboard.close()
            self.__user = username
            messagebox.showinfo("Successful creation", f'Successfully created account {self.__user}')
        except:
            messagebox.showerror("Failure", "Failed to create user profile, profile likely already exists")

    def signOut(self):
        self.__user = ""
        messagebox.showinfo("Successful sign out", f'Successfully signed out')

    def deleteAccount(self):
        try:
            self.__leaderboard.deleteUser(self.__user)
            self.__leaderboard.close()
            self.__user = ""
            messagebox.showinfo("Successful deletion", f"Successfully deleted account {self.__user}")
        except:
            messagebox.showerror("Failure", f"Could not delete {self.__user}")

    def signIn(self, *widgets):
        for widget in widgets:
            widget.destroy()
        usernameLabel = tkinter.Label(self.__window, text="Username: ")
        username = tkinter.Entry(self.__window)
        passwordLabel = tkinter.Label(self.__window, text="Password: ")
        password = tkinter.Entry(self.__window)
        logInButton = tkinter.Button(self.__window, text="Log In",
                                     command=lambda: self.attemptLogin(username.get(), password.get()))
        goBackButton = tkinter.Button(self.__window, text="Go back",
                                      command=lambda: self.main(usernameLabel, username, passwordLabel, password,
                                                                logInButton, goBackButton))
        self.displayWidgets(usernameLabel, username, passwordLabel, password, logInButton, goBackButton)

    def signUp(self, *widgets):
        for widget in widgets:
            widget.destroy()
        usernameLabel = tkinter.Label(self.__window, text="Username: ")
        username = tkinter.Entry(self.__window)
        passwordLabel = tkinter.Label(self.__window, text="Password: ")
        password = tkinter.Entry(self.__window)
        createAccountButton = tkinter.Button(self.__window, text="Create Account",
                                             command=lambda: self.createAccount(username.get(), password.get()))
        goBackButton = tkinter.Button(self.__window, text="Go back",
                                      command=lambda: self.main(usernameLabel, username, passwordLabel, password,
                                                                createAccountButton,
                                                                goBackButton))
        self.displayWidgets(usernameLabel, username, passwordLabel, password, createAccountButton, goBackButton)

    def deleteAccountMenu(self, *widgets):
        if self.__user != "":
            for widget in widgets:
                widget.destroy()
            confirmationLabel = tkinter.Label(self.__window, text="Are you sure you want to delete your account?")
            yesButton = tkinter.Button(self.__window, text="Yes",
                                       command=lambda: self.deleteAccount())
            noButton = tkinter.Button(self.__window, text="No",
                                      command=lambda: self.main(confirmationLabel, yesButton, noButton))
            self.displayWidgets(confirmationLabel, yesButton, noButton)

    def main(self, *widgets):
        for widget in widgets:
            widget.destroy()
        signInButton = tkinter.Button(self.__window, text="Sign in",
                                      command=lambda: self.signIn(signInButton, signUpButton, signOutButton,
                                                                  deleteAccountButton))
        signUpButton = tkinter.Button(self.__window, text="Sign up",
                                      command=lambda: self.signUp(signInButton, signUpButton, signOutButton,
                                                                  deleteAccountButton))
        deleteAccountButton = tkinter.Button(self.__window, text="Delete account",
                                             command=lambda: self.deleteAccountMenu(signInButton, signUpButton,
                                                                                    signOutButton, deleteAccountButton))
        signOutButton = tkinter.Button(self.__window, text="Log out",
                                       command=lambda: self.signOut())
        signInButton.grid(row=1, column=0)
        signUpButton.grid(row=1, column=1)
        signOutButton.grid(row=1, column=2)
        deleteAccountButton.grid(row=1, column=3)
        if self.__user:
            accountLabel = tkinter.Label(self.__window, text=f"Currently signed in as {self.__user}")
            accountLabel.grid(row=0, column=0)

        self.__window.mainloop()


def openTab(user):
    accountManager = AccountManager(user)
    accountManager.main()
    return accountManager.getUser()
