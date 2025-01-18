import json
import logging
import time
from queue import Queue
import base64
from typing import Any, Dict, List
from openai.types.chat import ChatCompletion
from openai import OpenAIError

from models.model import Model
from screen import Screen

class GPT4v(Model):
    def __init__(self, model_name, base_url, api_key, context, status_queue: Queue):
        super().__init__(model_name, base_url, api_key, context, status_queue)

    def get_instructions_for_objective(self, original_user_request: str, step_num: int = 0) -> dict[str, Any]:
        logging.info("Getting a screenshot to send to the AI model")
        photo_image_filepath = Screen().get_screenshot_file()
        base64_img = Screen().get_screenshot_in_base64()
        self.status_queue.put(("I took a screenshot and sent it to the AI model", photo_image_filepath))
        
        message = self.format_user_request_for_llm(original_user_request, step_num, base64_img)
        llm_response = self.send_message_to_llm(message)
        json_instructions: dict[str, Any] = self.convert_llm_response_to_json_instructions(llm_response)
        return json_instructions

    def format_user_request_for_llm(self, original_user_request: str, step_num: int, base64_img: str) -> list[dict[str, Any]]:
        return [
            {
                "role": "system",
                "content": self.context
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Step {step_num}: {original_user_request}"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_img}"
                        }
                    }
                ]
            }
        ]

    def send_message_to_llm(self, message, retries=0) -> ChatCompletion:
        logging.info("Sending message to the AI model...")
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=message,
                max_tokens=800,
                temperature=0.7
            )
            return response
        except OpenAIError as e:
            if "Rate limit" in str(e) and retries < self.MAX_RETRIES:
                logging.warning(f"Rate limit reached, retrying in {self.RATE_LIMIT_DELAY}s... ({retries + 1}/{self.MAX_RETRIES})")
                time.sleep(self.RATE_LIMIT_DELAY)
                return self.send_message_to_llm(message, retries + 1)
            logging.error(f"OpenAI Error: {str(e)}")
            raise

    def convert_llm_response_to_json_instructions(self, llm_response: ChatCompletion) -> dict[str, Any]:
        try:
            response_message = llm_response.choices[0].message
            return json.loads(response_message.content)
        except (json.JSONDecodeError, AttributeError, IndexError) as e:
            logging.error(f"Error parsing model response: {str(e)}")
            raise Exception(f"Failed to parse model response: {str(e)}")

    def cleanup(self):
        logging.info(f"Cleaning up model {self.model_name}")
        # No specific cleanup needed for GPT4v