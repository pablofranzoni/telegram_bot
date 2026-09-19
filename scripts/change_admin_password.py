#!/usr/bin/env python3
"""
Script para cambiar la contraseña de un usuario administrador de la API.

Modos de uso:

1) Cambio normal (conoce la contraseña actual):
     python scripts/change_admin_password.py

2) Reset con token (no requiere contraseña anterior):
     python scripts/change_admin_password.py --reset-token <TOKEN>

3) Solicitar token de reset por email (devuelve `_token_dev` en desarrollo):
     python scripts/change_admin_password.py --request-reset-for admin@ejemplo.com

Endpoints consumidos:
  - POST /api/auth/login                (modo normal)
  - POST /api/change-password           (modo normal)
  - POST /api/password-reset            (solicitar token)
  - POST /api/password-reset/<token>    (confirmar reset)

Las contraseñas se piden por teclado de forma oculta (getpass) a menos que
se pasen mediante variables de entorno:
    ADMIN_USERNAME, OLD_PASSWORD, NEW_PASSWORD

Requiere:
    pip install requests python-dotenv
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


DEFAULT_API_BASE_URL = "http://localhost:5000"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cambia la contraseña de un administrador de la API."
    )

    parser.add_argument(
        "--username",
        default=os.getenv("ADMIN_USERNAME"),
        help="Nombre de usuario del admin (también ADMIN_USERNAME).",
    )
    parser.add_argument(
        "--old-password",
        default=os.getenv("OLD_PASSWORD"),
        help="Contraseña actual (se recomienda usar variable OLD_PASSWORD).",
    )
    parser.add_argument(
        "--new-password",
        default=os.getenv("NEW_PASSWORD"),
        help="Nueva contraseña (se recomienda usar variable NEW_PASSWORD).",
    )
    parser.add_argument(
        "--reset-token",
        default=os.getenv("RESET_TOKEN"),
        help="Token de reset de contraseña. Si se indica, no se requiere contraseña anterior.",
    )
    parser.add_argument(
        "--request-reset-for",
        dest="request_reset_email",
        default=os.getenv("REQUEST_RESET_EMAIL"),
        help="Solicitar un token de reset para este email (modo sin contraseña anterior).",
    )
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("API_BASE_URL", DEFAULT_API_BASE_URL),
        help=f"URL base de la API (default: {DEFAULT_API_BASE_URL}).",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Archivo .env a cargar (default: .env).",
    )
    parser.add_argument(
        "--skip-verify-ssl",
        action="store_true",
        help="Deshabilitar verificación SSL (solo para desarrollo local).",
    )
    return parser.parse_args()


def load_env_file(env_file: str) -> None:
    env_path = Path(env_file)
    if env_path.exists():
        load_dotenv(env_path)
    elif env_file != ".env":
        print(f"[AVISO] No se encontró el archivo de entorno: {env_file}")


def get_input(prompt: str, default: str | None) -> str:
    if default:
        return default
    value = input(f"{prompt}: ").strip()
    if not value:
        print("[ERROR] Este campo es obligatorio.")
        sys.exit(1)
    return value


def get_password_input(prompt: str, default: str | None) -> str:
    if default:
        return default
    value = getpass.getpass(f"{prompt}: ")
    if not value:
        print("[ERROR] La contraseña no puede estar vacía.")
        sys.exit(1)
    return value


def get_new_password_pair(new_default: str | None = None) -> tuple[str, str]:
    """Pide y confirma la nueva contraseña."""
    new_password = get_password_input("Nueva contraseña", new_default)
    confirm_password = get_password_input("Confirmar nueva contraseña", None)
    if new_password != confirm_password:
        print("[ERROR] Las nuevas contraseñas no coinciden.")
        sys.exit(1)
    return new_password, confirm_password


def _print_response(response: requests.Response) -> None:
    try:
        body = response.json()
        message = body.get("message", body)
        error_code = body.get("error_code")
        print(f"        Mensaje: {message}")
        if error_code:
            print(f"        Código de error: {error_code}")
    except ValueError:
        print(f"        Respuesta: {response.text}")


def login(base_url: str, username: str, password: str, verify_ssl: bool) -> str:
    url = f"{base_url}/api/auth/login"
    payload = {"username": username, "password": password}

    try:
        response = requests.post(url, json=payload, verify=verify_ssl, timeout=30)
    except requests.exceptions.RequestException as exc:
        print(f"[ERROR] No se pudo conectar con {url}: {exc}")
        sys.exit(1)

    if response.status_code != 200:
        print(f"[ERROR] Login fallido (HTTP {response.status_code}).")
        _print_response(response)
        sys.exit(1)

    data = response.json()
    if data.get("status") != "success":
        print("[ERROR] Login fallido:")
        _print_response(response)
        sys.exit(1)

    access_token = data.get("data", {}).get("access_token")
    if not access_token:
        print("[ERROR] La respuesta de login no incluyó access_token.")
        sys.exit(1)

    return access_token


def change_password(
    base_url: str,
    access_token: str,
    old_password: str,
    new_password: str,
    verify_ssl: bool,
) -> None:
    url = f"{base_url}/api/change-password"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {"old_password": old_password, "new_password": new_password}

    try:
        response = requests.post(
            url, headers=headers, json=payload, verify=verify_ssl, timeout=30
        )
    except requests.exceptions.RequestException as exc:
        print(f"[ERROR] No se pudo conectar con {url}: {exc}")
        sys.exit(1)

    if response.status_code == 200:
        print("[OK] Contraseña cambiada exitosamente.")
        return

    print(f"[ERROR] No se pudo cambiar la contraseña (HTTP {response.status_code}).")
    _print_response(response)
    sys.exit(1)


def request_password_reset(base_url: str, email: str, verify_ssl: bool) -> dict:
    url = f"{base_url}/api/password-reset"
    payload = {"email": email}

    try:
        response = requests.post(url, json=payload, verify=verify_ssl, timeout=30)
    except requests.exceptions.RequestException as exc:
        print(f"[ERROR] No se pudo conectar con {url}: {exc}")
        sys.exit(1)

    try:
        data = response.json()
    except ValueError:
        data = {}

    if response.status_code != 200 or data.get("status") != "success":
        print(f"[ERROR] No se pudo solicitar el reset (HTTP {response.status_code}).")
        _print_response(response)
        sys.exit(1)

    return data


def confirm_password_reset(
    base_url: str, reset_token: str, new_password: str, verify_ssl: bool
) -> None:
    url = f"{base_url}/api/password-reset/{reset_token}"
    payload = {"new_password": new_password}

    try:
        response = requests.post(url, json=payload, verify=verify_ssl, timeout=30)
    except requests.exceptions.RequestException as exc:
        print(f"[ERROR] No se pudo conectar con {url}: {exc}")
        sys.exit(1)

    if response.status_code == 200:
        print("[OK] Contraseña restablecida exitosamente.")
        return

    print(
        f"[ERROR] No se pudo restablecer la contraseña (HTTP {response.status_code})."
    )
    _print_response(response)
    sys.exit(1)


def normal_change_flow(args: argparse.Namespace, base_url: str, verify_ssl: bool) -> None:
    username = get_input("Usuario", args.username)
    old_password = get_password_input("Contraseña actual", args.old_password)
    new_password, _ = get_new_password_pair(args.new_password)

    print(f"\n[INFO] Conectando a {base_url} ...")

    access_token = login(base_url, username, old_password, verify_ssl)
    change_password(base_url, access_token, old_password, new_password, verify_ssl)


def reset_with_token_flow(
    args: argparse.Namespace, base_url: str, reset_token: str, verify_ssl: bool
) -> None:
    new_password, _ = get_new_password_pair(args.new_password)

    print(f"\n[INFO] Restableciendo contraseña en {base_url} ...")
    confirm_password_reset(base_url, reset_token, new_password, verify_ssl)


def request_reset_flow(
    args: argparse.Namespace, base_url: str, email: str, verify_ssl: bool
) -> None:
    print(f"\n[INFO] Solicitando token de reset en {base_url} para {email} ...")
    data = request_password_reset(base_url, email, verify_ssl)
    print(f"[OK] {data.get('message', 'Solicitud procesada.')}")

    dev_token = data.get("_token_dev")
    if not dev_token:
        print(
            "[INFO] El token no fue devuelto en la respuesta; "
            "debería haberse enviado por email. "
            "Vuelva a ejecutar el script con --reset-token <TOKEN>."
        )
        return

    print(f"\n[INFO] Token de desarrollo: {dev_token}")
    answer = input("¿Desea establecer la nueva contraseña ahora con este token? (s/N): ").strip().lower()
    if answer in ("s", "si", "y", "yes"):
        new_password, _ = get_new_password_pair(args.new_password)
        confirm_password_reset(base_url, dev_token, new_password, verify_ssl)
    else:
        print(
            "[INFO] Guarde el token y ejecute:\n"
            f"  python scripts/change_admin_password.py --reset-token {dev_token}"
        )


def main() -> None:
    args = parse_args()

    # Cargar variables de entorno primero (pueden ser necesarias para la URL).
    load_env_file(args.env_file)

    # Volver a leer la URL base por si estaba en el .env.
    base_url = os.getenv("API_BASE_URL", args.api_base_url).rstrip("/")
    verify_ssl = not args.skip_verify_ssl

    if args.reset_token and args.request_reset_email:
        print("[ERROR] --reset-token y --request-reset-for son mutuamente excluyentes.")
        sys.exit(1)

    if args.reset_token:
        reset_with_token_flow(args, base_url, args.reset_token, verify_ssl)
    elif args.request_reset_email:
        request_reset_flow(args, base_url, args.request_reset_email, verify_ssl)
    else:
        normal_change_flow(args, base_url, verify_ssl)


if __name__ == "__main__":
    main()
