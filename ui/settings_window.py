import threading
import webbrowser
from multiprocessing import Queue
from pathlib import Path
import logging

import speech_recognition as sr # type: ignore
import ttkbootstrap as ttk # type: ignore
from PIL import Image, ImageTk # type: ignore

from llm import DEFAULT_MODEL_NAME
from settings import Settings  # Updated import
from version import version


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def open_link(url) -> None:
    webbrowser.open_new(url)


class SettingsWindow(ttk.Toplevel):
        """
        Self-contained settings sub-window for the UI
        """

        def __init__(self, parent):
            super().__init__(parent)
            self.title('Settings')
            self.minsize(300, 450)
            self.available_themes = ['darkly', 'cyborg', 'journal', 'solar', 'superhero']
            self.create_widgets()
            self.load_settings()

        def load_settings(self):
          self.settings = Settings()
          # Populate UI
          settings_dict = self.settings.get_dict()

          if 'api_key' in settings_dict:
              self.api_key_entry.insert(0, settings_dict['api_key'])
          if 'default_browser' in settings_dict:
              self.browser_combobox.set(settings_dict['default_browser'])
          if 'play_ding_on_completion' in settings_dict:
              self.play_ding.set(1 if settings_dict['play_ding_on_completion'] else 0)
          if 'custom_llm_instructions' in settings_dict:
              self.llm_instructions_text.insert('1.0', settings_dict['custom_llm_instructions'])
          self.theme_combobox.set(settings_dict.get('theme', 'superhero'))
          self.screenshot_slider.set(settings_dict.get("number_of_screenshots", 1))
          self.secure_connection.set(1 if settings_dict.get('secure_connection') else 0)
          self.update_screenshot_label()

        def create_widgets(self) -> None:
            # API Key Widgets
            label_api = ttk.Label(self, text='OpenAI API Key:', bootstyle="info")
            label_api.pack(pady=10)
            self.api_key_entry = ttk.Entry(self, width=30)
            self.api_key_entry.pack()

            # Label for Browser Choice
            label_browser = ttk.Label(self, text='Choose Default Browser:', bootstyle="info")
            label_browser.pack(pady=10)

            # Dropdown for Browser Choice
            self.browser_var = ttk.StringVar()
            self.browser_combobox = ttk.Combobox(self, textvariable=self.browser_var,
                                                 values=['Edge', 'Chrome', 'Firefox', 'Opera', 'Safari'],)
            self.browser_combobox.pack(pady=5)
            self.browser_combobox.set('Choose Browser')

            # Label for Custom LLM Instructions
            label_llm = ttk.Label(self, text='Custom LLM Instructions:', bootstyle="info")
            label_llm.pack(pady=10)

            # Text Box for Custom LLM Instructions
            self.llm_instructions_text = ttk.Text(self, height=10, width=50)
            self.llm_instructions_text.pack(padx=(10, 10), pady=(0, 10))

            # Checkbox for "Play Ding" option
            self.play_ding = ttk.IntVar()
            play_ding_checkbox = ttk.Checkbutton(self, text="Play Ding on Completion", variable=self.play_ding,
                                                 bootstyle="round-toggle")
            play_ding_checkbox.pack(pady=10)

             # Checkbox for "Secure Connection" option
            self.secure_connection = ttk.IntVar()
            secure_connection_checkbox = ttk.Checkbutton(self, text="Use Secure Connection", variable=self.secure_connection,
                                                 bootstyle="round-toggle")
            secure_connection_checkbox.pack(pady=10)

            # Theme Selection Widgets
            label_theme = ttk.Label(self, text='UI Theme:', bootstyle="info")
            label_theme.pack()
            self.theme_var = ttk.StringVar()
            self.theme_combobox = ttk.Combobox(self, textvariable=self.theme_var, values=self.available_themes,
                                               state="readonly")
            self.theme_combobox.pack(pady=5)
            self.theme_combobox.set('superhero')
            # Add binding for immediate theme change
            self.theme_combobox.bind('<<ComboboxSelected>>', self.on_theme_change)

            # Slider for number of screenshots
            self.screenshot_slider = ttk.Scale(self, from_=1, to=10, orient="horizontal", command=self.update_screenshot_label)
            self.screenshot_slider.pack(pady=10, fill=ttk.X)

            self.screenshot_label = ttk.Label(self, text='Number of Screenshots: 1', bootstyle="info")
            self.screenshot_label.pack(pady=5)

            # Add numbers to the slider
            self.screenshot_numbers = ttk.Frame(self)
            self.screenshot_numbers.pack(fill=ttk.X)
            for i in range(1, 11):
                label = ttk.Label(self.screenshot_numbers, text=str(i), bootstyle="info")
                label.pack(side=ttk.LEFT, expand=True)

            # Save Button
            save_button = ttk.Button(self, text='Save Settings', bootstyle="success", command=self.save_button)
            save_button.pack(pady=(10, 5))

            # Button to open Advanced Settings
            advanced_settings_button = ttk.Button(self, text='Advanced Settings', bootstyle="info",
                                                  command=self.open_advanced_settings)
            advanced_settings_button.pack(pady=(0, 10))

            # Hyperlink Label
            link_label = ttk.Label(self, text='Setup Instructions', bootstyle="primary")
            link_label.pack()
            link_label.bind('<Button-1>', lambda e: open_link(
                'https://github.com/AmberSahdev/Open-Interface?tab=readme-ov-file#setup-%EF%B8%8F'))

            # Check for updates Label
            update_label = ttk.Label(self, text='Check for Updates', bootstyle="primary")
            update_label.pack()
            update_label.bind('<Button-1>', lambda e: open_link(
                'https://github.com/AmberSahdev/Open-Interface/releases/latest'))

            # Version Label
            version_label = ttk.Label(self, text=f'Version: {str(version)}', font=('Helvetica', 10))
            version_label.pack(side="bottom", pady=10)

        def on_theme_change(self, event=None) -> None:
            # Apply theme immediately when selected
            theme = self.theme_var.get()
            self.master.change_theme(theme)

        def update_screenshot_label(self, event=None):
            number_of_screenshots = int(self.screenshot_slider.get())
            self.screenshot_label.config(text=f'Number of Screenshots: {number_of_screenshots}')

        def save_button(self) -> None:
            theme = self.theme_var.get()
            api_key = self.api_key_entry.get().strip()
            default_browser = self.browser_var.get()
            number_of_screenshots = int(self.screenshot_slider.get())
            settings_dict = {
                'api_key': api_key,
                'default_browser': default_browser,
                'play_ding_on_completion': bool(self.play_ding.get()),
                'custom_llm_instructions': self.llm_instructions_text.get("1.0", "end-1c").strip(),
                'theme': theme,
                'number_of_screenshots': number_of_screenshots,
                 'secure_connection': bool(self.secure_connection.get()),

            }

            # Remove redundant theme change since it's already applied
            self.settings.save_settings_to_file(settings_dict)
            self.destroy()

        def open_advanced_settings(self):
            # Open the advanced settings window
             from ui.advanced_settings_window import AdvancedSettingsWindow
             AdvancedSettingsWindow(self)