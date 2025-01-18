import os
from abc import ABC, abstractmethod
from typing import Any, List, Dict
import logging
from multiprocessing import Queue

from openai import OpenAI, OpenAIError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class Model(ABC):
    """Abstract base class for all models"""
    def __init__(self, model_name: str, base_url: str, api_key: str, context: str, status_queue: Queue):
        self.model_name = model_name
        self.base_url = base_url
        self.api_key = api_key
        self.context = context
        self.status_queue = status_queue
        try:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            logging.info(f"OpenAI client initialized successfully for model: {model_name}")
        except OpenAIError as e:
            logging.error(f"Error initializing OpenAI client for model {model_name}: {e}")
            raise


    @abstractmethod
    def get_instructions_for_objective(self, original_user_request: str, step_num: int = 0) -> Dict[str, Any]:
        """Abstract method for getting instructions from the LLM given an objective"""
        pass

    @abstractmethod
    def format_user_request_for_llm(self, original_user_request: str, step_num: int = 0) -> List[Dict[str, Any]]:
        """Abstract method for formatting the user request to be sent to the LLM"""
        pass

    @abstractmethod
    def convert_llm_response_to_json_instructions(self, llm_response: Any) -> Dict[str, Any]:
        """Abstract method to convert the LLM response into a JSON dictionary"""
        pass

    @abstractmethod
    def cleanup(self):
         """Abstract method to clean up resources used by the model"""
         pass