# db_users.py
import logging
from decimal import Decimal
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError

logger = logging.getLogger()

def get_user(table, user_id: str) -> Optional[Dict[str, Any]]:
    """Obtiene los datos de un usuario."""
    try:
        response = table.get_item(Key={'userId': user_id})
        item = response.get('Item')
        if item and 'balance' in item and not isinstance(item['balance'], Decimal):
             # Asegurar que el balance sea Decimal si existe
             item['balance'] = Decimal(str(item['balance']))
        return item
    except ClientError as e:
        logger.error(f"Error de DynamoDB consultando usuario {user_id}: {e}", exc_info=True)
        raise # Relanzar para que el handler lo maneje
    except (TypeError, ValueError) as e:
         logger.error(f"Error convirtiendo balance a Decimal para usuario {user_id}: {e}", exc_info=True)
         # Podrías decidir retornar None o relanzar dependiendo de tu lógica de negocio
         raise ValueError(f"Formato de balance inválido para usuario {user_id}")


def update_user_balance(table, user_id: str, amount_to_deduct: Decimal) -> bool:
    """
    Intenta descontar el monto del balance del usuario.
    Retorna True si tiene éxito.
    Retorna False si falla por fondos insuficientes (ConditionalCheckFailedException).
    Lanza ClientError para otros errores de DB.
    """
    logger.info(f"Intentando descontar {amount_to_deduct} del balance de {user_id}")
    try:
        table.update_item(
            Key={'userId': user_id},
            UpdateExpression="SET balance = balance - :amt",
            ConditionExpression="attribute_exists(balance) AND balance >= :amt",
            ExpressionAttributeValues={':amt': amount_to_deduct},
            ReturnValues="NONE"
        )
        logger.info(f"Balance actualizado exitosamente para usuario {user_id}")
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            logger.warning(f"Saldo insuficiente detectado por DynamoDB para usuario {user_id}, monto: {amount_to_deduct}")
            return False # Fondos insuficientes
        else:
            logger.error(f"Error de DynamoDB actualizando balance para {user_id}: {e}", exc_info=True)
            raise # Relanzar otro error de DB