# event_publisher.py
import json
import logging
from typing import Optional
from botocore.exceptions import ClientError

# Importar constantes de eventos desde config
from config import SOURCE_EVENT, DETAIL_TYPE_EVENT

logger = logging.getLogger()

def _publish_sns(sns_client, topic_arn: str, detail_json: str, transaction_id: str, status: str):
    """Publica en SNS."""
    try:
        sns_client.publish(
            TopicArn=topic_arn,
            Message=detail_json,
            Subject=f"Transacción {transaction_id} - {status}"
        )
        logger.info(f"Evento SNS publicado para TxID {transaction_id}, Status: {status}")
    except ClientError as e:
        logger.error(f"Error publicando en SNS para TxID {transaction_id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error inesperado publicando en SNS para TxID {transaction_id}: {e}", exc_info=True)

def _publish_eventbridge(events_client, bus_name: str, detail_json: str, transaction_id: str, status: str):
    """Publica en EventBridge."""
    try:
        events_client.put_events(
            Entries=[{
                'Source': SOURCE_EVENT,
                'DetailType': DETAIL_TYPE_EVENT,
                'Detail': detail_json,
                'EventBusName': bus_name
            }]
        )
        logger.info(f"Evento EventBridge publicado para TxID {transaction_id}, Status: {status}")
    except ClientError as e:
        logger.error(f"Error publicando en EventBridge para TxID {transaction_id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error inesperado publicando en EventBridge para TxID {transaction_id}: {e}", exc_info=True)

def publish_event(sns_client, events_client, sns_topic_arn: str, event_bus_name: str,
                  transaction_id: str, user_id: Optional[str], status: str, message: str):
    """Publica el mismo evento en SNS y EventBridge."""
    detail = {
        'transactionId': transaction_id,
        'userId': user_id,
        'status': status,
        'message': message
    }
    # Usar default=str para manejar Decimal en json.dumps
    detail_json = json.dumps(detail, default=str)

    _publish_sns(sns_client, sns_topic_arn, detail_json, transaction_id, status)
    _publish_eventbridge(events_client, event_bus_name, detail_json, transaction_id, status)