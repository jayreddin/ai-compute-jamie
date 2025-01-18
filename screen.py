import base64
import io
import os
import tempfile
import logging
import tkinter as tk

import pyautogui
from PIL import Image, ImageTk
from settings import Settings  # Updated import

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Screen:
    def __init__(self):
          self.settings = Settings()
          self.settings_directory = self.settings.get_settings_directory_path()
          self.screenshot_counter = 0
          self.screenshot_filepath = os.path.join(self.settings_directory, f'screenshot_{self.screenshot_counter}.png')


    def get_size(self) -> tuple[int, int]:
        screen_width, screen_height = pyautogui.size()  # Get the size of the primary monitor.
        return screen_width, screen_height

    def get_screenshot(self) -> Image.Image:
        # Enable screen recording from settings
        logging.info("Taking a screenshot using pyautogui")
        try:
            img = pyautogui.screenshot()  # Takes roughly 100ms # img.show()
            return img
        except Exception as e:
            logging.error(f"Error taking screenshot: {e}")
            raise

    def get_screenshot_as_photo_image(self, max_height=150) -> ImageTk.PhotoImage:
        """Captures the screenshot and returns it as a PhotoImage"""
        try:
            img = self.get_screenshot()
            # Resize the image to a maximum height while maintaining aspect ratio
            hpercent = (max_height / float(img.size[1]))
            wsize = int((float(img.size[0]) * float(hpercent)))
            img = img.resize((wsize, max_height), Image.Resampling.LANCZOS)
            photo_image = ImageTk.PhotoImage(img)
            return photo_image
        except Exception as e:
            logging.error(f'Error converting screenshot to PhotoImage: {e}')
            return None

    def get_screenshot_in_base64(self) -> str:
        # Base64 images work with ChatCompletions API but not Assistants API
        img_bytes = self.get_screenshot_as_file_object()
        encoded_image = base64.b64encode(img_bytes.read()).decode('utf-8')
        return encoded_image

    def get_screenshot_as_file_object(self) -> io.BytesIO:
         """Captures the screenshot and returns it as an in-memory file object"""
         img_bytes = io.BytesIO()
         img = self.get_screenshot()
         img.save(img_bytes, format='PNG')  # Save the screenshot to an in-memory file.
         img_bytes.seek(0)
         return img_bytes

    def get_temp_filename_for_current_screenshot(self) -> str:
        """Saves screenshot to a temp file, returns the path"""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmpfile:
                logging.info(f"Saving a temp screenshot to: {tmpfile.name}")
                screenshot = self.get_screenshot()
                screenshot.save(tmpfile.name)
                return tmpfile.name
        except Exception as e:
            logging.error(f"Error saving a temporary screenshot: {e}")
            raise


    def get_screenshot_file(self) -> str:
        """Saves the screenshot to the settings directory and returns the file path"""
        filename = f'screenshot_{self.screenshot_counter}.png'
        self.screenshot_filepath = os.path.join(self.settings_directory, filename)
        logging.info(f"Saving screenshot to file: {self.screenshot_filepath}")
        try:
            img = self.get_screenshot()
            img.save(self.screenshot_filepath)
            self.screenshot_counter = (self.screenshot_counter + 1) % 10
            return self.screenshot_filepath
        except Exception as e:
             logging.error(f"Error saving screenshot to file: {e}")
             raise