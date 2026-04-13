import os
import hmac
import hashlib
import logging
import mercadopago

from typing import Any
from datetime import datetime
from utils.database import actualizar_pago

logger = logging.getLogger(__name__)

MP_ACCESS_TOKEN = os.getenv('MP_ACCESS_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

class MercadoPagoSimple:
    def __init__(self):
        self.sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
    
    def crear_pago(self, titulo, monto, telegram_id, invoice_id, email_cliente):
        """
        Crea un pago único y devuelve link para pagar
        """
        # Referencia externa para identificar al usuario
        #external_reference = f"telegram_{telegram_id}_{monto}"
        external_reference = f"telegram_{telegram_id}_{invoice_id}_{monto}"
        
        preference_data = {
            "items": [
                {
                    "title": titulo,
                    "quantity": 1,
                    "currency_id": "ARS",
                    "unit_price": float(monto)
                }
            ],
            "payer": {
                "email": email_cliente
            },
            "back_urls": {
                "success": f"{WEBHOOK_URL}/okpago",  # Opcional
                "failure": f"{WEBHOOK_URL}/failpago",  # Opcional
                "pending": f"{WEBHOOK_URL}/pendpago"   # Opcional
            },
            "auto_return": "approved",
            "notification_url": f"{WEBHOOK_URL}/mercadopago-webhook/",
            "external_reference": external_reference,
            "metadata": {
                "telegram_id": telegram_id,
                "invoice_id": invoice_id,
                "monto": monto
            }
        }
        
        # Crear preferencia
        response = self.sdk.preference().create(preference_data)
        logger.info(
            "Preferencia de Mercado Pago creada",
            extra={
                "invoice_id": invoice_id,
                "telegram_id": telegram_id,
                "response_status": response.get("status"),
            },
        )

        if response["status"] == 201:
            return {
                "success": True,
                "preference_id": response["response"]["id"],
                #"init_point": response["response"]["init_point"],  # Link para pagar en PRD
                "init_point": response["response"]["sandbox_init_point"],  # Link para pagar en sandbox 
                "external_reference": external_reference
            }

        else:
            return {
                "success": False,
                "error": response["response"]
            }
        
    
    def obtener_pago(self, payment_id) -> dict[Any, Any] | None:
        """Obtiene información de un pago específico"""
        try:
            response = self.sdk.payment().get(payment_id)
            logger.debug("Consulta de pago en Mercado Pago", extra={"payment_id": payment_id, "response_status": response.get("status")})

            if response["status"] == 200:
                pago = response["response"]
                
                # Extraer solo lo necesario
                return {
                    "success": True,
                    "pago": {
                        "id": pago["id"],
                        "status": pago["status"],  # approved, pending, rejected
                        "status_detail": pago.get("status_detail", ""),
                        "monto": pago["transaction_amount"],
                        "external_reference": pago.get("external_reference", ""),
                        "metadata": pago.get("metadata", {}),
                        "fecha_aprobado": pago.get("date_approved", ""),
                        "metodo_pago": pago.get("payment_method", {}).get("id", "")
                    }
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
        

    def procesar_merchant_order(self, resource_id):
        try:    
            order = self.sdk.merchant_order().get(resource_id)["response"]
            payments = order.get("payments", [])
            
            for payment in payments:
                payment_id = payment["id"]
                if payment["status"] == "approved":
                    # No necesitamos verificar firma para cada pago
                    # porque ya viene dentro de una orden
                    self.procesar_pago(payment_id, desde_orden=True)

        except Exception as e:
            logger.error("Error procesando merchant_order %s: %s", resource_id, e)


    def procesar_pago(self, payment_id, desde_orden=False):
        """Procesa un pago individual"""
        try:
            # Verificar si el pago ya fue procesado para evitar duplicados
            # cuando llegan dos webhooks: payment + merchant_order
            from utils.database import pago_ya_procesado

            try:
                if pago_ya_procesado(str(payment_id)):
                    logger.info(
                        "Pago ya fue procesado previamente, ignorando para evitar duplicados",
                        extra={"payment_id": payment_id, "desde_orden": desde_orden},
                    )
                    return {
                        "success": True,
                        "action": "ya_procesado",
                        "payment_id": payment_id,
                        "message": "Pago ya fue procesado en este webhook",
                    }
            except RuntimeError as db_runtime_error:
                logger.warning(
                    "No se pudo verificar pago_ya_procesado por BD no inicializada; se continúa procesamiento",
                    extra={"payment_id": payment_id, "error": str(db_runtime_error)},
                )
            
            # Consultar detalles del pago
            payment_response = self.sdk.payment().get(payment_id)

            if payment_response.get("status") != 200:
                logger.warning(
                    "No se pudo consultar pago en Mercado Pago",
                    extra={"payment_id": payment_id, "desde_orden": desde_orden, "response_status": payment_response.get("status")},
                )
                return self.procesar_error_pago(payment_id, "No se pudo consultar el pago en Mercado Pago")

            raw_payment = payment_response["response"]
            payment = {
                "id": raw_payment["id"],
                "status": raw_payment["status"],
                "status_detail": raw_payment.get("status_detail", ""),
                "monto": raw_payment.get("transaction_amount"),
                "external_reference": raw_payment.get("external_reference", ""),
                "metadata": raw_payment.get("metadata", {}),
                "date_approved": raw_payment.get("date_approved", ""),
                "metodo_pago": raw_payment.get("payment_method", {}).get("id", ""),
            }

            payment_ids = extraer_ids_del_pago(payment)
            if not payment_ids:
                logger.warning("No se pudieron extraer IDs del pago", extra={"payment_id": payment_id, "desde_orden": desde_orden})
                return {
                    "success": False,
                    "action": "id_no_encontrado",
                    "payment_id": payment_id,
                }

            telegram_id, invoice_id = payment_ids
            estado = payment["status"]
            logger.info(
                "Pago identificado para procesamiento",
                extra={
                    "payment_id": payment_id,
                    "telegram_id": telegram_id,
                    "invoice_id": invoice_id,
                    "estado": estado,
                    "desde_orden": desde_orden,
                },
            )

            if estado == 'approved':
                return self.procesar_pago_aprobado(payment)

            if estado == 'rejected':
                return self.procesar_pago_rechazado(payment)

            if estado == 'pending':
                return self.procesar_pago_pendiente(payment)

            logger.info(
                "Pago con estado no critico en procesar_pago",
                extra={"payment_id": payment_id, "estado": estado, "desde_orden": desde_orden},
            )
            return {
                "success": True,
                "action": estado,
                "payment_id": payment_id,
            }

        except Exception as e:
            logger.error("Error procesando pago %s: %s", payment_id, e)
            return self.procesar_error_pago(payment_id, str(e))


    def procesar_notificacion_pago(self, payment_id):
        logger.info("Procesando notificacion de pago", extra={"payment_id": payment_id})
        
        try:
            response = self.obtener_pago(payment_id)  # Solo para loggear el pago completo (opcional)
            
            if response is not None:
                if response["success"] == False:
                    return self.procesar_error_pago(payment_id, f"Error consultando pago: {response['error']}")

                payment = response["pago"]
                estado = payment["status"]
                payment_id = payment["id"]

                # 2. Loggear información básica
                logger.info("Estado de pago recibido", extra={"payment_id": payment_id, "estado": estado, "monto": payment['monto']})
            
                # 3. Procesar según el estado
                if estado == 'approved':
                    return self.procesar_pago_aprobado(payment)
                
                elif estado == 'rejected':
                    return self.procesar_pago_rechazado(payment)
                
                elif estado == 'pending':
                    return self.procesar_pago_pendiente(payment)
                
                else:
                    # Otros estados: in_process, cancelled, refunded, etc.
                    logger.info("Pago con estado no critico", extra={"payment_id": payment_id, "estado": estado})
                    
                    return {
                        "success": True,
                        "action": estado,
                        "payment_id": payment_id
                    }
                
        except Exception as e:
            logger.exception("Excepcion procesando pago %s", payment_id)
            return self.procesar_error_pago(payment_id, str(e))

    # ============================================
    # MÉTODOS DE PROCESAMIENTO DE PAGOS 
    # ============================================
    def procesar_pago_aprobado(self, payment):
        """
        Procesa un pago aprobado
        - Actualiza BD
        - Notifica al usuario
        - Ejecuta lógica de negocio
        """
        monto = payment['monto']
        fecha = payment.get("date_approved", datetime.now().isoformat())
        payment_id = payment["id"]
        payment_ids = extraer_ids_del_pago(payment)
        if not payment_ids:
            return {
                "success": False,
                "action": "aprobado",
                "error": "No se pudieron extraer los IDs del pago.",
            }
        telegram_id, invoice_id = payment_ids
        
        logger.info(
            "Pago aprobado",
            extra={"payment_id": payment_id, "telegram_id": telegram_id, "invoice_id": invoice_id, "monto": monto},
        )
        
        # 1. Actualizar BD
        actualizar_pago(payment_id, invoice_id, 'aprobado', monto, fecha)
        
        # 2. Aquí iría la notificación al usuario por Telegram
        if invoice_id:
            # notificar_usuario_telegram(telegram_id, monto, payment_id)
            logger.debug("Pendiente de notificar pago aprobado", extra={"invoice_id": invoice_id, "telegram_id": telegram_id})
        
        # 3. Aquí iría la lógica de negocio (ej: activar producto, enviar código, etc.)
        # activar_servicio_para_usuario(telegram_id, monto)
        receipt_delivery = self.enviar_comprobante_si_corresponde(invoice_id, payment_id)
        
        return {
            "success": True,
            "action": "aprobado",
            "invoice_id": invoice_id,
            "monto": monto,
            "receipt_sent": receipt_delivery.get("success", False),
            "receipt_message": receipt_delivery.get("message"),
        }

    def enviar_comprobante_si_corresponde(self, invoice_id, payment_id):
        """Genera y envía el comprobante PDF si no fue enviado previamente."""
        if not invoice_id:
            return {"success": False, "message": "Invoice no disponible para enviar comprobante."}

        from shared.services.document_service import build_receipt_pdf_attachment
        from shared.services.email_service import send_email
        from shared.services.document_service import send_receipt_pdf_via_telegram
        from utils.config import Config
        from utils.database import documento_ya_enviado, obtener_comprobante_pedido, registrar_documento_enviado

        logger.info("Iniciando envío de comprobante", extra={"invoice_id": invoice_id, "payment_id": payment_id})

        invoice_info, _ = obtener_comprobante_pedido(invoice_id)
        if not invoice_info:
            return {"success": False, "message": "No se encontraron datos del pedido para el comprobante."}

        recipient_email = invoice_info.get('email') if isinstance(invoice_info, dict) else None
        telegram_chat_id = invoice_info.get('customer_id') if isinstance(invoice_info, dict) else None

        document_type = 'receipt_pdf'
        send_mode = Config.SEND_PDF_MODE if Config.SEND_PDF_MODE in {'EMAIL', 'TELEGRAM', 'BOTH'} else 'EMAIL'

        logger.info(
            "Config de envío de comprobante",
            extra={
                "invoice_id": invoice_id,
                "send_mode": send_mode,
                "recipient_email": recipient_email,
                "telegram_chat_id": telegram_chat_id,
            },
        )

        messages: list[str] = []
        delivery_success = False
        attachment = None
        file_name = None

        def ensure_attachment():
            nonlocal attachment, file_name
            if attachment is None or file_name is None:
                attachment_result, generated_file_name, generation_error = build_receipt_pdf_attachment(invoice_id)
                if not attachment_result or not generated_file_name:
                    return None, None, generation_error or "No se pudo generar el comprobante PDF."
                attachment = attachment_result
                file_name = generated_file_name
            return attachment, file_name, None

        if send_mode in {'EMAIL', 'BOTH'}:
            if recipient_email:
                logger.info("Verificando si comprobante ya fue enviado por email", extra={"invoice_id": invoice_id, "recipient_email": recipient_email})
                if documento_ya_enviado(invoice_id, document_type, 'email', recipient_email):
                    logger.info("Comprobante ya enviado por email, skipping", extra={"invoice_id": invoice_id, "recipient_email": recipient_email})
                    messages.append('Comprobante por email ya enviado previamente.')
                    delivery_success = True
                else:
                    logger.info("Comprobante NO encontrado en BD, procediendo a generar y enviar por email", extra={"invoice_id": invoice_id, "recipient_email": recipient_email})
                    attachment_value, file_name_value, generation_error = ensure_attachment()
                    if not attachment_value or not file_name_value:
                        logger.error("No se pudo generar PDF", extra={"invoice_id": invoice_id, "error": generation_error})
                        messages.append(generation_error or 'No se pudo generar el comprobante PDF.')
                    else:
                        logger.info("Enviando comprobante por email", extra={"invoice_id": invoice_id, "recipient_email": recipient_email, "file_name": file_name_value})
                        email_result = send_email(
                            subject=f"Comprobante de tu pedido #{str(invoice_id).zfill(10)}",
                            body_text=(
                                f"Adjuntamos el comprobante de tu pedido #{str(invoice_id).zfill(10)}.\n\n"
                                "Gracias por tu compra."
                            ),
                            to=[recipient_email],
                            attachments=[attachment_value],
                        )
                        registrar_documento_enviado(
                            invoice_id=invoice_id,
                            document_type=document_type,
                            delivery_channel='email',
                            recipient_target=recipient_email,
                            file_name=file_name_value,
                            payment_id=str(payment_id),
                            status='sent' if email_result.success else 'failed',
                            error_message=None if email_result.success else email_result.error_message,
                        )
                        if email_result.success:
                            logger.info("Comprobante enviado exitosamente por email y registrado en BD", extra={"invoice_id": invoice_id, "recipient_email": recipient_email})
                            messages.append('Comprobante enviado por email.')
                            delivery_success = True
                        else:
                            logger.error("Error al enviar comprobante por email", extra={"invoice_id": invoice_id, "recipient_email": recipient_email, "error": email_result.error_message})
                            messages.append(email_result.error_message or 'No se pudo enviar el comprobante por email.')
            else:
                logger.warning("Cliente no tiene email", extra={"invoice_id": invoice_id})
                messages.append('El cliente no tiene email para enviar el comprobante.')

        if send_mode in {'TELEGRAM', 'BOTH'}:
            if telegram_chat_id:
                telegram_target = str(telegram_chat_id)
                logger.info("Verificando si comprobante ya fue enviado por Telegram", extra={"invoice_id": invoice_id, "telegram_chat_id": telegram_target})
                if documento_ya_enviado(invoice_id, document_type, 'telegram', telegram_target):
                    logger.info("Comprobante ya enviado por Telegram, skipping", extra={"invoice_id": invoice_id, "telegram_chat_id": telegram_target})
                    messages.append('Comprobante por Telegram ya enviado previamente.')
                    delivery_success = True
                else:
                    logger.info("Comprobante NO encontrado en BD, procediendo a generar y enviar por Telegram", extra={"invoice_id": invoice_id, "telegram_chat_id": telegram_target})
                    attachment_value, file_name_value, generation_error = ensure_attachment()
                    if not attachment_value or not file_name_value:
                        logger.error("No se pudo generar PDF", extra={"invoice_id": invoice_id, "error": generation_error})
                        messages.append(generation_error or 'No se pudo generar el comprobante PDF.')
                    else:
                        logger.info("Enviando comprobante por Telegram", extra={"invoice_id": invoice_id, "telegram_chat_id": telegram_target, "file_name": file_name_value})
                        telegram_ok, telegram_error = send_receipt_pdf_via_telegram(
                            telegram_chat_id,
                            attachment_value,
                            caption=f"Comprobante de tu pedido #{str(invoice_id).zfill(10)}",
                        )
                        registrar_documento_enviado(
                            invoice_id=invoice_id,
                            document_type=document_type,
                            delivery_channel='telegram',
                            recipient_target=telegram_target,
                            file_name=file_name_value,
                            payment_id=str(payment_id),
                            status='sent' if telegram_ok else 'failed',
                            error_message=None if telegram_ok else telegram_error,
                        )
                        if telegram_ok:
                            logger.info("Comprobante enviado exitosamente por Telegram y registrado en BD", extra={"invoice_id": invoice_id, "telegram_chat_id": telegram_target})
                            messages.append('Comprobante enviado por Telegram.')
                            delivery_success = True
                        else:
                            logger.error("Error al enviar comprobante por Telegram", extra={"invoice_id": invoice_id, "telegram_chat_id": telegram_target, "error": telegram_error})
                            messages.append(telegram_error or 'No se pudo enviar el comprobante por Telegram.')
            else:
                logger.warning("Cliente no tiene telegram_chat_id", extra={"invoice_id": invoice_id})
                messages.append('El cliente no tiene chat_id para enviar el comprobante por Telegram.')

        if not messages:
            messages.append('No hay canales configurados para el envío del comprobante.')

        return {"success": delivery_success, "message": " ".join(messages)}

    def procesar_pago_rechazado(self, payment):
        """Procesa un pago rechazado"""
        monto = payment['monto']
        status_detail = payment.get("status_detail", "")
        payment_id = payment["id"]
        payment_ids = extraer_ids_del_pago(payment)
        if not payment_ids:
            return {
                "success": False,
                "action": "rechazado",
                "motivo": "No se pudieron extraer los IDs del pago.",
            }
        telegram_id, invoice_id = payment_ids
        
        logger.warning(
            "Pago rechazado",
            extra={"payment_id": payment_id, "telegram_id": telegram_id, "invoice_id": invoice_id, "status_detail": status_detail},
        )
        
        # 1. Actualizar BD
        actualizar_pago(payment_id, invoice_id, 'rechazado', monto)
        
        # 2. Notificar al usuario (opcional)
        if invoice_id:
            logger.debug("Pendiente de notificar pago rechazado", extra={"invoice_id": invoice_id, "telegram_id": telegram_id})
        
        return {
            "success": False,
            "action": "rechazado",
            "invoice_id": invoice_id,
            "motivo": status_detail
        }

    def procesar_pago_pendiente(self, payment):
        """Procesa un pago pendiente"""
        monto = payment['monto']
        payment_id = payment["id"]
        payment_ids = extraer_ids_del_pago(payment)
        if not payment_ids:
            return {
                "success": False,
                "action": "pendiente",
                "error": "No se pudieron extraer los IDs del pago.",
            }
        telegram_id, invoice_id = payment_ids
        
        logger.info(
            "Pago pendiente",
            extra={"payment_id": payment_id, "telegram_id": telegram_id, "invoice_id": invoice_id},
        )
        
        # 1. Actualizar BD
        actualizar_pago(payment_id, invoice_id, 'pendiente', monto)
        
        return {
            "success": True,
            "action": "pendiente",
            "invoice_id": invoice_id
        }

    def procesar_error_pago(self, payment_id, error_msg):
        """Procesa un error al consultar el pago"""
        logger.error("Error consultando pago %s: %s", payment_id, error_msg)
        
        # Podrías guardar el error en una tabla de errores
        # guardar_error(payment_id, error_msg)
        
        return {
            "success": False,
            "action": "error",
            "error": error_msg
        }



def extraer_ids_del_pago(payment) -> tuple[str, str] | None:
    """Extrae `telegram_id` e `invoice_id` desde un objeto de pago.

    Busca primero en `metadata` (campos `telegram_id` e `invoice_id`),
    y en caso de no existir intenta parsear `external_reference`.
    Devuelve una tupla `(telegram_id, invoice_id)` o `None` si no se encuentran.
    """
    metadata = payment.get("metadata", {})
    external_ref = payment.get("external_reference", "")

    # external_reference tiene este formato ahora:
    # f"telegram_{telegram_id}_{invoice_id}_{monto}"
    # Intentar desde metadata primero
    if metadata and metadata.get("invoice_id") and metadata.get("telegram_id"):
        return metadata["telegram_id"], metadata["invoice_id"]

    # Fallback: desde external_reference (formato: "telegram_123456_500")
    if external_ref and external_ref.startswith("telegram_"):
        parts = external_ref.split('_')
        if len(parts) >= 3:
            return (parts[1], parts[2])  # telegram_id, invoice_id

    return None


def verificar_firma(request, payment_id):
    """Verifica la firma de MercadoPago para un payment_id específico"""
    MERCADOPAGO_WEBHOOK_SECRET = os.getenv('MERCADOPAGO_WEBHOOK_SECRET')
    logger.info("Verificando firma de Mercado Pago", extra={"payment_id": payment_id})

    try:
        if not MERCADOPAGO_WEBHOOK_SECRET:
            logger.error("Secreto de webhook de Mercado Pago no configurado")
            return False

        # 1. Obtener headers
        x_signature = request.headers.get('x-signature')
        x_request_id = request.headers.get('x-request-id')

        if not x_signature or not x_request_id:
            logger.warning("Headers de firma faltantes en webhook de Mercado Pago", extra={"payment_id": payment_id})
            return False

        # 2. Parsear la firma
        signature_parts = {}
        for part in x_signature.split(','):
            if '=' in part:
                key, value = part.split('=', 1)
                signature_parts[key.strip()] = value.strip()

        ts = signature_parts.get('ts')
        received_hash = signature_parts.get('v1')

        if not ts or not received_hash:
            logger.warning("Firma mal formada en webhook de Mercado Pago", extra={"payment_id": payment_id})
            return False

        # 3. Generar manifiesto
        template = f"id:{payment_id};request-id:{x_request_id};ts:{ts};"

        # 4. Calcular firma local
        calculated_hash = hmac.new(
            MERCADOPAGO_WEBHOOK_SECRET.encode('utf-8'),
            template.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # 5. Comparar
        result = hmac.compare_digest(received_hash, calculated_hash)
        logger.info("Resultado de verificacion de firma", extra={"payment_id": payment_id, "resultado": result})
        return result

    except Exception as e:
        logger.exception("Error verificando firma de Mercado Pago para payment_id %s", payment_id)
        return False
    
    

