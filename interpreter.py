import json
from multiprocessing import Queue
from time import sleep
from typing import Any, Union
import logging
import platform

import pyautogui
import subprocess
import psutil


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class Interpreter:
    def __init__(self, status_queue: Queue):
        # MP Queue to put current status of execution in while processes commands.
        # It helps us reflect the current status on the UI.
        self.status_queue = status_queue

    def process_commands(self, json_commands: list[dict[str, Any]]) -> bool:
        """
        Reads a list of JSON commands and runs the corresponding function call as specified in context.txt
        :param json_commands: List of JSON Objects with format as described in context.txt
        :return: True for successful execution, False for exception while interpreting or executing.
        """
        for command in json_commands:
            success = self.process_command(command)
            if not success:
                return False  # End early and return
        return True

    def process_command(self, json_command: dict[str, Any]) -> bool:
        """
        Reads the passed in JSON object and extracts relevant details. Format is specified in context.txt.
        After interpretation, it proceeds to execute the appropriate function call.

        :return: True for successful execution, False for exception while interpreting or executing.
        """
        function_name = json_command.get('function')
        parameters = json_command.get('parameters', {})
        human_readable_justification = json_command.get('human_readable_justification')

        if not function_name:
            logging.error(f"Missing 'function' key in JSON command: {json_command}")
            return False

        logging.info(f'Now performing - {function_name} - {parameters} - {human_readable_justification}')
        self.status_queue.put(human_readable_justification)

        try:
            self.execute_function(function_name, parameters)
            return True
        except Exception as e:
            logging.error(f'\nError executing {function_name} with parameters {parameters}')
            logging.exception(f'Exception details:')  # Log the full traceback
            logging.error(f'This was the json we received from the LLM: {json.dumps(json_command, indent=2)}')
            return False

    def execute_function(self, function_name: str, parameters: dict[str, Any]) -> None:
        """
            We are expecting only two types of function calls below
            1. time.sleep() - to wait for web pages, applications, and other things to load.
            2. pyautogui calls to interact with system's mouse and keyboard.
        """

        # Warm up pyautogui, but make it conditional on the OS.
        if platform.system() == "Darwin":  # Check for macOS
            pyautogui.press("command", interval=0.2)

        if function_name == "sleep" and parameters.get("secs"):
            self._execute_sleep(parameters.get("secs"))
        elif hasattr(pyautogui, function_name):
            self._execute_pyautogui_function(function_name, parameters)
        elif function_name == "open_application" and parameters.get("application_name"):
            self._execute_open_application(parameters.get("application_name"))
        elif function_name == "close_application" and parameters.get("application_name"):
            self._execute_close_application(parameters.get("application_name"))
        else:
            logging.warning(f'No such function {function_name} in our interface\'s interpreter')

    def _execute_sleep(self, secs: Union[int, float]):
        """Executes a sleep command"""
        sleep(secs)

    def _execute_pyautogui_function(self, function_name: str, parameters: dict[str, Any]) -> None:
        """Executes a pyautogui function with specific parameter handling"""

        function_to_call = getattr(pyautogui, function_name)

        try:
            if function_name == 'write' and ('string' in parameters or 'text' in parameters):
                self._execute_write(function_to_call, parameters)
            elif function_name == 'press' and ('keys' in parameters or 'key' in parameters):
                self._execute_press(function_to_call, parameters)
            elif function_name == 'hotkey':
                self._execute_hotkey(function_to_call, parameters)
            elif function_name == 'scroll':
                 self._execute_scroll(function_to_call, parameters)
            elif function_name == 'moveTo' and ('x' in parameters and 'y' in parameters):
                self._execute_move_to(function_to_call, parameters)
            elif function_name == 'click' and ('x' in parameters and 'y' in parameters):
                self._execute_click(function_to_call, parameters)
            elif function_name == 'doubleClick' and ('x' in parameters and 'y' in parameters):
                 self._execute_double_click(function_to_call, parameters)
            else:
                function_to_call(**parameters)
        except pyautogui.PyAutoGUIException as e:
            logging.error(f"PyAutoGUI Exception with {function_name} and params {parameters}: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected Exception with {function_name} and params {parameters}: {e}")
            raise

    def _execute_write(self, function_to_call, parameters):
        string_to_write = parameters.get('string') or parameters.get('text')
        interval = parameters.get('interval', 0.1)
        function_to_call(string_to_write, interval=interval)

    def _execute_press(self, function_to_call, parameters):
        keys_to_press = parameters.get('keys') or parameters.get('key')
        presses = parameters.get('presses', 1)
        interval = parameters.get('interval', 0.2)
        function_to_call(keys_to_press, presses=presses, interval=interval)

    def _execute_hotkey(self, function_to_call, parameters):
        function_to_call(list(parameters.values()))

    def _execute_scroll(self, function_to_call, parameters):
        amount = parameters.get('amount', 100)
        function_to_call(amount)

    def _execute_move_to(self, function_to_call, parameters):
        x, y = parameters.get('x'), parameters.get('y')
        duration = parameters.get('duration', 0.2)
        function_to_call(x, y, duration=duration)

    def _execute_click(self, function_to_call, parameters):
        x, y = parameters.get('x'), parameters.get('y')
        button = parameters.get('button', 'left')
        function_to_call(x=x, y=y, button=button)

    def _execute_double_click(self, function_to_call, parameters):
        x, y = parameters.get('x'), parameters.get('y')
        button = parameters.get('button', 'left')
        function_to_call(x=x, y=y, button=button, clicks=2)

    def _execute_open_application(self, application_name: str):
         """Opens an application using subprocess.Popen"""
         try:
              logging.info(f"Opening application: {application_name}")
              subprocess.Popen(application_name)
         except FileNotFoundError:
              logging.error(f"Application not found: {application_name}")
              self.status_queue.put(f"Application not found: {application_name}")
         except Exception as e:
              logging.error(f"Error opening application: {application_name}. Error {e}")
              self.status_queue.put(f"Error opening application: {application_name}")

    def _execute_close_application(self, application_name: str):
        """Closes an application using psutil"""
        try:
             logging.info(f"Closing application: {application_name}")
             for process in psutil.process_iter(['pid', 'name']):
                 if application_name.lower() in process.info['name'].lower():
                    p = psutil.Process(process.info['pid'])
                    p.terminate()
                    logging.info(f"Terminated application: {application_name} with pid {process.info['pid']}")
                    break
             else:
               logging.warning(f'No application found with name {application_name}')
               self.status_queue.put(f'No application found with name {application_name}')
        except Exception as e:
             logging.error(f"Error closing application: {application_name}. Error: {e}")
             self.status_queue.put(f"Error closing application: {application_name}")