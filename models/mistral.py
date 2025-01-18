import json
from typing import Any
import logging
from multiprocessing import Queue

from models.model import Model
from screen import Screen

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MistralLarge(Model):
     def __init__(self, model_name, base_url, api_key, context, status_queue: Queue):
        super().__init__(model_name, base_url, api_key, context, status_queue)
        logging.error("Mistral Large is not correctly supported, please use another model")
        raise ValueError(f"Unsupported model type {model_name}. Please use another model.")

     def get_instructions_for_objective(self, original_user_request: str, step_num: int = 0) -> dict[str, Any]:
        logging.info("Taking a screenshot to send to ai model...")
        message: list[dict[str, Any]] = self.format_user_request_for_llm(original_user_request, step_num)
        llm_response = self.send_message_to_llm(message)
        json_instructions: dict[str, Any] = self.convert_llm_response_to_json_instructions(llm_response)
        return json_instructions

     def format_user_request_for_llm(self, original_user_request, step_num) -> list[dict[str, Any]]:
        logging.info("Taking a screenshot to send to ai model...")
        base64_img: str = Screen().get_screenshot_in_base64()
        logging.info("Screenshot has been taken.")

        request_data: str = json.dumps({
            'original_user_request': original_user_request,
            'step_num': step_num
        })

        # We have to add context every request for now which is expensive because our chosen model doesn't have a
        #   stateful/Assistant mode yet.
        message = [
            {'type': 'text', 'text': self.context + request_data},
         ]
        return message

     def send_message_to_llm(self, message) -> str:
          logging.info("Sending message to the ai model...")
          logging.error("Mistral Large is not correctly supported, please use another model")
          raise ValueError(f"Unsupported model type {self.model_name}. Please use another model.")
          return ""
          

     def convert_llm_response_to_json_instructions(self, llm_response: str) -> dict[str, Any]:
         llm_response_data: str = llm_response.strip()

         # Our current LLM model does not guarantee a JSON response hence we manually parse the JSON part of the response
         # Check for updates here - https://platform.openai.com/docs/guides/text-generation/json-mode
         start_index = llm_response_data.find('{')
         end_index = llm_response_data.rfind('}')

         try:
            json_response = json.loads(llm_response_data[start_index:end_index + 1].strip())
            return json_response
         except Exception as e:
             logging.error(f'Error while parsing JSON response - {e}')
             return {}

     def cleanup(self):
          logging.info(f"Cleaning up model {self.model_name}")
          self.client = None