# utils.py
import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger()

def build_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Construye la respuesta HTTP para API Gateway."""
    # Usar default=str para manejar Decimal en json.dumps si es necesario
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
        },
        'body': json.dumps(body, default=str)
    }

def parse_and_validate_input(event_body: Optional[str]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Parsea y valida el cuerpo del evento.
    Retorna un diccionario con los datos validados o (None, mensaje_error).
    """
    if not event_body:
        logger.warning("Cuerpo de la solicitud vacío.")
        return None, "Cuerpo de la solicitud vacío."

    try:
        body = json.loads(event_body)
        transaction_id = body.get('transactionId')
        user_id = body.get('userId')
        amount_str = body.get('amount')

        if not transaction_id or not user_id or amount_str is None:
            raise ValueError("Faltan campos requeridos: transactionId, userId, amount")

        # Convertir a Decimal de forma segura
        amount = Decimal(str(amount_str))
        if amount <= 0:
            raise ValueError("El monto debe ser positivo.")

        # Opcional: redondear/validar decimales
        # amount = amount.quantize(Decimal("0.01"), rounding=ROUND_DOWN)

        return {
            'transaction_id': transaction_id,
            'user_id': user_id,
            'amount': amount
        }, None

    except (json.JSONDecodeError, TypeError):
        logger.warning("Error decodificando JSON del body.", exc_info=True)
        return None, "Cuerpo de la solicitud inválido (no es JSON válido)."
    except (ValueError, KeyError, InvalidOperation) as e:
        logger.warning(f"Validación de entrada fallida: {e}")
        return None, f"Datos de entrada inválidos: {e}"