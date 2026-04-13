"""Fachada de handlers agrupados por funcionalidad.

Este módulo reexporta los handlers principales para que el resto de la
aplicación pueda seguir importando desde `shared.handlers.commands`.
"""

from .auth import (
    es_email_valido,
    cmd_inicio_cliente,
    start,
    ver_ayuda,
    generar_codigo_verificacion,
    recibir_email,
    verificar_codigo,
    cancelar_ingreso_email,
    reply_markup_principal,
    mostrar_menu_principal,
    reiniciar_desde_fallback,
)

from .products import (
    obtener_categorias,
    seleccionar_categoria,
    mostrar_productos_categoria_texto,
    mostrar_productos_categoria,
    seleccionar_producto,
    cancelar_opcion_producto,
)

from .cart import (
    manejar_botones_carrito,
    ver_pedido,
    finalizar_pedido,
    disminuir_cantidad,
    aumentar_cantidad,
    agregar_producto_al_pedido,
    vaciar_pedido,
    eliminar_producto,
    mostrar_confirmacion_eliminar,
    mostrar_confirmacion_finalizar_carrito,
    ejecutar_eliminacion,
    ejecutar_finalizar_pedido,
    actualizar_vista_pedido,
    manejar_confirmacion_finalizar_pedido,
    manejar_confirmacion_eliminar,
    mensajes_texto,
    error_handler
)

from .payments import cmd_estado_pago


__all__ = [
    "es_email_valido",
    "cmd_inicio_cliente",
    "start",
    "ver_ayuda",
    "generar_codigo_verificacion",
    "recibir_email",
    "verificar_codigo",
    "cancelar_ingreso_email",
    "reply_markup_principal",
    "mostrar_menu_principal",
    "reiniciar_desde_fallback",
    "obtener_categorias",
    "seleccionar_categoria",
    "mostrar_productos_categoria_texto",
    "mostrar_productos_categoria",
    "seleccionar_producto",
    "cancelar_opcion_producto",
    "manejar_botones_carrito",
    "ver_pedido",
    "finalizar_pedido",
    "disminuir_cantidad",
    "aumentar_cantidad",
    "agregar_producto_al_pedido",
    "vaciar_pedido",
    "eliminar_producto",
    "mostrar_confirmacion_eliminar",
    "mostrar_confirmacion_finalizar_carrito",
    "ejecutar_eliminacion",
    "ejecutar_finalizar_pedido",
    "actualizar_vista_pedido",
    "manejar_confirmacion_finalizar_pedido",
    "manejar_confirmacion_eliminar",
    "mensajes_texto",
    "cmd_estado_pago",
    "error_handler"
]
