from enum import Enum, auto

class EstadoConversacion(Enum):
    # Registro de usuario
    ESPERANDO_EMAIL = auto()
    ESPERANDO_CODIGO = auto()
    
    #ESPERANDO_DIRECCION = auto()
    #ESPERANDO_TELEFONO = auto()
    
    # Compra
    ESPERANDO_CATEGORIA = auto()
    ESPERANDO_PRODUCTO = auto()
    #ESPERANDO_CANTIDAD = auto()
    
    # Checkout
    #CONFIRMAR_PEDIDO = auto()


    