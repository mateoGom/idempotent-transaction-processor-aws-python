# config.py
import os
import logging

logger = logging.getLogger()

# --- Constantes de Estado ---
STATUS_PENDING = 'PENDING'
STATUS_SUCCESS = 'SUCCESS'
STATUS_FAILED = 'FAILED'
STATUS_ERROR = 'ERROR'

# --- Constantes de Eventos ---
SOURCE_EVENT = 'transaction.processor'
DETAIL_TYPE_EVENT = 'TransactionEvent'

class ConfigError(Exception):
    """Excepción para errores de configuración."""
    pass

def load_config() -> dict:
    """Carga la configuración desde variables de entorno."""
    try:
        config = {
            'users_table_name': os.environ['USERS_TABLE'],
            'transactions_table_name': os.environ['TRANSACTIONS_TABLE'],
            'sns_topic_arn': os.environ['SNS_TOPIC_ARN'],
            'event_bus_name': os.environ['EVENT_BUS_NAME'],
        }
        logger.info("Configuración cargada exitosamente.")
        return config
    except KeyError as e:
        error_msg = f"Falta la variable de entorno: {str(e)}"
        logger.error(error_msg)
        raise ConfigError(error_msg)

# Cargar configuración al importar el módulo
try:
    APP_CONFIG = load_config()
    CONFIG_LOAD_SUCCESS = True
except ConfigError:
    APP_CONFIG = {}
    CONFIG_LOAD_SUCCESS = False