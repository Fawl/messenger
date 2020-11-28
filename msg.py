#! /usr/bin/env python3
##
import atexit
import ctypes
import curses
import hashlib
import json
import socket
import threading
from datetime import datetime
 
import pyaes
 
BROADCAST = "10.0.0.255"
PORT = 42069
 
CHUNK_SIZE = 4096
 
 
class HistoryWindow:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.max_y = self.max_x = 0, 0
        self.border = None
        self.win = None
 
        self.history = []
 
        self.refresh()
 
    def refresh(self):
        self.max_y, self.max_x = self.stdscr.getmaxyx()
        self.border = self.stdscr.subwin(self.max_y - 5, self.max_x, 0, 0)
        self.win = self.border.subwin(self.max_y - 7, self.max_x - 2, 1, 1)
        self.border.border(0)
        self.win.scrollok(True)
 
        # Add current history
        history = self.history
        if len(history) > self.max_y - 7:
            history = history[-(self.max_y - 7):]
 
        for line in history:
            try:
                self.win.addstr(line.rstrip("\n") + "\n")
            except Exception as e:
                self.win.scroll()
 
        # Refresh internal window
        self.win.refresh()
 
    def add_history(self, s):
        self.history.append(s)
 
 
class TextboxWindow:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.max_y = self.max_x = 0, 0
        self.border = None
        self.win = None
 
        self.input_buffer = "> "
 
        self.refresh()
 
    def refresh(self):
        self.max_y, self.max_x = self.stdscr.getmaxyx()
        self.border = self.stdscr.subwin(5, self.max_x, self.max_y - 5, 0)
        self.win = self.border.subwin(2, self.max_x - 2, self.max_y - 3, 1)
        self.border.border(0)
        self.win.scrollok(True)
 
        # Add current input
        try:
            self.win.addstr(self.input_buffer.rstrip("\n") + "\n", curses.A_BLINK)
        except Exception as e:
            self.win.scroll()
 
        # Refresh internal window
        self.win.refresh()
 
    def handle_input(self, input_buffer):
        self.input_buffer = f"> {input_buffer}"
        self.refresh()
 
 
class Console:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.stdscr.border(0)
 
        self.max_y, self.max_x = stdscr.getmaxyx()
        self.history = HistoryWindow(stdscr)
        self.textbox = TextboxWindow(stdscr)
 
        self.refresh()
 
    def refresh(self):
        self.stdscr.clear()
        self.history.refresh()
        self.textbox.refresh()
        self.stdscr.refresh()
 
    def add_line(self, inpt):
        self.history.add_history(inpt)
        self.refresh()
 
    def handle_input(self, inpt):
        self.textbox.handle_input(inpt)
        self.refresh()
 
 
class Link:
 
    def encrypt(self, message):
        key = hashlib.md5(self.key.encode()).digest()
        aes = pyaes.AESModeOfOperationCTR(key)
        return aes.encrypt(message)
 
    def decrypt(self, message):
        key = hashlib.md5(self.key.encode()).digest()
        aes = pyaes.AESModeOfOperationCTR(key)
        return aes.decrypt(message)
 
    def socket_listener(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind(("", PORT))
 
            while True:
                payload, address = s.recvfrom(CHUNK_SIZE)
                payload = self.decrypt(payload).decode()
 
                try:
                    payload = json.loads(payload)
                    self.console.add_line(f"{payload['name']} @ {payload['timestamp']}: {payload['message']}\n")
                except:
                    self.console.add_line(f"{address}: {payload}")
 
                # Alert user
                ctypes.windll.user32.FlashWindow(ctypes.windll.kernel32.GetConsoleWindow(), True)
 
    def send(self, message):
        timestamp = datetime.now().strftime("%H%M")
        payload = {"name": self.name, "message": message, "timestamp": timestamp}
        payload = json.dumps(payload)
        payload = self.encrypt(payload)
        msgs = [payload[i:i + CHUNK_SIZE] for i in range(0, len(payload), CHUNK_SIZE)]
 
        for msg in msgs:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                s.connect((BROADCAST, PORT))
                s.sendall(msg)
 
    def start_console(self):
        # Initial
        self.console.add_line(f"Console started with default username '{self.name}' and key '{self.key}'")
 
        # Loop forever
        input_buffer = []
        while True:
            ch = self.stdscr.getch()
 
            if ch == ord("\n"):
                inpt_str = "".join(input_buffer)
 
                # Command system?
                if inpt_str.startswith("/"):
                    inpt_str = inpt_str[1:].split(" ")
 
                    if inpt_str[0] == "nick":
                        self.name = inpt_str[1]
                        self.console.add_line(f"Successfully set name to {self.name}")
                        del input_buffer[:]
                        continue
                    if inpt_str[0] == "key":
                        self.key = inpt_str[1]
                        self.console.add_line(f"Successfully set key to {self.key}")
                        del input_buffer[:]
                        continue
                else:
                    if self.name == "anonymoose":
                        self.console.add_line("PLEASE CHANGE YOUR NAME WITH /nick FIRST!")
                        del input_buffer[:]
                        continue
 
                    del input_buffer[:]
                    self.send(inpt_str)
 
            elif ch == 3:
                raise KeyboardInterrupt
 
            elif ch == 26:
                raise EOFError
 
            elif ch == curses.KEY_RESIZE:
                # self.console.draw()
                self.console.refresh()
 
            elif ch == curses.KEY_BACKSPACE or ch == 127 or chr(ch) == "\b":
                if len(input_buffer) > 0:
                    del input_buffer[-1]
 
            elif ch < 256:
                input_buffer.append(chr(ch))
 
            # Update input
            self.console.handle_input("".join(input_buffer))
 
    # def exit(self):
    #     self._send("LOGGED OUT".encode())
 
    def __init__(self, stdscr):
        # Prepare keys
        self.key = "sit2020"
 
        # Start listener thread
        self.listener = threading.Thread(target=self.socket_listener)
        self.listener.daemon = True
        self.listener.start()
 
        # Get name
        self.name = "desktop"
 
        # Set screen
        self.stdscr = stdscr
        self.console = Console(self.stdscr)
 
        # # Log "in"
        # self._send("LOGGED IN".encode())
 
        # # Atexit
        # atexit.register(self.exit)
 
        # Receive input
        self.start_console()
 
 
if __name__ == "__main__":
    # os.system('mode con: cols=40 lines=30')
    curses.wrapper(Link)
