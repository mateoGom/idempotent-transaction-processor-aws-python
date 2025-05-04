# idempotent-transaction-processor-aws-python
Sistema serverless en AWS para procesar transacciones de pago de manera idempotente. Utiliza Lambda, DynamoDB, API Gateway, SNS y EventBridge para validar y ejecutar pagos. Si la transacción ya fue procesada, evita duplicados y garantiza consistencia en el sistema de pagos.
