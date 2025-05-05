# db_transactions.py
import logging
from decimal import Decimal
from typing import Dict, Any, Optional, List
from botocore.exceptions import ClientError

# Importar constantes de estado desde config
from config import STATUS_PENDING

logger = logging.getLogger()

def create_pending_transaction(table, tx_data: Dict[str, Any], request_id: str) -> bool:
    """
    Intenta crear un registro de transacción inicial en estado PENDING.
    Retorna True si se crea, False si ya existe (idempotencia).
    Lanza ClientError en otros errores de DB.
    """
    transaction_id = tx_data['transaction_id']
    try:
        table.put_item(
            Item={
                'transactionId': transaction_id,
                'userId': tx_data['user_id'],
                'amount': tx_data['amount'], # Boto3 maneja Decimal
                'status': STATUS_PENDING,
                'createdAt': request_id # O un timestamp real
            },
            ConditionExpression='attribute_not_exists(transactionId)'
        )
        logger.info(f"Registro inicial creado para TxID {transaction_id}")
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            logger.warning(f"Transacción {transaction_id} ya existe (Idempotencia).")
            return False # Ya existe, no es un error, es idempotencia
        else:
            logger.error(f"Error de DynamoDB al crear registro para TxID {transaction_id}: {e}", exc_info=True)
            raise # Relanzar para que el handler lo maneje

def update_transaction_status(table, transaction_id: str, status: str, message: Optional[str] = None):
    """Actualiza el estado y opcionalmente el mensaje de una transacción."""
    logger.info(f"Actualizando TxID {transaction_id} a estado {status}")
    try:
        update_expression = "SET #st = :s"
        expression_attribute_values = {':s': status}
        expression_attribute_names = {'#st': 'status'}

        if message:
            update_expression += ", message = :m"
            expression_attribute_values[':m'] = message

        table.update_item(
            Key={'transactionId': transaction_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names
        )
        logger.info(f"Estado de TxID {transaction_id} actualizado a {status}")
    except ClientError as e:
        logger.error(f"Error actualizando estado de TxID {transaction_id} a {status}: {e}", exc_info=True)
        # Considerar si relanzar o solo loguear. Por ahora, loguear.

def update_transaction_status_conditionally(table, transaction_id: str, status: str, message: str, avoid_statuses: List[str]):
    """Actualiza el estado solo si el estado actual NO está en avoid_statuses."""
    logger.info(f"Intentando actualizar TxID {transaction_id} a estado {status} (condicional)")
    try:
        condition_parts = [f"#st <> :{status_val}" for status_val in avoid_statuses]
        condition_expression = " AND ".join(condition_parts)

        expression_attribute_values = {f':{status_val}': status_val for status_val in avoid_statuses}
        expression_attribute_values[':s'] = status
        expression_attribute_values[':m'] = message[:400] # Limitar longitud

        table.update_item(
            Key={'transactionId': transaction_id},
            UpdateExpression="SET #st = :s, message = :m",
            ConditionExpression=condition_expression,
            ExpressionAttributeNames={'#st': 'status'},
            ExpressionAttributeValues=expression_attribute_values
        )
        logger.info(f"Estado de TxID {transaction_id} actualizado condicionalmente a {status}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            logger.warning(f"No se actualizó TxID {transaction_id} a {status} porque su estado actual está en {avoid_statuses}.")
        else:
            logger.error(f"Error actualizando condicionalmente TxID {transaction_id} a {status}: {e}", exc_info=True)
        # No relanzar, es un intento de 'mejor esfuerzo' en el manejo de errores