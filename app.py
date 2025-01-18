import sys
import threading
import logging
from multiprocessing import freeze_support, Queue
import queue

from core import Core
from ui.main_window import MainWindow
from llm import LLM
from web_server import start_web_server, get_local_ip_address


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class App:
    """
    +----------------------------------------------------+
    | App                                                |
    |                                                    |
    |    +-------+                                       |
    |    |  GUI  |                                       |
    |    +-------+                                       |
    |        ^                                           |
    |        | (via MP Queues)                           |
    |        v                                           |
    |  +-----------+  (Screenshot + Goal)  +-----------+ |
    |  |           | --------------------> |           | |
    |  |    Core   |                       |    LLM    | |
    |  |           | <-------------------- |  (GPT-4V) | |
    |  +-----------+    (Instructions)     +-----------+ |
    |        |                                           |
    |        v                                           |
    |  +-------------+                                   |
    |  | Interpreter |                                   |
    |  +-------------+                                   |
    |        |                                           |
    |        v                                           |
    |  +-------------+                                   |
    |  |   Executer  |                                   |
    |  +-------------+                                   |
    +----------------------------------------------------+
    """

    def __init__(self):
        self.status_queue = Queue() # Initialize the status_queue here
        self.core = Core(self.status_queue)
        self.ui = MainWindow()
        self._stop_event = threading.Event()


        # Create threads to facilitate communication between core and ui through queues
        self.core_to_ui_connection_thread = threading.Thread(target=self.send_status_from_core_to_ui, daemon=True)
        self.ui_to_core_connection_thread = threading.Thread(target=self.send_user_request_from_ui_to_core, daemon=True)
        self.llm = LLM(self.status_queue)
        start_web_server(user_request_queue=self.ui.user_request_queue)

    def run(self) -> None:
        self.core_to_ui_connection_thread.start()
        self.ui_to_core_connection_thread.start()

        self.ui.mainloop()
        self._stop_event.set() # Set stop event when UI is closed

    def send_status_from_core_to_ui(self) -> None:
        while not self._stop_event.is_set():
            try:
                status: str = self.core.status_queue.get(timeout=0.1)  # added timeout to avoid blocking when the UI exits.
                logging.info(f'Sending status: {status}')
                self.ui.update_message(status)
            except queue.Empty:
                continue
            except Exception as e:
                 logging.error(f"Error in send_status_from_core_to_ui thread: {e}")
                 break

    def send_user_request_from_ui_to_core(self) -> None:
        while not self._stop_event.is_set():
            try:
                user_request: str = self.ui.user_request_queue.get(timeout=0.1)  # added timeout to avoid blocking when the UI exits.
                logging.info(f'Sending user request: {user_request}')

                if user_request == 'stop':
                    self.core.stop_previous_request()
                    self._stop_event.set()

                else:
                    threading.Thread(target=self.core.execute_user_request, args=(user_request,), daemon=True).start()
            except queue.Empty:
                continue
            except Exception as e:
                 logging.error(f"Error in send_user_request_from_ui_to_core thread: {e}")
                 break

    def cleanup(self):
        logging.info("Cleaning up application resources")
        self.core.cleanup()
        self.llm.cleanup()


if __name__ == '__main__':
    freeze_support()
    app = App()
    app.run()
    app.cleanup()
    sys.exit(0)