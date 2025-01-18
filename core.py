import time
from multiprocessing import Queue
from typing import Optional, Any
import logging
import threading
import json

from openai import OpenAIError

from interpreter import Interpreter
from llm import LLM
from settings import Settings


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class Core:
    def __init__(self, status_queue: Queue):
        self.status_queue = status_queue
        self._interrupt_event = threading.Event()  # Use an event for interruption
        self.settings_dict = Settings().get_dict()

        self.interpreter = Interpreter(self.status_queue)

        self.llm = None
        try:
            self.llm = LLM(self.status_queue)
            logging.info("LLM initialized successfully.")
        except OpenAIError as e:
            error_msg = f'Set your OpenAPI API Key in Settings and Restart the App. Error: {e}'
            self.status_queue.put(error_msg)
            logging.error(error_msg)
        except Exception as e:
            error_msg = (f'An error occurred during startup. Please fix and restart the app.\n'
                         f'Error likely in file {Settings().settings_file_path}.\n'
                         f'Error: {e}')
            self.status_queue.put(error_msg)
            logging.error(error_msg)

    def execute_user_request(self, user_request: str) -> None:
        self.stop_previous_request()
        time.sleep(0.1)
        self.execute(user_request)

    def stop_previous_request(self) -> None:
         self._interrupt_event.set()  # Set the event to interrupt any execution

    def execute(self, user_request: str, step_num: int = 0) -> Optional[str]:
        """
            This function might recurse.

            user_request: The original user request
            step_number: the number of times we've called the LLM for this request.
                Used to keep track of whether it's a fresh request we're processing (step number 0), or if we're already
                in the middle of one.
                Without it the LLM kept looping after finishing the user request.
                Also, it is needed because the LLM we are using doesn't have a stateful/assistant mode.
        """
        self._interrupt_event.clear() # Reset the event flag before each execution
        if not self.llm:
            status = 'Set your OpenAPI API Key in Settings and Restart the App'
            self.status_queue.put(status)
            logging.warning(status)
            return status
        if  self._interrupt_event.is_set():
                self.status_queue.put('Interrupted')
                logging.info('Execution Interrupted')
                return 'Interrupted'

        max_retries = 3
        retries = 0
        instructions: Optional[dict[str, Any]] = None
        while retries < max_retries:
            if  self._interrupt_event.is_set():
                self.status_queue.put('Interrupted')
                logging.info('Execution Interrupted')
                return 'Interrupted'
            try:
                instructions = self.llm.get_instructions_for_objective(user_request, step_num)
                if instructions and instructions != {}:
                   break # break out of the retry loop if instructions are available
                retries += 1
                logging.warning(f'LLM returned malformed or empty instructions, retrying {retries}/{max_retries} ')
                time.sleep(0.1*retries) #add a small backoff.
            except Exception as e:
                logging.error(f'Exception fetching instructions from LLM: {e}')
                retries += 1
                time.sleep(0.1*retries)
            if  self._interrupt_event.is_set():
                self.status_queue.put('Interrupted')
                logging.info('Execution Interrupted')
                return 'Interrupted'


        if not instructions:
             try:
                  llm_response = self.llm.model.send_message_to_llm(user_request)
                  instructions_str = self.llm.model.convert_llm_response_to_json_instructions(llm_response)
                  if isinstance(instructions_str, str) and instructions_str != "":
                      self.status_queue.put(("ai",instructions_str)) # send to both uis
                      if hasattr(self, 'user_and_ai_responses'):
                            self.user_and_ai_responses.append(("ai", instructions_str))
                      return instructions_str
             except json.JSONDecodeError as e:
                logging.error(f'JSONDecodeError when parsing instructions: {e}')
             except Exception as e:
                  logging.error(f'Exception in execute method - {e}')

             status = 'Failed to fetch valid instructions after multiple retries.'
             self.status_queue.put(status)
             logging.error(status)
             return status

        try:
            for step in instructions.get('steps', []): # Ensure 'steps' is a list
                if self._interrupt_event.is_set():
                    self.status_queue.put('Interrupted')
                    logging.info('Execution Interrupted')
                    return 'Interrupted'
                success = self.interpreter.process_command(step)
                if not success:
                    error_msg = f'Unable to process command step: {step}'
                    self.status_queue.put(error_msg)
                    logging.error(error_msg)
                    return 'Unable to execute the request'
                if  self._interrupt_event.is_set():
                    self.status_queue.put('Interrupted')
                    logging.info('Execution Interrupted')
                    return 'Interrupted'


        except Exception as e:
            status = f'Exception Unable to execute the request - {e}'
            self.status_queue.put(status)
            logging.error(status)
            return status

        if instructions.get('done'):
            # Communicate Results
            self.status_queue.put(instructions['done'])
            self.play_ding_on_completion()
            return instructions['done']
        else:
            # if not done, continue to next phase
            self.status_queue.put('Fetching further instructions based on current state')
            return self.execute(user_request, step_num + 1)

    def play_ding_on_completion(self):
        # Play ding sound to signal completion
        if self.settings_dict.get('play_ding_on_completion'):
            print('\a')

    def cleanup(self):
        if self.llm:
            self.llm.cleanup()
        logging.info("Core cleanup complete")