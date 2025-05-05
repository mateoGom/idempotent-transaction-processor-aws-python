# lambda_function.py
import logging
import json
from decimal import Decimal
from typing import Dict, Any

import boto3
from botocore.exceptions import ClientError

# Importar configuración, constantes y funciones de módulos separados
from config import (APP_CONFIG, CONFIG_LOAD_SUCCESS, STATUS_SUCCESS,
                    STATUS_FAILED, STATUS_ERROR)
from utils import build_response, parse_and_validate_input
from db_transactions import (create_pending_transaction, update_transaction_status,
                             update_transaction_status_conditionally)
from db_users import get_user, update_user_balance
from event_publisher import publish_event

# --- Configuración del Logger ---
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- Inicialización Global ---
# Realizada al importar los módulos y cargar APP_CONFIG en config.py
# Aquí inicializamos los clientes que dependen de boto3
if CONFIG_LOAD_SUCCESS:
    try:
        dynamodb = boto3.resource('dynamodb')
        sns_client = boto3.client('sns')
        events_client = boto3.client('events')

        # Obtener objetos Table
        users_table = dynamodb.Table(APP_CONFIG['users_table_name'])
        transactions_table = dynamodb.Table(APP_CONFIG['transactions_table_name'])

        INITIALIZATION_SUCCESS = True
        logger.info("Clientes Boto3 y Tablas DynamoDB inicializados.")
    except Exception as e:
        logger.critical(f"Error crítico inicializando clientes/tablas AWS: {e}", exc_info=True)
        INITIALIZATION_SUCCESS = False
else:
    INITIALIZATION_SUCCESS = False
    # Error ya logueado durante la carga de config


# --- Handler Principal ---
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Punto de entrada de AWS Lambda."""

    # Verificar si la inicialización global falló
    if not INITIALIZATION_SUCCESS:
        return build_response(500, {'message': 'Error de configuración interna del servidor.'})

    # 1. Parsear y Validar Entrada
    tx_data, error_message = parse_and_validate_input(event.get('body'))
    if error_message:
        return build_response(400, {'message': error_message})

    # Extraer datos validados
    transaction_id = tx_data['transaction_id']
    user_id = tx_data['user_id']
    amount = tx_data['amount']
    final_status_code = 500 # Default a error
    final_response_body = {'message': 'Error interno procesando la transacción.'}


    try:
        # 2. Intentar crear registro (Idempotencia)
        created = create_pending_transaction(transactions_table, tx_data, context.aws_request_id)
        if not created:
            # Ya existía, idempotencia
            final_status_code = 200
            final_response_body = {'message': f"Transacción {transaction_id} ya procesada o en proceso."}
            return build_response(final_status_code, final_response_body) # Salida temprana

        # 3. Consultar Usuario
        user = get_user(users_table, user_id)
        if not user:
            message = f"Usuario {user_id} no encontrado."
            logger.warning(f"{message} para TxID {transaction_id}.")
            update_transaction_status(transactions_table, transaction_id, STATUS_FAILED, message)
            publish_event(sns_client, events_client, APP_CONFIG['sns_topic_arn'], APP_CONFIG['event_bus_name'],
                          transaction_id, user_id, STATUS_FAILED, message)
            final_status_code = 404
            final_response_body = {'message': message}
            return build_response(final_status_code, final_response_body) # Salida temprana

        current_balance = user.get('balance', Decimal('0')) # Ya debería ser Decimal por get_user
        logger.info(f"Usuario {user_id} encontrado con balance {current_balance} para TxID {transaction_id}.")


        # 4. Intentar Descontar Saldo (Atómico)
        balance_updated = update_user_balance(users_table, user_id, amount)

        if not balance_updated:
            # Falló por fondos insuficientes
            message = "Saldo insuficiente."
            logger.warning(f"{message} para usuario {user_id}, TxID {transaction_id}.")
            update_transaction_status(transactions_table, transaction_id, STATUS_FAILED, message)
            publish_event(sns_client, events_client, APP_CONFIG['sns_topic_arn'], APP_CONFIG['event_bus_name'],
                          transaction_id, user_id, STATUS_FAILED, message)
            final_status_code = 400
            final_response_body = {'message': message}
            return build_response(final_status_code, final_response_body) # Salida temprana

        # 5. Marcar Transacción como Exitosa
        success_message = "Transacción procesada exitosamente."
        update_transaction_status(transactions_table, transaction_id, STATUS_SUCCESS, success_message)

        # 6. Publicar Evento de Éxito
        publish_event(sns_client, events_client, APP_CONFIG['sns_topic_arn'], APP_CONFIG['event_bus_name'],
                      transaction_id, user_id, STATUS_SUCCESS, success_message)

        # 7. Preparar Respuesta Exitosa
        final_status_code = 200
        final_response_body = {'message': success_message, 'transactionId': transaction_id}

    except ClientError as e: # Errores específicos de Boto3/DynamoDB no manejados antes
        error_message = f"Error interno del servicio (DB): {e.response['Error']['Code']}"
        logger.error(f"{error_message} durante procesamiento de TxID {transaction_id}", exc_info=True)
        # Intentar marcar como ERROR, si es posible y no tiene estado final
        update_transaction_status_conditionally(
            transactions_table, transaction_id, STATUS_ERROR, error_message,
            avoid_statuses=[STATUS_SUCCESS, STATUS_FAILED]
        )
        publish_event(sns_client, events_client, APP_CONFIG['sns_topic_arn'], APP_CONFIG['event_bus_name'],
                      transaction_id, user_id, STATUS_ERROR, error_message)
        final_status_code = 500
        final_response_body = {'message': 'Error interno del servidor.'}

    except Exception as e: # Otros errores inesperados
        error_message = f"Error inesperado: {str(e)}"
        logger.error(f"{error_message} durante procesamiento de TxID {transaction_id or 'desconocida'}", exc_info=True)
        # Intentar marcar como ERROR, si es posible y tenemos ID y no tiene estado final
        if transaction_id:
            update_transaction_status_conditionally(
                transactions_table, transaction_id, STATUS_ERROR, error_message,
                avoid_statuses=[STATUS_SUCCESS, STATUS_FAILED]
            )
            publish_event(sns_client, events_client, APP_CONFIG['sns_topic_arn'], APP_CONFIG['event_bus_name'],
                          transaction_id, user_id, STATUS_ERROR, error_message)
        final_status_code = 500
        final_response_body = {'message': 'Error interno procesando la transacción.'}


    # Construir y Retornar Respuesta Final
    return build_response(final_status_code, final_response_body)