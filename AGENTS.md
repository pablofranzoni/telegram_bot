# AGENTS.md - Bot de Telegram con Webhook y Flask

## Resumen del Proyecto

Este proyecto consiste en el desarrollo de un bot de Telegram utilizando la biblioteca 
`python-telegram-bot` (PTB) en su versión 20.x, operando bajo la modalidad de **webhook** en lugar de polling. El bot estará integrado en una aplicación Flask que servirá tanto para recibir las actualizaciones de Telegram como para exponer una API REST adicional.

### Funcionalidades Principales:

1.  **Bot de Telegram:**
    - Manejo de comandos (ej. `/start`, `/ayuda`, `/productos`).
    - Manejo de mensajes de texto y posibles interacciones con botones (InlineKeyboards).
    - Envío de notificaciones proactivas a los usuarios.

2.  **API de Gestión (Endpoints Adicionales):**
    - Se implementarán endpoints RESTful para la administración de los recursos del negocio.
    - **Clientes:** Creación, consulta, actualización y eliminación (CRUD) de clientes/usuarios del bot.
    - **Productos:** Gestión del catálogo de productos.
    - **Categorías:** Organización de los productos por categorías.
    - **Pedidos:** Creación (desde el bot o el panel), consulta y actualización del estado de pedidos.
    - **Pagos:** Registro y confirmación de pagos, posiblemente integrando un webhook de pasarela de pago.

3.  **Arquitectura:**
    - **Flask:** Actúa como servidor web principal.
    - **python-telegram-bot:** Gestiona la lógica del bot y se integra con Flask a través de su clase `Application`.
    - **Webhook:** Telegram enviará las actualizaciones a un endpoint específico (ej. `/webhook`), que será procesado por la aplicación de PTB.

## Comandos de Compilación y Prueba

El proyecto utiliza `pip` para la gestión de dependencias y `pytest` para las pruebas.

### Configuración del Entorno

