import threading
import webbrowser
from multiprocessing import Queue
from pathlib import Path
import logging
import tkinter as tk

import speech_recognition as sr
import ttkbootstrap as ttk
from PIL import Image, ImageTk

from settings import Settings  # Updated import
from version import version
from web_server import get_local_ip_address, start_web_server
import qrcode
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def open_link(url) -> None:
    webbrowser.open_new(url)

class MainWindow(ttk.Window):

    def change_theme(self, theme_name: str) -> None:
        self.style.theme_use(theme_name)

    def __init__(self):
        self.settings = Settings()
        settings_dict = self.settings.get_dict()
        theme = settings_dict.get('theme', 'superhero')

        try:
            super().__init__(themename=theme)
        except Exception as e:
            logging.error(f"Error applying theme, using default theme instead: {e}")
            super().__init__()  # https://github.com/AmberSahdev/Open-Interface/issues/35

        self.title('Jamie AI Compute')
        window_width = 550
        window_height = 450
        self.minsize(window_width, window_height)

        # Set the geometry of the window
        # Calculate position for bottom right corner
        screen_width = self.winfo_screenwidth()
        x_position = screen_width - window_width - 10  # 10px margin from the right edge
        y_position = 50  # 50px margin from the bottom edge
        self.geometry(f'{window_width}x{window_height}+{x_position}+{y_position}')
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # PhotoImage object needs to persist as long as the app does, hence it's a class object.
        try:
            path_to_icon_png = Path(__file__).resolve().parent.joinpath('resources', 'icon.png')
            path_to_microphone_png = Path(__file__).resolve().parent.joinpath('resources', 'microphone.png')
            with Image.open(path_to_icon_png) as img:
                resized_img = img.resize((50, 50))
                self.logo_img = ImageTk.PhotoImage(resized_img)
            with Image.open(path_to_microphone_png) as mic_image:
                with mic_image.resize((24, 24)).convert("RGBA") as resized_mic_image:
                    self.mic_icon = ImageTk.PhotoImage(resized_mic_image)

                for x in range(mic_image.width):
                    for y in range(mic_image.height):
                        r, g, b, a = mic_image.getpixel((x, y))
                        mic_image.putpixel((x, y), (255, 0, 0, a))

                self.mic_icon_red = ImageTk.PhotoImage(mic_image)
        except Exception as e:
            logging.error(f'Error loading images: {e}')

        # This adds app icon in linux which pyinstaller can't
        self.tk.call('wm', 'iconphoto', self._w, self.logo_img)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        # MP Queue to facilitate communication between UI and Core.
        self.user_request_queue = Queue()

        self.is_mic_active = False
        self.is_technical_output_visible = False
        self.local_ip = get_local_ip_address()
        self.server_running = False
        self.api_key = self.settings.get_dict().get("api_key")

        self.create_widgets()
        self._setup_logger()

    def create_widgets(self) -> None:
        # Creates and arranges the UI elements
        try:
            # Frame
            frame = ttk.Frame(self, padding='10 10 10 10')
            frame.grid(column=0, row=0, sticky=(ttk.W, ttk.E, ttk.N, ttk.S))
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(7, weight=1)

            # Entry widget
            self.entry = ttk.Entry(frame, font=('Helvetica', 14))
            self.entry.grid(column=0, row=1, sticky=(ttk.W, ttk.E), columnspan=3, pady=(0, 5))
            self.entry.insert(0, "Input Command")
            self.entry.bind("<FocusIn>", self.on_focus_in)
            self.entry.bind("<FocusOut>", self.on_focus_out)
            self.entry.bind("<Return>", self.execute_user_request)

            # Button Frame
            button_frame = ttk.Frame(frame)
            button_frame.grid(column=0, row=2, sticky=(ttk.W, ttk.E), columnspan=3, pady=(0, 5))

            button_frame.columnconfigure(0, weight=1)
            button_frame.columnconfigure(1, weight=1)
            button_frame.columnconfigure(2, weight=1)
            # Submit Button
            submit_button = ttk.Button(button_frame, text='Submit', bootstyle="success", command=self.execute_user_request)
            submit_button.grid(column=0, row=0, sticky="ew", padx=(0, 5))

            # Mic Button
            self.mic_button = ttk.Button(button_frame, image=self.mic_icon, bootstyle="link", command=self.start_voice_input_thread)
            self.mic_button.grid(column=1, row=0, sticky="ew", padx=(0, 5))
            # Stop Button
            stop_button = ttk.Button(button_frame, text='Stop', bootstyle="danger-outline", command=self.stop_previous_request)
            stop_button.grid(column=2, row=0, sticky="ew")

            # Text display for echoed input and ai response
            self.input_display = ttk.Label(frame, text='', font=('Helvetica', 14), wraplength=500, justify="left")
            self.input_display.grid(column=0, row=3, columnspan=3, sticky=ttk.W, pady=(0, 5))

            # Loading Bar
            self.progress_bar = ttk.Progressbar(frame, mode="indeterminate", bootstyle="success", length=400)
            self.progress_bar.grid(column=0, row=4, columnspan=3, sticky=ttk.EW, pady=(0, 5))
            self.progress_bar.grid_remove()

            # Text display for additional messages
            log_label = ttk.Label(frame, text='Log Output', font=('Helvetica', 12), bootstyle="secondary")
            log_label.grid(column=0, row=5, columnspan=3, sticky=ttk.W, pady=(0, 5))

            self.message_display = ttk.ScrolledText(frame, wrap=ttk.WORD, font=('Helvetica', 10), height=8)
            self.message_display.grid(column=0, row=6, columnspan=3, sticky=(ttk.W, ttk.E, ttk.N, ttk.S), pady=(0, 5))

            # Technical Output Frame
            self.technical_output_frame = ttk.Frame(frame, padding='5 5 5 5')
            self.technical_output_frame.grid(column=0, row=7, columnspan=3, sticky=(ttk.W, ttk.E, ttk.N, ttk.S), pady=(0, 5))
            self.technical_output_frame.columnconfigure(0, weight=1)
            self.technical_output_frame.rowconfigure(1, weight=1)

            # Technical Output Text Box
            log_label = ttk.Label(self.technical_output_frame, text='Technical Output', font=('Helvetica', 12), bootstyle="secondary")
            log_label.grid(column=0, row=0, sticky=ttk.W, pady=(0, 5))
            self.technical_output_display = ttk.ScrolledText(self.technical_output_frame, wrap=ttk.WORD, font=('Helvetica', 10), height=15)
            self.technical_output_display.grid(column=0, row=1, sticky=(ttk.W, ttk.E, ttk.N, ttk.S))

            # Hide Technical Output Initially
            self.technical_output_frame.grid_remove()

            # Mobile Control Button
            self.mobile_control_button = ttk.Button(frame, text='Mobile Control', bootstyle="info-outline", command=self.toggle_web_server)
            self.mobile_control_button.grid(column=0, row=9, columnspan=3, sticky=ttk.W, pady=(0, 5))
            # View Technical Output Button
            technical_output_button = ttk.Button(frame, text='View technical output', bootstyle="info",
                                                 command=self.toggle_technical_output)
            technical_output_button.grid(column=0, row=10, columnspan=3, sticky=ttk.W, pady=(0, 5))

            # Server Address
            self.server_address_label = ttk.Label(frame, text=f'http://{self.local_ip}:5000', font=('Helvetica', 8), bootstyle="secondary")
            self.server_address_label.grid(column=0, row=11, columnspan=3, sticky=ttk.W, pady=(0, 5))
            self.server_address_label.grid_remove()

            # Settings Button
            settings_button = ttk.Button(self, text='Settings', bootstyle="info-outline", command=self._open_settings)
            settings_button.place(relx=1.0, rely=0.0, anchor='ne', x=-5, y=5)

        except Exception as e:
            logging.error(f'Error creating widgets: {e}')

    def toggle_technical_output(self) -> None:
        """Toggles the visibility of the technical output section"""
        if self.is_technical_output_visible:
            self.technical_output_frame.grid_remove()
            for handler in logging.getLogger().handlers[:]:  # make a copy of the list to avoid errors
                if isinstance(handler, self.TkLoggingHandler):
                    logging.getLogger().removeHandler(handler)
        else:
            self.technical_output_frame.grid()
            self._setup_logger()

        self.is_technical_output_visible = not self.is_technical_output_visible

    def toggle_web_server(self) -> None:
        """Toggles the visibility of the web server address, and starts or stops the server, and shows a QR code"""
        if self.server_running:
            self.server_address_label.grid_remove()
            self.server_running = False
        else:
            self.server_address_label.grid()
            if not hasattr(self, 'web_server_thread') or not self.web_server_thread.is_alive():
                self.web_server_thread = threading.Thread(target=start_web_server, args=(self.local_ip, 5000, self.user_request_queue), daemon=True)
                self.web_server_thread.start()
            self.show_qr_code()
            self.server_running = True

    def show_qr_code(self):
        # Create QR Code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(f'http://{self.local_ip}:5000/?api_key={self.api_key}')
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        # Convert PIL Image to PhotoImage
        photo = ImageTk.PhotoImage(img)

        # Create Pop-up
        popup = ttk.Toplevel(self)
        popup.title("Scan QR Code")
        label = ttk.Label(popup, image=photo)
        label.image = photo  # keep a reference!
        label.pack(padx=10, pady=10)

    def _open_settings(self) -> None:
        """Opens the settings window"""
        try:
            from ui.settings_window import SettingsWindow
            SettingsWindow(self)
        except Exception as e:
            logging.error(f'Error opening settings window: {e}')

    def stop_previous_request(self) -> None:
        # Interrupt currently running request by queueing a stop signal.
        self.user_request_queue.put('stop')

    def on_focus_in(self, event):
        if self.entry.get() == "Input Command":
            self.entry.delete(0, ttk.END)

    def on_focus_out(self, event):
        if self.entry.get() == "":
            self.entry.insert(0, "Input Command")

    def display_input(self) -> str:
        # Get the entry and update the input display
        user_input = self.entry.get()
        self.input_display['text'] = f'User Command: {user_input}'

        # Clear the entry widget
        self.entry.delete(0, ttk.END)

        return user_input.strip()

    def execute_user_request(self, event=None) -> None:
        try:
            # Puts the user request received from the UI into the MP queue being read in App to be sent to Core.
            user_request = self.display_input()

            if user_request == '' or user_request is None:
                return
            self.progress_bar.start()
            self.update_message('AI is processing your request...')
            self.user_request_queue.put(user_request)
        except Exception as e:
            logging.error(f"Error executing user request: {e}")

    def start_voice_input_thread(self) -> None:
        # Start voice input in a separate thread
        threading.Thread(target=self.voice_input, daemon=True).start()
        self.is_mic_active = True
        self.mic_button.configure(image=self.mic_icon_red)  # changed to configure

    def voice_input(self) -> None:
        # Function to handle voice input
        recognizer = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                self.update_message('Listening...')
                # This might also help with asking for mic permissions on Macs
                recognizer.adjust_for_ambient_noise(source)
                try:
                    audio = recognizer.listen(source, timeout=4)
                    try:
                        text = recognizer.recognize_google(audio)
                        self.entry.delete(0, ttk.END)
                        self.entry.insert(0, text)
                        self.update_message('')
                    except sr.UnknownValueError:
                        self.update_message('Could not understand audio')
                    except sr.RequestError as e:
                        self.update_message(f'Could not request results - {e}')
                except sr.WaitTimeoutError:
                    self.update_message('Didn\'t hear anything')
        except Exception as e:
            logging.error(f"Error during voice input: {e}")
        finally:
            self.is_mic_active = False
            self.mic_button.configure(image=self.mic_icon)  # changed to configure

    def update_message(self, message: str, image: ImageTk.PhotoImage = None) -> None:
        # Update the message display with the provided text.
        # Ensure thread safety when updating the Tkinter GUI.
        if message == "Probability of unsafe content":
            logging.info("Filtered out unsafe response")
            return

        def insert_message():
            if isinstance(message, str):
                self.message_display.insert(0.0, message + '\n')
            elif isinstance(message, tuple) and len(message) == 2 and isinstance(message[0], str) and isinstance(message[1], str):
                try:
                    with Image.open(message[1]) as img_file:
                        img = ImageTk.PhotoImage(img_file)
                        self.message_display.insert(0.0, message[0] + '\n')
                        self.message_display.image_create(0.0, image=img)
                        self.message_display.insert(0.0, '\n')
                except Exception as e:
                    logging.error(f"Error loading image from path {message[1]}: {e}")
                    self.message_display.insert(0.0, f"Error loading image from path {message[1]}: {e}" + '\n')
            self.message_display.see(0.0)

        if threading.current_thread() == threading.main_thread():
            insert_message()
            if self.progress_bar.winfo_ismapped():
                self.progress_bar.stop()
                self.progress_bar.grid_remove()
        else:
            self.message_display.after(0, insert_message)
            if self.progress_bar.winfo_ismapped():
                self.progress_bar.after(0, self.progress_bar.stop)
                self.progress_bar.after(0, self.progress_bar.grid_remove)

    # Redirect logging to text widget
    class TkLoggingHandler(logging.Handler):
        def __init__(self, text_widget):
            super().__init__()
            self.text_widget = text_widget

        def emit(self, record):
            msg = self.format(record)
            self.text_widget.insert(0.0, msg + '\n')
            self.text_widget.see(0.0)  # Scroll to the top

    def _setup_logger(self):
        handler = self.TkLoggingHandler(self.technical_output_display)
        logging.getLogger().addHandler(handler)

        # Log a message to show that the handler is working.
        logging.info("Starting to log messages...")

    def _cleanup_logger(self):
        for handler in logging.getLogger().handlers[:]:  # make a copy of the list to avoid errors
            if isinstance(handler, self.TkLoggingHandler):
                logging.getLogger().removeHandler(handler)
        logging.info("Finished logging messages...")

    def on_closing(self):
        self._cleanup_logger()
        self.user_request_queue.close()
        if hasattr(self, 'web_server_thread') and self.web_server_thread.is_alive():
            self.web_server_thread.join(timeout=5)
        self.destroy()

    def destroy(self):
        self._cleanup_logger()
        super().destroy()
        self.model_var.set('gpt-4o')  # Set default model to gpt-4o