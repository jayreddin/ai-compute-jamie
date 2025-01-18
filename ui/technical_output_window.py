import threading
import webbrowser
from multiprocessing import Queue
from pathlib import Path
import logging
import tkinter as tk

import speech_recognition as sr
import ttkbootstrap as ttk
from PIL import Image, ImageTk

from llm import DEFAULT_MODEL_NAME
from settings import Settings  # Updated import
from version import version

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def open_link(url) -> None:
    webbrowser.open_new(url)

class TechnicalOutputWindow(ttk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title('Technical Output')
        self.geometry("600x400")
        self.protocol("WM_DELETE_WINDOW", self.close_window) #handle the close window event
        self.create_widgets()
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)


    def create_widgets(self) -> None:
        try:
            # Creates and arranges the UI elements
            # Frame
            frame = ttk.Frame(self, padding='10 10 10 10')
            frame.grid(column=0, row=0, sticky=(ttk.W, ttk.E, ttk.N, ttk.S))
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(1, weight = 1)

            # Text display for additional messages
            log_label = ttk.Label(frame, text='Log Output', font=('Helvetica', 12), bootstyle="secondary")
            log_label.grid(column=0, row=0, columnspan=3, sticky=ttk.W, pady=(0, 5))

            self.message_display = ttk.ScrolledText(frame, wrap=ttk.WORD, font=('Helvetica', 10),  height=15)
            self.message_display.grid(column=0, row=1, columnspan=3, sticky=(ttk.W, ttk.E, ttk.N, ttk.S), pady=(0, 5))

            # Redirect logging to text widget
            class TkLoggingHandler(logging.Handler):
                def __init__(self, text_widget):
                    super().__init__()
                    self.text_widget = text_widget

                def emit(self, record):
                    msg = self.format(record)
                    self.text_widget.insert(ttk.END, msg + '\n')
                    self.text_widget.see(ttk.END)  # Scroll to end
            handler = TkLoggingHandler(self.message_display)
            logging.getLogger().addHandler(handler)
            logging.info("Technical Output window created successfully")
        except Exception as e:
            logging.error(f'Error creating technical output window: {e}')


    def close_window(self):
        """Closes the window and removes the handler"""
        logging.info("Closing Technical Output window")
        for handler in logging.getLogger().handlers[:]: #make a copy of the list to avoid errors
            if isinstance(handler, TkLoggingHandler):
                logging.getLogger().removeHandler(handler)
        self.destroy() # closes the window