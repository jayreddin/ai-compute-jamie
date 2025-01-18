from pathlib import Path
from typing import Any
import logging

from models.factory import ModelFactory
from local_info import *
from models.gpt4o import GPT4o
from models.gpt4v import GPT4v
from screen import Screen
from settings import Settings
from multiprocessing import Queue
import threading


DEFAULT_MODEL_NAME = 'gpt-4o'

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class LLM:
    """
    LLM Request
    {
    	"original_user_request": ...,
    	"step_num": ...,
    	"screenshot": ...
    }

    step_num is the count of times we've interacted with the LLM for this user request.
        If it's 0, we know it's a fresh user request.
    	If it's greater than 0, then we know we are already in the middle of a request.
    	Therefore, if the number is positive and from the screenshot it looks like request is complete, then return an
    	    empty list in steps and a string in done. Don't keep looping the same request.

    Expected LLM Response
    {
    	"steps": [
    		{
    			"function": "...",
    			"parameters": {
    				"key1": "value1",
    				...
    			},
    			"human_readable_justification": "..."
    		},
    		{...},
    		...
    	],
    	"done": ...
    }

    function is the function name to call in the executer.
    parameters are the parameters of the above function.
    human_readable_justification is what we can use to debug in case program fails somewhere or to explain to user why we're doing what we're doing.
    done is null if user request is not complete, and it's a string when it's complete that either contains the
        information that the user asked for, or just acknowledges completion of the user requested task. This is going
        to be communicated to the user if it's present.
    """

    def __init__(self, status_queue: Queue):
        self.status_queue = status_queue
        self.model = None
        self.settings_dict: dict[str, str] = {}
        self.model_name = None
        self.base_url = None
        self.api_key = None
        self._load_settings()
        self._create_model()
        threading.Thread(target=self._wait_for_settings_change, daemon=True).start()


    def _wait_for_settings_change(self):

         Settings().wait_for_settings_change()
         self._load_settings()
         self._create_model()

    def _load_settings(self):
        """Load settings and set class attributes."""
        try:
            logging.info("Loading settings.")
            self.settings_dict = Settings().get_dict()
            model_name, base_url, api_key = self.get_settings_values()
            self.model_name = model_name
            self.base_url = base_url
            self.api_key = api_key
            logging.info(f'Loaded settings: model={model_name}, base_url={base_url}')
        except KeyError as e:
            logging.error(f'Error loading settings: Missing key {e}')
            raise
        except ValueError as e:
            logging.error(f'Error loading settings: Invalid value - {e}')
            raise
        except Exception as e:
            logging.error(f'Unexpected error loading settings: {e}')
            raise

    def _create_model(self):
        try:
            logging.info("Creating model.")
            context = self.read_context_txt_file()
            self.model = ModelFactory.create_model(self.model_name, self.base_url, self.api_key, context, self.status_queue)
            logging.info(f"Model created successfully: {self.model_name}")

        except Exception as e:
            logging.error(f'Error creating model: {e}')
            raise

    def get_settings_values(self) -> tuple[str, str, str]:
        model_name = self.settings_dict.get('model')
        if not model_name:
            model_name = DEFAULT_MODEL_NAME
        base_url = self.settings_dict.get('base_url', '').strip('/')
        if not base_url:
            base_url = 'https://api.openai.com/v1'

        if base_url == "openai":
            base_url = "https://api.openai.com/v1"

        if not base_url.endswith('/v1'):
            base_url = base_url + '/v1'

        api_key = self.settings_dict.get('api_key')
        return model_name, base_url, api_key


    def read_context_txt_file(self) -> str:

        # Construct context for the assistant by reading context.txt and adding extra system information
        context = ''
        path_to_context_file = Path(__file__).resolve().parent.joinpath('resources', 'context.txt')
        try:
             with open(path_to_context_file, 'r') as file:
                 context += file.read()
        except FileNotFoundError as e:
             logging.error(f'Error reading context file: {e}')
             raise
        except IOError as e:
             logging.error(f'An error occurred while reading context file: {e}')
             raise
        context += (
        "You are an agent that can control a computer by executing commands based on user requests. "

        "You will receive a user request, and may have access to a screenshot. "
        "If the user request is a command, you MUST reply with JSON that contains a list of steps. "
        "Each step must have a `function` (the name of the action to perform) and `parameters` (a dictionary with the required parameters for that action), "
         "as well as a `human_readable_justification`. "
        "The `human_readable_justification` should be written as if you are a human expressing what you are trying to achieve. "
        "When the user request is fully complete, return a `done` message that acknowledges completion, explaining to the user what you did, and your reasoning. The done message MUST be inside the done key in the JSON response. "
        "The format of the JSON should be "
        '{"steps": [{"function": "...", "parameters": {"key1": "value1", ...}, "human_readable_justification": "..."}, {...}, ...], "done": "..."}'
         "If the user request is not complete, the done key must be null."
        "If the user request is complete, and you don't need to perform any more steps, the steps must be an empty list `[]`."
        "You MUST always reply in valid JSON, even if you don't know how to reply, or there is an error."
        "You MUST always use a `human_readable_justification` that explains what each step does. "
        "You MUST use all functions and keys specified in the context. "
        "You should always use human-like language, and avoid responding with 'I have completed the request'."
        "If the user request is a question, you should directly answer the question, and you MUST NOT return a list of steps and you MUST NOT take a screenshot. You should always reply with a natural human-like tone, as if you were a normal person. Do not give instructions, just provide the answer. The reply MUST be in the done field, without steps."
        "If the user request is a command, you MUST return a list of steps that will be executed to complete the command. You MUST always take a screenshot when a command is given."
          "You should only include the human readable response inside the `done` key and not as a parameter of the different steps"
        "You will have access to `open_application` and `close_application` functions, and must specify the application name in the `application_name` parameter."
         "You will also have access to `sleep`, `write`, `press`, `hotkey`, `scroll`, `moveTo`, `click`, `doubleClick` commands, for interacting with the OS, and must follow the instructions in the provided context for the correct usage. "
        "The number of screenshots you must take is specified using the `number_of_screenshots` setting, and you MUST use this when deciding how many screenshots to take. Please use the `number_of_screenshots` as an integer to define how many screenshots should be taken."
        "If you are using `gpt-4-vision-preview` or `gpt-4-turbo` models, you have access to vision, so you can use the screenshots to help you understand what to do and how to complete the command. If you are using the `claude-3-sonnet` or `mistral-large` models, you do not have access to vision, so you cannot use screenshots."


        )
        context += f' Locally installed apps are {",".join(locally_installed_apps)}.'
        context += f' OS is {operating_system}.'
        context += f' Primary screen size is {Screen().get_size()}.\n'

        if 'default_browser' in self.settings_dict and self.settings_dict['default_browser']:
            context += f'\nDefault browser is {self.settings_dict["default_browser"]}.'

        if 'custom_llm_instructions' in self.settings_dict and self.settings_dict['custom_llm_instructions']:
            context += f'\nCustom user-added info: {self.settings_dict["custom_llm_instructions"]}.'
        if 'number_of_screenshots' in self.settings_dict:
             context += f'\nThe number of screenshots you must take for this command is {self.settings_dict["number_of_screenshots"]}'

        return context

    def get_instructions_for_objective(self, original_user_request: str, step_num: int = 0) -> dict[str, Any]:
        if not self.model:
             logging.error("Model is not initialized")
             return {} # or raise an exception if that is more suitable
        logging.info(f"Getting instructions from the model {self.model_name}")
        try:
            if self.model_name == "mistral-large":
                 return self.model.get_instructions_for_objective(original_user_request, step_num)
            else:
                if 'number_of_screenshots' in self.settings_dict and int(self.settings_dict['number_of_screenshots']) > 0 and isinstance(self.model, (GPT4v, GPT4o)):
                    return self.model.get_instructions_for_objective(original_user_request, step_num)
                else:
                    return self.model.get_instructions_for_objective(original_user_request, step_num)
        except Exception as e:

            logging.error(f"Error in get_instructions_for_objective: {e}")
            return {}

    def cleanup(self):
         if self.model:

            logging.info(f"Cleaning up model {self.model_name}")
            self.model.cleanup()
         else:
            logging.info("No model to cleanup.")