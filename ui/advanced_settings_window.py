import threading
import webbrowser
from multiprocessing import Queue
from pathlib import Path
import logging

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


class AdvancedSettingsWindow(ttk.Toplevel):
    """
    Self-contained settings sub-window for the UI
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title('Advanced Settings')
        self.minsize(300, 300)
        self.settings = Settings()
        self.create_widgets()
        self.load_settings() # Load settings and set values
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def load_settings(self):
        """Load settings and populate the UI elements"""
        settings_dict = self.settings.get_dict()

        if 'base_url' in settings_dict:
            self.base_url_entry.insert(0, settings_dict['base_url'])

        model = settings_dict.get('model', DEFAULT_MODEL_NAME)
        self.model_var.set(model if model in [item[1] for item in self.models] else 'custom')
        if model not in [item[1] for item in self.models]:
            self.model_entry.insert(0, model)

    def create_widgets(self) -> None:
        # Frame
        frame = ttk.Frame(self, padding='10 10 10 10')
        frame.grid(column=0, row=0, sticky=(ttk.W, ttk.E, ttk.N, ttk.S))
        frame.columnconfigure(0, weight=1)

        # Radio buttons for model selection
        ttk.Label(frame, text='Select Model:', bootstyle="primary").pack(pady=10, padx=10)
        self.model_var = ttk.StringVar(value='custom')  # default selection

        # Create a frame to hold the radio buttons
        radio_frame = ttk.Frame(frame)
        radio_frame.pack(padx=20, pady=10, fill=ttk.X)  # Add padding around the frame

        self.models = [
            ('GPT-4o (Default. Medium-Accurate, Medium-Fast)', 'gpt-4o'),
            ('GPT-4o-mini (Cheapest, Fastest)', 'gpt-4o-mini'),
            ('GPT-4v (Deprecated. Most-Accurate, Slowest)', 'gpt-4-vision-preview'),
            ('GPT-4-Turbo (Least Accurate, Fast)', 'gpt-4-turbo'),
            ('Claude 3 Sonnet (Good Quality, Medium Speed, No Images)', 'claude-3-sonnet'),
             ('Mistral Large (Text and Code, No Images)', 'mistral-large'),
            ('Custom (Specify Settings Below)', 'custom')
        ]
        for text, value in self.models:
            ttk.Radiobutton(radio_frame, text=text, value=value, variable=self.model_var, bootstyle="info", command = self.update_model_entry).pack(
                anchor=ttk.W, pady=5, fill = ttk.X)

        label_base_url = ttk.Label(frame, text='Custom OpenAI-Like API Model Base URL', bootstyle="secondary")
        label_base_url.pack(pady=10, fill=ttk.X)

        # Entry for Base URL
        self.base_url_entry = ttk.Entry(frame)
        self.base_url_entry.pack(fill=ttk.X, pady=5)

        # Model Label
        label_model = ttk.Label(frame, text='Custom Model Name:', bootstyle="secondary")
        label_model.pack(pady=10, fill=ttk.X)

        # Entry for Model
        self.model_entry = ttk.Entry(frame)
        self.model_entry.pack(fill=ttk.X, pady=5)

        # Save Button
        save_button = ttk.Button(frame, text='Save Settings', bootstyle="success", command=self.save_button)
        save_button.pack(pady=20, fill = ttk.X)

    def update_model_entry(self):
         if self.model_var.get() != 'custom':
            self.model_entry.delete(0, ttk.END)


    def save_button(self) -> None:
        logging.info("Saving settings from Advanced Settings Window.")
        base_url = self.base_url_entry.get().strip()
        model = self.model_var.get() if self.model_var.get() != 'custom' else self.model_entry.get().strip()
        settings_dict = {
            'base_url': base_url,
            'model': model,
        }
        try:
           self.settings.save_settings_to_file(settings_dict)
           logging.info("Advanced settings saved successfully.")
           self.destroy() # Close the window after saving
        except Exception as e:
             logging.error(f"Error saving advanced settings: {e}")
             # Consider showing an error message to the user