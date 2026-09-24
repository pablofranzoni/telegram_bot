"""Business logic for authentication and customer onboarding."""

import random
import re
import string

from utils.database import guardar_cliente, obtener_cliente


def is_valid_email(email: str) -> bool:
    """Validate the email format accepted by the bot."""
    if not email or len(email) > 100:
        return False

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


def generate_verification_code() -> str:
    """Generate a six-digit verification code."""
    return "".join(random.choices(string.digits, k=6))


def get_customer_with_email(telegram_id: int):
    """Return the customer record only when it has a valid email."""
    customer = obtener_cliente(telegram_id)
    if customer and customer.get("email"):
        return customer
    return None


def register_verified_customer(
    telegram_id: int,
    first_name: str | None,
    last_name: str | None,
    username: str | None,
    email: str,
) -> None:
    """Persist a verified customer into the database."""
    guardar_cliente(
        telegram_id,
        first_name,
        last_name,
        username,
        email=email,
    )