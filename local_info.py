import os
import platform
import logging
import psutil
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

"""
List the apps the user has locally, default browsers, etc. 
"""

locally_installed_apps: list[str] = []
operating_system: str = platform.platform()

if platform.system() == "Darwin": # Check if it is macOS
    try:
      locally_installed_apps = [app for app in os.listdir('/Applications') if app.endswith('.app')]
      logging.info(f'Successfully listed {len(locally_installed_apps)} apps.')
    except FileNotFoundError as e:
      logging.warning(f'Applications folder not found. Error: {e}')
      locally_installed_apps = ["Unknown"]
    except PermissionError as e:
        logging.warning(f'Permission error when reading the applications folder. Error: {e}')
        locally_installed_apps = ["Unknown"]
    except Exception as e:
        logging.error(f'An unexpected error has occurred when reading the applications folder. Error: {e}')
        locally_installed_apps = ["Unknown"]
else:
    logging.info('Not on macOS, cannot list apps.')
    locally_installed_apps = ["Unknown"]

try:
    running_processes = [p.info["name"] for p in psutil.process_iter(['pid', 'name'])]
except Exception as e:
     logging.error(f'Could not obtain the running processes {e}')
     running_processes = []