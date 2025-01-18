from pathlib import Path
import threading
import logging
from queue import Queue
from typing import Any
from settings import Settings
from models.gpt4o import GPT4o
from models.gpt4v import GPT4v
from models.model import Model

class LLM:
    """LLM handler that manages model initialization and request processing"""
    def __init__(self, status_queue: Queue):
        self.model = None
        self.settings_dict: dict[str, str] = {}
        self.model_name = None
        self.base_url = None
        self.api_key = None
        self.status_queue = status_queue
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
        except Exception as e:
            logging.error(f'Error loading settings: {e}')
            raise

    def _create_model(self):
        """Create an instance of the appropriate model."""
        try:
            context = self.read_context_txt_file()
            if self.model_name == "gpt-4-vision-preview":
                self.model = GPT4v(self.model_name, self.base_url, self.api_key, context, self.status_queue)
            elif self.model_name == "gpt-4" or self.model_name == "gpt-4-turbo":
                self.model = GPT4o(self.model_name, self.base_url, self.api_key, context, self.status_queue)
            logging.info(f"Created model instance of type: {type(self.model).__name__}")
        except Exception as e:
            logging.error(f"Error creating model: {e}")
            self.model = None
            raise

    def get_settings_values(self) -> tuple[str, str, str]:
        """Extract required settings values."""
        settings_dict = self.settings_dict
        model_name = settings_dict.get('model', '')
        base_url = settings_dict.get('base_url', '')
        api_key = settings_dict.get('api_key', '')
        
        if not all([model_name, base_url, api_key]):
            raise ValueError("Missing required settings: model, base_url, or api_key")
            
        return model_name, base_url, api_key

    def read_context_txt_file(self) -> str:
        """Read the context from the system prompt file."""
        try:
            # First try system_prompt.txt, fall back to context.txt for backwards compatibility
            path_to_context_file = Path(__file__).parent / "resources" / "system_prompt.txt"
            if not path_to_context_file.exists():
                path_to_context_file = Path(__file__).parent / "resources" / "context.txt"
            with open(path_to_context_file, 'r') as file:
                return file.read().strip()
        except Exception as e:
            logging.error(f"Error reading context file: {e}")
            raise

    def get_instructions_for_objective(self, original_user_request: str, step_num: int = 0) -> dict[str, Any]:
        """Get instructions from the model for achieving an objective."""
        if not self.model:
            logging.error("Model is not initialized")
            raise RuntimeError("Model is not initialized")
        
        logging.info(f"Getting instructions from the model {self.model_name}")
        if self.model_name == "mistral-large":
            return self.model.get_instructions_for_objective(original_user_request, step_num)
        
        num_screenshots = int(self.settings_dict.get('number_of_screenshots', 1))
        if isinstance(self.model, (GPT4v, GPT4o)) and num_screenshots > 1:
            logging.info(f"Taking {num_screenshots} screenshots for analysis")
            merged_instructions = {}
            for i in range(num_screenshots):
                try:
                    new_instructions = self.model.get_instructions_for_objective(original_user_request, step_num)
                    for key, value in new_instructions.items():
                        if key not in merged_instructions or (not merged_instructions[key] and value):
                            merged_instructions[key] = value
                except Exception as e:
                    logging.error(f"Error processing screenshot {i+1}: {e}")
            if merged_instructions:
                return merged_instructions
        
        return self.model.get_instructions_for_objective(original_user_request, step_num)

    def cleanup(self):
        """Clean up any resources used by the model."""
        if self.model:
            try:
                self.model.cleanup()
            except Exception as e:
                logging.error(f"Error during cleanup: {e}")