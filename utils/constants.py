from enum import Enum, auto

class EstadoConversacion(Enum):
    # Registro de usuario
    ESPERANDO_EMAIL = auto()
    ESPERANDO_CODIGO = auto()

    # Compra
    ESPERANDO_CATEGORIA = auto()
    ESPERANDO_PRODUCTO = auto()

    # Modificación del carrito
    MODIFICANDO_CARRITO = auto()


    