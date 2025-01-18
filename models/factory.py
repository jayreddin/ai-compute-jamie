import logging

from models.gpt4o import GPT4o

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ModelFactory:
    _model_classes = {
        'gpt-4o': GPT4o,
        'gpt-4o-mini': GPT4o,
        'gpt-4-turbo': GPT4o,
        'claude-3-sonnet': GPT4o,
        'custom': GPT4o
    }

    @staticmethod
    def create_model(model_name, *args, **kwargs):
        try:
            logging.info(f"Creating model: {model_name}")
            model_class = ModelFactory._model_classes.get(model_name)
            if model_class:
                return model_class(model_name, *args, **kwargs)
            else:
                # Assume all other models are GPT4O
                logging.warning(f"Model type '{model_name}' not explicitly defined, assuming GPT4O.")
                return GPT4o(model_name, *args, **kwargs)
        except Exception as e:
            logging.error(f'Error creating model {model_name}: {e}')
            raise ValueError(f'Unsupported model type {model_name}. Create entry in app/models/. Error: {e}') from e