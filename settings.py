import base64
import json
import os
from pathlib import Path
import logging
import threading

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Settings:
    def __init__(self):
        self.settings_file_path = os.path.join(self.get_settings_directory_path(), 'settings.json')
        os.makedirs(os.path.dirname(self.settings_file_path), exist_ok=True)
        self.settings = self.load_settings_from_file()
        self._settings_change_event = threading.Event()

    def get_settings_directory_path(self) -> str:
        return str(Path.home()) + '/.open-interface/'

    def get_dict(self) -> dict[str, str]:
        return self.settings

    def save_settings_to_file(self, settings_dict: dict[str, str]) -> None:
        logging.info(f"Saving settings to file: {self.settings_file_path}")
        try:
            settings: dict[str, str] = {}

            # Preserve previous settings in case new dict doesn't contain them
            if os.path.exists(self.settings_file_path):
                with open(self.settings_file_path, 'r') as file:
                    try:
                        settings = json.load(file)
                    except json.JSONDecodeError:
                         logging.warning(f"Settings file is empty or not valid JSON, ignoring existing settings.")
                         settings = {}
                    except Exception as e:
                         logging.error(f"Unexpected error while reading settings file: {e}")
                         settings = {}


            updated_settings = False
            for setting_name, setting_val in settings_dict.items():
                if setting_val is not None:
                    if setting_name == "api_key":
                        encoded_api_key = base64.b64encode(setting_val.encode()).decode()
                        if settings.get(setting_name) != encoded_api_key:
                            settings[setting_name] = encoded_api_key
                            updated_settings = True
                    elif settings.get(setting_name) != setting_val:
                        settings[setting_name] = setting_val
                        updated_settings = True


            if updated_settings:
              with open(self.settings_file_path, 'w+') as file:
                   json.dump(settings, file, indent=4)
              logging.info(f'Settings saved correctly.')
              self._settings_change_event.set() # set event
              self._settings_change_event.clear() # clear event for next update.
            else:
              logging.info(f'No settings changed, skipping saving.')


        except Exception as e:
             logging.error(f"Error saving settings to file: {e}")
             raise

    def load_settings_from_file(self) -> dict[str, str]:
         logging.info(f'Loading settings from file: {self.settings_file_path}')
         settings = {}
         if os.path.exists(self.settings_file_path):
            try:
                with open(self.settings_file_path, 'r') as file:
                    settings = json.load(file)

                # Decode the API key
                if 'api_key' in settings:
                    decoded_api_key = base64.b64decode(settings['api_key']).decode()
                    settings['api_key'] = decoded_api_key
            except json.JSONDecodeError:
                 logging.warning(f"Settings file is empty or not valid JSON, ignoring existing settings.")
                 return {}
            except FileNotFoundError:
                logging.warning(f"Settings file not found, returning empty settings")
                return {}
            except Exception as e:
                 logging.error(f"Unexpected error while reading settings file: {e}")
                 return {}
            logging.info(f'Settings loaded correctly: {settings}')
         else:
             logging.info(f"Settings file not found, returning empty settings")

         return settings
    def notify_settings_changed(self):
         """Notifies all the threads that the settings have been changed."""
         self._settings_change_event.set()
         self._settings_change_event.clear()
    def wait_for_settings_change(self):
        """Waits for a settings change event and loads the settings in a separate thread"""
        def wait_and_load():
           self._settings_change_event.wait()
           self.settings = self.load_settings_from_file()

        threading.Thread(target=wait_and_load, daemon=True).start()