import os
import json
import logging
from abc import ABC, abstractmethod
from queue import Queue
from typing import Any, Dict, List
from openai import OpenAI, OpenAIError

class Model(ABC):
    """Abstract base class for all models"""
    # Common constants for rate limiting and retries
    MAX_RETRIES = 3
    RATE_LIMIT_DELAY = 20  # seconds
    POLL_INTERVAL = 1  # seconds

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
    def get_instructions_for_objective(self, original_user_request: str, step_num: int = 0) -> dict[str, Any]:
        pass

    @abstractmethod
    def format_user_request_for_llm(self, original_user_request: str, step_num: int = 0) -> List[Dict[str, Any]]:
        """Format user request in the expected format for the LLM."""
        pass

    @abstractmethod
    def convert_llm_response_to_json_instructions(self, llm_response: Any) -> Dict[str, Any]:
        """Convert LLM response to standardized JSON instructions format."""
        pass

    def cleanup(self):
        """Cleanup any resources used by the model."""
        logging.info(f"Cleaning up model {self.model_name}")
        # Default implementation - no cleanup needed