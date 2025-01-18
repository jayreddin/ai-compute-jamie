import json
import time
from typing import Any
import logging
from pathlib import Path
from multiprocessing import Queue

from models.model import Model
from openai import OpenAIError # type: ignore
from openai.types.beta.threads.message import Message # type: ignore
from screen import Screen
import tkinter as tk


# TODO
# [ ] Function calling with assistants api - https://platform.openai.com/docs/assistants/tools/function-calling/quickstart

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class GPT4o(Model):
    def __init__(self, model_name, base_url, api_key, context, status_queue: Queue):
        super().__init__(model_name, base_url, api_key, context, status_queue)

        try:
            # GPT4o has Assistant Mode enabled that we can utilize to make Open Interface be more contextually aware
            logging.info(f"Creating assistant with model {model_name}")
            self.assistant = self.client.beta.assistants.create(
                name='Open Interface Backend',
                instructions=self.context,
                model=model_name,
            )
            logging.info(f'Assistant created successfully, id: {self.assistant.id}')
        except openai.error.APIError as e: # import openai
            logging.error(f'API Error creating assistant: {e}')
            raise
        except openai.error.AuthenticationError as e: # import openai
            logging.error(f'Authentication Error creating assistant: {e}')
            raise
        except OpenAIError as e:
            logging.error(f'Other OpenAI Error creating assistant: {e}')
            raise

        try:
            logging.info("Creating a new thread")

            self.thread = self.client.beta.threads.create()
            logging.info(f"Thread created successfully, id: {self.thread.id}")
        except OpenAIError as e:
            logging.error(f"Error creating thread: {e}")
            raise

        # IDs of images uploaded to OpenAI for use with the assistants API, can be cleaned up once thread is no longer needed
        self.list_of_image_ids = []

    def get_instructions_for_objective(self, original_user_request: str, step_num: int = 0) -> dict[str, Any]:
        logging.info("Getting a screenshot to send to the AI model")
        # Upload screenshot to OpenAI - Note: Don't delete files from openai while the thread is active
        try:
            photo_image_filepath = Screen().get_screenshot_file()
        except Exception as e:
            logging.error(f"Error capturing screenshot: {e}")
            raise

        try:
            openai_screenshot_file_id = self.upload_screenshot_and_get_file_id(photo_image_filepath)
        except Exception as e:
            logging.error(f"Error uploading screenshot: {e}")
            raise

        logging.info("Screenshot obtained, file_id: " + str(openai_screenshot_file_id))
        
        self.status_queue.put(("I took a screenshot and sent it to the AI model", photo_image_filepath))


        self.list_of_image_ids.append(openai_screenshot_file_id)

        # Format user request to send to LLM
        formatted_user_request = self.format_user_request_for_llm(original_user_request, step_num,
                                                                  openai_screenshot_file_id)

        # Read response
        llm_response = self.send_message_to_llm(formatted_user_request)
        json_instructions: dict[str, Any] = self.convert_llm_response_to_json_instructions(llm_response)

        return json_instructions

    def send_message_to_llm(self, formatted_user_request) -> Message:
         try:
           message = self.client.beta.threads.messages.create(
               thread_id=self.thread.id,
               role='user',
               content=formatted_user_request
           )
           logging.info("Sending message to the ai model...")
           run = self.client.beta.threads.runs.create(
               thread_id=self.thread.id,
               assistant_id=self.assistant.id,
               instructions=''
           )
           run = self.client.beta.threads.runs.retrieve(thread_id = self.thread.id, run_id = run.id)

           wait_time = 1
           max_wait_time = 60
           while run.status != 'completed':
               logging.info(f'Waiting for response, sleeping for {wait_time}. run.status={run.status}')
               time.sleep(wait_time)
               wait_time = min(wait_time * 2, max_wait_time)  # Exponential backoff with a maximum wait time

               run = self.client.beta.threads.runs.retrieve(thread_id = self.thread.id, run_id = run.id) #check the status.


               if run.status == 'failed':
                  error_message = f'Failed run. Required action: {run.required_action}. Last error: {run.last_error}'
                  logging.error(error_message)
                  raise Exception(error_message)


           if run.status == 'completed':
               response = self.client.beta.threads.messages.list(thread_id=self.thread.id)
               logging.info("Response received from ai model")
               return response.data[0]
           else:
              error_message = 'Run did not complete successfully.'
              logging.error(error_message)
              raise Exception(error_message)
         except OpenAIError as e:
             logging.error(f"OpenAI Error in send_message_to_llm {e}")
             raise


    def upload_screenshot_and_get_file_id(self,filepath) -> str:
        # Files are used to upload documents like images that can be used with features like Assistants
        # Assistants API cannot take base64 images like chat.completions API
        logging.info("Uploading screenshot to AI model...")
        try:
            with open(filepath, 'rb') as file:
                response = self.client.files.create(
                    file=file,
                    purpose='vision'
                )
            return response.id
        except FileNotFoundError as e:
            logging.error(f"File not found error: {e}")
            raise
        except OpenAIError as e:
            logging.error(f"OpenAI Error {e}")
            raise
        except Exception as e:
            logging.error(f"Unknown error: {e}")
            logging.exception("Detailed traceback:")
            raise

    def format_user_request_for_llm(self, original_user_request, step_num, openai_screenshot_file_id) -> list[

        dict[str, Any]]:
        request_data: str = json.dumps({
            'original_user_request': original_user_request,
            'step_num': step_num
        })

        content = [
            {
                'type': 'text',
                'text': request_data
            },
            {
                'type': 'image_file',
                'image_file': {
                    'file_id': openai_screenshot_file_id
                }
            }
        ]

        return content

    def convert_llm_response_to_json_instructions(self, llm_response: Message) -> dict[str, Any]:
        try:
            llm_response_data: str = llm_response.content[0].text.value.strip()

            # Our current LLM model does not guarantee a JSON response hence we use regex to extract JSON
            import re # import re
            json_match = re.search(r'\{.*\}', llm_response_data, re.DOTALL)
            if json_match:
                json_response = json.loads(json_match.group())
                return json_response
            else:
                raise ValueError("No JSON object found in the response")

        except json.JSONDecodeError as e:
            logging.error(f"JSONDecodeError: {e}, response received: {llm_response.content[0].text.value}")
            return {"error": "JSONDecodeError", "message": str(e), "raw_data": llm_response.content[0].text.value}

        except Exception as e:
            logging.error(f'Error while parsing JSON response - {e}')
            return {}


    def cleanup(self):
        # Note: Cannot delete screenshots while the thread is active. Cleanup during shut down.
        logging.info(f"Cleaning up model {self.model_name}")
        for id in self.list_of_image_ids:
            try:
                logging.info(f"Deleting file with id: {id}")
                self.client.files.delete(id)
            except OpenAIError as e:
                logging.error(f"Error deleting file {id}: {e}")

        try:
            logging.info(f"Deleting thread with id: {self.thread.id}")
            self.client.beta.threads.delete(self.thread.id)
        except OpenAIError as e:
            logging.error(f"Error deleting thread {self.thread.id}: {e}")