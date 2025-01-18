import json
import logging
import time
from queue import Queue
from typing import Any, Dict, List
from openai.types import Message
from openai import OpenAIError

from models.model import Model
from screen import Screen

class GPT4o(Model):
    MAX_RETRIES = 3
    RATE_LIMIT_DELAY = 20  # seconds
    POLL_INTERVAL = 1  # seconds

    def __init__(self, model_name, base_url, api_key, context, status_queue: Queue):
        super().__init__(model_name, base_url, api_key, context, status_queue)
        self.assistant = None
        self.thread = None
        self.list_of_image_ids = []
        self._initialize_assistant_and_thread()

    def _initialize_assistant_and_thread(self):
        try:
            logging.info(f"Creating assistant with model {self.model_name}")
            self.assistant = self.client.beta.assistants.create(
                name='Open Interface Backend',
                instructions=self.context,
                model=self.model_name,
            )
            logging.info(f'Assistant created successfully, id: {self.assistant.id}')

            logging.info("Creating a new thread")
            self.thread = self.client.beta.threads.create()
            logging.info(f"Thread created successfully, id: {self.thread.id}")
        except OpenAIError as e:
            logging.error(f"Error initializing assistant/thread: {e}")
            raise

    def send_message_to_llm(self, formatted_user_request, retries=0) -> Message:
        if not self.thread or not self.assistant:
            logging.error("Thread or Assistant not initialized")
            self._initialize_assistant_and_thread()

        try:
            # Send message to thread
            message = self.client.beta.threads.messages.create(
                thread_id=self.thread.id,
                role='user',
                content=formatted_user_request
            )

            # Create and monitor run
            run = self.client.beta.threads.runs.create(
                thread_id=self.thread.id,
                assistant_id=self.assistant.id,
                instructions=''
            )

            # Monitor run status with proper error handling
            while True:
                try:
                    run = self.client.beta.threads.runs.retrieve(
                        thread_id=self.thread.id,
                        run_id=run.id
                    )

                    if run.status == 'completed':
                        response = self.client.beta.threads.messages.list(
                            thread_id=self.thread.id
                        )
                        return response.data[0]
                    elif run.status in ['failed', 'cancelled', 'expired']:
                        error_msg = f"Run failed with status {run.status}: {getattr(run, 'last_error', 'Unknown error')}"
                        logging.error(error_msg)
                        raise Exception(error_msg)
                    elif run.status == 'requires_action':
                        logging.warning(f"Run requires action: {run.required_action}")
                        # Handle required actions if needed
                        raise Exception("Run requires manual action")
                    
                    time.sleep(self.POLL_INTERVAL)

                except OpenAIError as e:
                    if "Rate limit" in str(e) and retries < self.MAX_RETRIES:
                        logging.warning(f"Rate limit reached, retrying in {self.RATE_LIMIT_DELAY}s...")
                        time.sleep(self.RATE_LIMIT_DELAY)
                        return self.send_message_to_llm(formatted_user_request, retries + 1)
                    raise

        except OpenAIError as e:
            logging.error(f"OpenAI Error in send_message_to_llm: {e}")
            if retries < self.MAX_RETRIES:
                logging.info(f"Retrying... ({retries + 1}/{self.MAX_RETRIES})")
                time.sleep(self.RATE_LIMIT_DELAY)
                return self.send_message_to_llm(formatted_user_request, retries + 1)
            raise

    def upload_screenshot_and_get_file_id(self, photo_image_filepath: str) -> str:
        """Upload screenshot to OpenAI and get file ID."""
        try:
            with open(photo_image_filepath, "rb") as image_file:
                uploaded_file = self.client.files.create(
                    file=image_file,
                    purpose="assistants"
                )
                return uploaded_file.id
        except OpenAIError as e:
            logging.error(f"Error uploading screenshot: {e}")
            raise

    def format_user_request_for_llm(self, original_user_request: str, step_num: int = 0, file_id: str = None) -> str:
        """Format user request for Assistant API."""
        formatted_text = f"Step {step_num}: {original_user_request}"
        if file_id:
            formatted_text += f"\nScreenshot file_id: {file_id}"
        return formatted_text

    def convert_llm_response_to_json_instructions(self, llm_response: Message) -> Dict[str, Any]:
        """Convert Assistant API response to standardized JSON instructions."""
        try:
            # Assistant response should be in the content of the message
            content = llm_response.content[0].text.value if hasattr(llm_response.content[0], 'text') else llm_response.content[0]
            return json.loads(content)
        except (json.JSONDecodeError, AttributeError, IndexError) as e:
            logging.error(f"Error parsing model response: {str(e)}")
            raise Exception(f"Failed to parse model response: {str(e)}")

    def get_instructions_for_objective(self, original_user_request: str, step_num: int = 0) -> dict[str, Any]:
        logging.info("Getting a screenshot to send to the AI model")
        photo_image_filepath = Screen().get_screenshot_file()
        self.status_queue.put(("I took a screenshot and sent it to the AI model", photo_image_filepath))
        
        # Upload screenshot and get file ID
        file_id = self.upload_screenshot_and_get_file_id(photo_image_filepath)
        self.list_of_image_ids.append(file_id)
        
        message = self.format_user_request_for_llm(original_user_request, step_num, file_id)
        llm_response = self.send_message_to_llm(message)
        json_instructions = self.convert_llm_response_to_json_instructions(llm_response)
        return json_instructions

    def cleanup(self):
        logging.info(f"Cleaning up model {self.model_name}")
        try:
            # Clean up thread
            if hasattr(self, 'thread') and self.thread:
                try:
                    self.client.beta.threads.delete(self.thread.id)
                    logging.info(f"Thread {self.thread.id} deleted")
                except OpenAIError as e:
                    logging.warning(f"Failed to delete thread: {e}")

            # Clean up assistant
            if hasattr(self, 'assistant') and self.assistant:
                try:
                    self.client.beta.assistants.delete(self.assistant.id)
                    logging.info(f"Assistant {self.assistant.id} deleted")
                except OpenAIError as e:
                    logging.warning(f"Failed to delete assistant: {e}")

            # Clean up uploaded images
            for image_id in self.list_of_image_ids:
                try:
                    self.client.files.delete(image_id)
                    logging.info(f"Deleted image file {image_id}")
                except OpenAIError as e:
                    logging.warning(f"Failed to delete image {image_id}: {e}")
            
            self.list_of_image_ids.clear()
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")
            raise