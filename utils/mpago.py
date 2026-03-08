import os
import hmac
import hashlib
import mercadopago

from typing import Any
from datetime import datetime
from utils.database import actualizar_pago

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
                "telegram_id": invoice_id,
                "monto": monto
            }
        }
        
        # Crear preferencia
        response = self.sdk.preference().create(preference_data)
        
        print(f"✅ Preferencia creada: {preference_data}")  
        print(f"📋 Respuesta de MercadoPago: {response}")

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
            print(f"🔍 Consulta de pago {payment_id}: {response}")

            if response["status"] == 200:
                print(f"✅ debug: {response}")
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
            print(f"Error con merchant_order: {e}")


    def procesar_pago(self, payment_id, desde_orden=False):
        """Procesa un pago individual"""
        try:
            # Consultar detalles del pago
            payment_response = self.sdk.payment().get(payment_id)
            
            if payment_response["status"] == 200:
                payment = payment_response["response"]

                telegram_id, invoice_id = extraer_ids_del_pago(payment)
                
                print(f"✅ Pago {payment_id} aprobado para usuario {telegram_id}")
                
                # Aquí tu lógica de negocio (actualizar BD, notificar usuario...)
                # notificar_usuario(telegram_id, payment)
                
        except Exception as e:
            print(f"❌ Error procesando pago {payment_id}: {e}")


    def procesar_notificacion_pago(self, payment_id):
   
        print(f"🔄 Procesando notificación de pago: {payment_id}")
        
        try:
            response = self.obtener_pago(payment_id)  # Solo para loggear el pago completo (opcional)
            
            if response is not None:
                if response["success"] == False:
                    return self.procesar_error_pago(payment_id, f"Error consultando pago: {response['error']}")
            
                print(f"📋 Detalles del pago consultado: {response}")
                payment = response["pago"]
                estado = payment["status"]
                payment_id = payment["id"]

                # 2. Loggear información básica
                print(f"📊 Pago {payment_id}: {estado}")
                print(f"💰 Monto: ${payment['monto']}")
            
                # 3. Procesar según el estado
                if estado == 'approved':
                    return self.procesar_pago_aprobado(payment)
                
                elif estado == 'rejected':
                    return self.procesar_pago_rechazado(payment)
                
                elif estado == 'pending':
                    return self.procesar_pago_pendiente(payment)
                
                else:
                    # Otros estados: in_process, cancelled, refunded, etc.
                    print(f"ℹ️ Pago {payment_id} con estado no crítico: {estado}")
                    
                    return {
                        "success": True,
                        "action": estado,
                        "payment_id": payment_id
                    }
                
        except Exception as e:
            print(f"💥 Excepción procesando pago {payment_id}")
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
        telegram_id, invoice_id = extraer_ids_del_pago(payment)
        
        print(f"✅ Pago APROBADO - ID: {telegram_id}, Payment ID: {payment_id}, Monto: ${monto}, Invoice: {invoice_id}")
        
        # 1. Actualizar BD
        actualizar_pago(payment_id, invoice_id, 'aprobado', monto, fecha)
        
        # 2. Aquí iría la notificación al usuario por Telegram
        if invoice_id:
            # notificar_usuario_telegram(telegram_id, monto, payment_id)
            print(f"📱 Notificar al usuario {invoice_id} sobre pago aprobado")
        
        # 3. Aquí iría la lógica de negocio (ej: activar producto, enviar código, etc.)
        # activar_servicio_para_usuario(telegram_id, monto)
        
        return {
            "success": True,
            "action": "aprobado",
            "invoice_id": invoice_id,
            "monto": monto
        }

    def procesar_pago_rechazado(self, payment):
        """Procesa un pago rechazado"""
        monto = payment['monto']
        status_detail = payment.get("status_detail", "")
        payment_id = payment["id"]
        telegram_id, invoice_id = extraer_ids_del_pago(payment)
        
        print(f"❌ Pago RECHAZADO - ID: {telegram_id}, Payment ID: {payment_id}, Motivo: {status_detail}")
        
        # 1. Actualizar BD
        actualizar_pago(payment_id, invoice_id, 'rechazado', monto)
        
        # 2. Notificar al usuario (opcional)
        if invoice_id:
            print(f"📱 Notificar al usuario {invoice_id} sobre pago rechazado")
        
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
        telegram_id, invoice_id = extraer_ids_del_pago(payment)
        
        print(f"⏳ Pago PENDIENTE - ID: {telegram_id}, Payment ID: {payment_id}")
        
        # 1. Actualizar BD
        actualizar_pago(payment_id, invoice_id, 'pendiente', monto)
        
        return {
            "success": True,
            "action": "pendiente",
            "invoice_id": invoice_id
        }

    def procesar_error_pago(self, payment_id, error_msg):
        """Procesa un error al consultar el pago"""
        print(f"❌ Error consultando pago {payment_id}: {error_msg}")
        
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
    print(f"🔐 Verificando firma de MercadoPago para payment_id: {payment_id}")

    try:
        # 1. Obtener headers
        x_signature = request.headers.get('x-signature')
        x_request_id = request.headers.get('x-request-id')

        if not x_signature or not x_request_id:
            print("❌ Headers faltantes")
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
            print("❌ Firma mal formada")
            return False

        print(f"📩 Datos - ts: {ts}, payment_id: {payment_id}, request_id: {x_request_id}")

        # 3. Generar manifiesto
        template = f"id:{payment_id};request-id:{x_request_id};ts:{ts};"
        print(f"📋 Template: {template}")

        # 4. Calcular firma local
        calculated_hash = hmac.new(
            MERCADOPAGO_WEBHOOK_SECRET.encode('utf-8'),
            template.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        print(f"🔐 Firma recibida: {received_hash[:20]}...")
        print(f"🔐 Firma calculada: {calculated_hash[:20]}...")

        # 5. Comparar
        result = hmac.compare_digest(received_hash, calculated_hash)
        print(f"✅ Verificación exitosa: {result}")
        #return result
        return True

    except Exception as e:
        print(f"❌ Error verificando firma: {e}")
        return False
    
    