1.  **Clonar el repositorio:**
    ```bash
    git clone <url-del-repositorio>
    cd nombre-del-proyecto
	
2.  **Crear y activar un entorno virtual (recomendado):**
	bash 
	python -m venv venv
	source venv/bin/activate  # En Windows: venv\Scripts\activate
	
3.  **Instalar dependencias**
	bash
	pip install -r requirements.txt
	
4.  **Variables de entorno**
	Crear un archivo .env en la raíz del proyecto (basado en .env.example) con las siguientes variables:
	BOT_TOKEN=<tu_token_de_bot>
	WEBHOOK_URL=https://suffocatingly-resedaceous-mia.ngrok-free.dev/webhook
	FLASK_APP=bot_pa.py
	FLASK_ENV=development  # Solo para desarrollo
	DATABASE_URL=<tu_url_de_base_de_datos>  # Ej: sqlite:///db.sqlite3
	SECRET_KEY=<una_clave_secreta_para_flask>
	
## Ejecución del Proyecto
	**Desarrollo Local (con ngrok para webhook)**
	1.	Iniciar la aplicación Flask:
		python bot_pa.py
		
	2.	Exponer el servidor local con ngrok:
		ngrok http 5000
		
	3.  Configurar el Webhook en Telegram:
		curl -F "url=<tu_url_ngrok>/webhook" https://api.telegram.org/bot<TU_TOKEN>/setWebhook
	
	**Producción**
	1.	gunicorn --workers 4 --bind 0.0.0.0:8000 "app:create_app()"
	
	2.  Configurar el Webhook en Telegram:
		curl -F "url=<tu_url_ngrok>/webhook" https://api.telegram.org/bot<TU_TOKEN>/setWebhook

##Pruebas y Estilo de Código
	**Ejecutar todas las pruebas:**
	pytest -v
	
	**Ejecutar pruebas con cobertura:**
	pytest --cov=. --cov-report=term-missing
	
	**Formatear código con Black:**
	black .
	
	**Ordenar imports con isort:**
	isort .
	
	**Verificar estilo con Flake8:**
	flake8
	
	**Verificar tipos con mypy:**
	mypy .
	
	##El proyecto sigue las convenciones establecidas en la comunidad Python y las mejores prácticas para proyectos mantenibles.

	##Formato:

	-Black: Se utiliza para un formateo consistente. La línea máxima de código es 88 (por defecto de Black).

	-isort: Para ordenar las importaciones, configurado para ser compatible con Black (perfil "black").

	##Linting y Tipado:

	Flake8: Para el linting del código, asegurando que se sigan las convenciones de PEP 8.

	mypy: Se utiliza tipado estático. Todas las funciones y métodos deben tener type hints para sus argumentos y valores de retorno.

	##Convenciones de Nomenclatura:

	-snake_case para variables, funciones y métodos.

	-CamelCase para clases.

	-UPPER_CASE para constantes.

	-Los nombres deben ser descriptivos y en inglés (o español, definiendo un estándar claro para todo el proyecto).

	##Estructura del Proyecto:

	-La lógica del bot debe estar modularizada (ej. handlers/, services/).

	-Los endpoints de la API REST deben estar en un blueprint de Flask separado (ej. api/).

	-La configuración debe centralizarse (ej. config.py).

	##Documentación:

	-Se debe incluir docstrings en todas las funciones, clases y módulos utilizando el formato Google (o el estándar que se defina).

	-El código complejo debe incluir comentarios explicativos.

	##Instrucciones de Prueba
	
	-Framework de Pruebas: pytest.

	-Estructura: Los archivos de prueba deben residir en el directorio tests/, reflejando la estructura del proyecto (ej. tests/test_handlers.py, tests/api/test_clientes.py).

	-Cobertura: Se espera una alta cobertura de código (mínimo >80%).

	##Tests de Bot:

	-Utilizar pytest.mark.asyncio para probar funciones asíncronas (handlers).

	-Aprovechar los helpers de python-telegram-bot como Update y ContextTypes.DEFAULT_TYPE para simular actualizaciones.

	-Probar la respuesta a comandos y mensajes específicos, así como la navegación por menús inline.

	##Tests de API:

	-Usar el cliente de prueba de Flask (app.test_client()).

	-Probar los endpoints CRUD para cada recurso, verificando códigos de estado HTTP, estructura de la respuesta (JSON) y validación de datos.

	##Tests de Integración:

	-Configurar una base de datos en memoria (ej. SQLite) para pruebas que requieran interacción con la BD.

	-Probar flujos completos que involucren tanto al bot como a la API (ej. un pedido creado desde el bot que debe ser consultable por la API).

	##Consideraciones de Seguridad
	
	-La seguridad es un aspecto fundamental en el desarrollo de este bot y su API.

	##Verificación del Webhook:

	-El endpoint /webhook debe ser público, pero es crucial verificar que las solicitudes entrantes provienen realmente de los servidores de Telegram.

	-Utilizar la función de verificación incorporada en python-telegram-bot que valida las peticiones.

	-Configurar un secret_token al establecer el webhook y verificar el header X-Telegram-Bot-Api-Secret-Token.

	##Protección de Endpoints de la API:

	-Los endpoints de gestión (/api/clientes, /api/pedidos, etc.) no deben ser públicos.

	##Implementar un mecanismo de autenticación robusto, como:

	-API Keys: Claves secretas que deben ser enviadas en el header Authorization de cada solicitud.

	-JWT (JSON Web Tokens): Para autenticación basada en sesiones de usuario.

	-Implementar control de acceso basado en roles (RBAC) si es necesario.

	-Validación y Sanitización de Entradas:

	-Validar rigurosamente todos los datos de entrada, tanto en los handlers del bot como en los endpoints de la API.

	-Utilizar librerías como pydantic o marshmallow para la definición y validación de esquemas de datos.

	-Sanitizar cualquier entrada de usuario para prevenir inyección de código (SQL, NoSQL, etc.).

	##Manejo Seguro de Secretos:

	-NUNCA hardcodear tokens, contraseñas o claves en el código fuente.

	-Todas las credenciales deben inyectarse a través de variables de entorno (.env en desarrollo, secretos del orquestador en producción).

	-HTTPS Obligatorio:

	-Tanto el webhook de Telegram como la comunicación con la API de gestión deben realizarse exclusivamente a través de HTTPS.

	-En producción, configurar correctamente el certificado SSL en el servidor web o proxy inverso.

	##Control de Acceso y Logging:

	-Implementar un logging seguro que no registre información sensible (tokens, contraseñas, datos personales de clientes).

	-Almacenar logs de acceso a la API con fines de auditoría, sin exponer datos críticos.

	-Configurar niveles de log apropiados para producción (INFO o WARNING, nunca DEBUG).

	##Protección contra Ataques Comunes:

	-Implementar rate limiting en los endpoints de la API para prevenir abusos y ataques de fuerza bruta.

	-Configurar cabeceras de seguridad en Flask (ej. con Flask-Talisman) para mitigar ataques como XSS, clickjacking.

	-Mantener todas las dependencias actualizadas para evitar vulnerabilidades conocidas.

	##Base de Datos:

	-Utilizar consultas parametrizadas (o un ORM que lo haga automáticamente) para prevenir inyecciones SQL.

	-Almacenar contraseñas de usuarios utilizando algoritmos de hash seguros y con salt (ej. bcrypt).

	-Cifrar datos especialmente sensibles en la base de datos si es necesario.

	##Respuestas del Bot al usuario
	-Utilizar la clase TelegramTable cuando sea el resultado de opciones (categorias o productos) (enviando los parametros adecuados a la factory como en el ejemplo)

	-Paginar los resultados si superan los 10 registros
		