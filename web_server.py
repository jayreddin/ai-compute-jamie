import logging
import secrets
from threading import Thread
from flask import Flask, render_template, request, jsonify
from settings import Settings
import socket
import ssl
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__, template_folder='resources/templates')
settings = Settings()
app.user_and_ai_responses = [] # To store the responses for mobile view.
app.server_active = False
app.API_KEY = secrets.token_urlsafe(32)


def check_api_key():
    auth_header = request.headers.get('Authorization')
    if not auth_header or auth_header != f'Bearer {app.API_KEY}':
        return False
    return True

@app.route('/', methods=['GET', 'POST'])
def index():
    if not check_api_key():
        return jsonify(success=False, message="Unauthorized Access"), 401
    settings_dict = settings.get_dict()

    if request.method == 'POST':
        user_input = request.form.get('user_input')
        if user_input:
           logging.info(f"Received User Input via webserver: {user_input}")
           app.user_and_ai_responses.append(("user", user_input))
           app.user_request_queue.put(user_input)
        return render_template('index.html', settings=settings_dict, messages = app.user_and_ai_responses, api_key= app.API_KEY)
    else:
        return render_template('index.html', settings=settings_dict, messages = app.user_and_ai_responses, api_key= app.API_KEY)

@app.route('/settings', methods = ['GET', 'POST'])
def web_settings():
    if not check_api_key():
        return jsonify(success=False, message="Unauthorized Access"), 401
    if request.method == 'POST':
        theme = request.form.get('theme')
        api_key = request.form.get('api_key')
        default_browser = request.form.get('default_browser')
        play_ding_on_completion = request.form.get('play_ding_on_completion') == 'on'
        custom_llm_instructions = request.form.get('custom_llm_instructions')
        model = request.form.get('model')
        base_url = request.form.get('base_url')
        secure_connection = request.form.get('secure_connection') == 'on'

        settings_dict = {
            'theme': theme,
            'api_key': api_key,
            'default_browser': default_browser,
            'play_ding_on_completion': play_ding_on_completion,
            'custom_llm_instructions': custom_llm_instructions,
            'model': model,
            'base_url': base_url,
            'secure_connection': secure_connection,
        }

        settings.save_settings_to_file(settings_dict)
        settings.notify_settings_changed()
        logging.info(f"Settings updated from web browser: {settings_dict}")

        return jsonify(success=True, message="Settings saved successfully", settings=settings.get_dict())
    else:
         return render_template('settings.html', settings = settings.get_dict())

@app.route('/get-messages', methods = ['GET'])
def get_messages():
    if not check_api_key():
        return jsonify(success=False, message="Unauthorized Access"), 401
    return jsonify(success = True, messages = app.user_and_ai_responses)


def get_local_ip_address():
        """Get the local IP address for the web server"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception as e:
            logging.error(f"Error getting local IP address: {e}")
            return "127.0.0.1"

def run_server(host, port, user_request_queue):
        app.user_request_queue = user_request_queue
        settings_dict = settings.get_dict()
        if settings_dict.get('secure_connection'):
            logging.info(f"Starting web server on https://{host}:{port}")
            cert_path = 'resources/cert.pem'
            key_path = 'resources/key.pem'
            if os.path.exists(cert_path) and os.path.exists(key_path):
                 ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                 ssl_context.load_cert_chain(cert_path, key_path)
                 app.run(host=host, port = port, debug=False, use_reloader=False, ssl_context = ssl_context)
            else:
                logging.info(f"SSL files not found, running in HTTP mode.")
                app.run(host=host, port = port, debug=False, use_reloader=False)

        else:
            logging.info(f"Starting web server on http://{host}:{port}")
            app.run(host=host, port = port, debug=False, use_reloader=False)




def start_web_server(host = get_local_ip_address(), port = 5000, user_request_queue=None):
     if not user_request_queue:
           logging.error(f"Could not start web server, queue has not been set")
           return
     app.server_active = True
     server_thread = Thread(target=run_server, args=(host,port,user_request_queue), daemon=True)
     server_thread.start()

if __name__ == '__main__':
      #This is only used to run the web server in standalone mode for testing.
       #Should not be called when running from the app.py
      #Dummy Queue to start the app.
      start_web_server(user_request_queue = Queue())