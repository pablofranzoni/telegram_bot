#!/usr/bin/env python3
"""
Script to create the first superadmin for the API.

This script:
1. Validates database connection
2. Validates that no admin exists yet
3. Prompts for username, email, password
4. Creates the API user with is_admin=1
5. Generates and displays verification code
6. Prompts to verify email code
7. Marks email as verified

Usage:
    py create_first_admin.py
"""

import os
import sys
import getpass
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def print_header(title: str) -> None:
    """Print a formatted header."""
    print("\n" + "-" * 60)
    print(f" {title}")
    print("-" * 60)


def print_success(message: str) -> None:
    """Print success message."""
    print(f"[OK] {message}")


def print_error(message: str) -> None:
    """Print error message."""
    print(f"[ERROR] {message}")


def print_warning(message: str) -> None:
    """Print warning message."""
    print(f"[WARNING] {message}")


def print_info(message: str) -> None:
    """Print info message."""
    print(f"[INFO] {message}")


def validate_database_connection() -> bool:
    """Validate that database connection is available."""
    print_header("Database Connection Check")
    
    try:
        from database.db_manager import init_db, get_db
        from database.db_factory import DatabaseType
        
        # Initialize database from environment
        database_url = os.getenv('DATABASE_URL')
        
        if database_url:
            print_info("Initializing PostgreSQL database...")
            try:
                init_db(DatabaseType.POSTGRESQL, DATABASE_URL=database_url)
            except Exception as e:
                print_error(f"Failed to initialize PostgreSQL: {str(e)}")
                return False
        else:
            print_info("Initializing SQLite database...")
            try:
                sqlite_path = os.getenv('SQLITE_PATH', './pedidos_bot.db')
                init_db(DatabaseType.SQLITE, db_path=sqlite_path)
            except Exception as e:
                print_error(f"Failed to initialize SQLite: {str(e)}")
                return False
        
        # Try to execute a simple query
        db = get_db()
        if db is None:
            print_error("Database manager returned None after initialization")
            return False
        
        result = db.execute('SELECT 1', ())
        print_success("Database connection OK")
        return True
            
    except ImportError as e:
        print_error(f"Failed to import database module: {str(e)}")
        return False
    except Exception as e:
        print_error(f"Unexpected error checking database: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def check_existing_admin() -> bool:
    """Check if any admin user already exists."""
    try:
        from database.db_manager import get_db
        
        db = get_db()
        result = db.execute(
            'SELECT COUNT(*) as cnt FROM customers WHERE is_admin = 1',
            (),
            fetchone=True
        )
        
        count = result['cnt'] if result else 0
        return count > 0
        
    except Exception as e:
        print_error(f"Error checking for existing admin: {str(e)}")
        # Assume admin exists to be safe
        return True


def import_required_modules():
    """Import and validate all required modules."""
    try:
        print_info("Importing required modules...")
        
        from shared.services.user_service import (
            UserService,
            PasswordValidator,
            PasswordHasher,
            EmailValidator
        )
        from shared.services.email_service import EmailService
        from shared.services.auth_service import is_valid_email
        from database.db_manager import get_db
        
        print_success("All modules imported successfully")
        return {
            'UserService': UserService,
            'PasswordValidator': PasswordValidator,
            'PasswordHasher': PasswordHasher,
            'EmailValidator': EmailValidator,
            'EmailService': EmailService,
            'is_valid_email': is_valid_email,
            'get_db': get_db
        }
    except ImportError as e:
        print_error(f"Failed to import required module: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def get_username(modules: dict) -> str:
    """Prompt for and validate username."""
    UserService = modules['UserService']
    get_db = modules['get_db']
    
    while True:
        username = input("Username: ").strip()
        
        if not username:
            print_error("Username cannot be empty")
            continue
        
        if len(username) < 3:
            print_error("Username must be at least 3 characters")
            continue
        
        if " " in username:
            print_error("Username cannot contain spaces")
            continue
        
        # Check if user already exists
        try:
            db = get_db()
            result = db.execute(
                'SELECT id FROM customers WHERE username = ?',
                (username,),
                fetchone=True
            )
            
            if result:
                print_error("This username is already taken")
                continue
        except Exception as e:
            print_error(f"Error checking username: {str(e)}")
            continue
        
        return username


def get_email(modules: dict) -> str:
    """Prompt for and validate email."""
    is_valid_email = modules['is_valid_email']
    get_db = modules['get_db']
    
    while True:
        email = input("Email: ").strip()
        
        if not email:
            print_error("Email cannot be empty")
            continue
        
        if not is_valid_email(email):
            print_error("Invalid email format")
            continue
        
        # Check if email already exists
        try:
            db = get_db()
            result = db.execute(
                'SELECT id FROM customers WHERE email = ?',
                (email,),
                fetchone=True
            )
            
            if result:
                print_error("This email is already registered")
                continue
        except Exception as e:
            print_error(f"Error checking email: {str(e)}")
            continue
        
        return email


def get_password(modules: dict) -> str:
    """Prompt for and validate password."""
    PasswordValidator = modules['PasswordValidator']
    
    while True:
        password = getpass.getpass("Password: ")
        
        # Validate password
        is_valid, error_msg = PasswordValidator.validate(password)
        if not is_valid:
            print_error(error_msg)
            continue
        
        password_confirm = getpass.getpass("Confirm password: ")
        
        if password != password_confirm:
            print_error("Passwords do not match")
            continue
        
        return password


def get_verification_code() -> str:
    """Prompt for and validate verification code."""
    while True:
        code = input("Enter verification code: ").strip()
        
        if not code:
            print_error("Code cannot be empty")
            continue
        
        if len(code) != 6 or not code.isdigit():
            print_error("Code must be exactly 6 digits")
            continue
        
        return code


def main():
    """Main script execution."""
    print_header("CREATE FIRST SUPERADMIN")
    
    # Validate database connection
    if not validate_database_connection():
        print_error("Cannot proceed without database connection")
        sys.exit(1)
    
    # Import required modules
    modules = import_required_modules()
    
    # Check if admin already exists
    if check_existing_admin():
        print_error("An admin user already exists in the database")
        print_info("To create additional admins, use the /api/register endpoint")
        sys.exit(1)
    
    print_info("No existing admin found - proceeding with creation\n")
    
    # Get user inputs
    print_header("User Information")
    username = get_username(modules)
    print_success(f"Username: {username}")
    
    email = get_email(modules)
    print_success(f"Email: {email}")
    
    password = get_password(modules)
    print_success("Password: ••••••••")
    
    # Create API user
    print_header("Creating User")
    try:
        PasswordHasher = modules['PasswordHasher']
        get_db = modules['get_db']
        
        # Hash password
        password_hash = PasswordHasher.hash_password(password)
        customer_id = f"api_{username}"
        
        # Generate verification code
        import random
        verification_code = str(random.randint(100000, 999999))
        expires_at = datetime.utcnow() + timedelta(minutes=15)
        
        # Insert into database
        db = get_db()
        
        # Use execute with proper parameter handling
        cursor = db.execute(
            """
            INSERT INTO customers 
            (customer_id, username, email, name, password_hash, is_admin, 
             email_verified, email_verification_code, email_verification_expires, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
             (
                customer_id,           # customer_id
                username,              # username
                email,                 # email
                username,              # name (use username as default)
                password_hash,         # password_hash
                1,                     # is_admin = 1 (INTEGER type in PostgreSQL)
                False,                 # email_verified = False (BOOLEAN type in PostgreSQL)
                verification_code,     # email_verification_code
                expires_at.isoformat(),  # email_verification_expires
                None                   # created_by = NULL (first admin, no creator)
            )
        )
        
        print_success(f"User created: {username}")
        
    except Exception as e:
        print_error(f"Failed to create user: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Send verification email (mock - will print to console)
    print_header("Email Verification")
    try:
        EmailService = modules['EmailService']
        
        print_info(f"Sending verification email to: {email}\n")
        EmailService.send_verification_email(
            email=email,
            code=verification_code,
            user_name=username
        )
        
        print_header("VERIFICATION CODE")
        print("\n[INFO] In development mode, the verification code is displayed below")
        print("[INFO] (In production, this would be sent via email)\n")
        print("=" * 60)
        print(f"Email: {email}")
        print("=" * 60)
        print(f"\nVerification Code:\n")
        print(f"    {verification_code}")
        print(f"\nExpires in: 15 minutes")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print_error(f"Failed to send verification email: {str(e)}")
        print_warning("You can still verify manually using the code above")
    
    # Verify email
    print_header("Verify Email")
    try:
        get_db = modules['get_db']
        
        while True:
            code = get_verification_code()
            
            # Verify the code in database
            db = get_db()
            
            # Check if code matches and hasn't expired
            result = db.execute(
                """
                SELECT id FROM customers 
                WHERE email = ? 
                AND email_verification_code = ?
                AND email_verification_expires > ?
                """,
                (email, code, datetime.utcnow().isoformat()),
                fetchone=True
            )
            
            if result:
                # Mark email as verified
                db.execute(
                    """
                    UPDATE customers 
                    SET email_verified = ?, email_verification_code = NULL
                    WHERE email = ?
                    """,
                    (True, email)
                )
                #db.commit()
                print_success("Email verified successfully!")
                break
            else:
                print_error("Invalid or expired verification code. Please try again.")
    
    except Exception as e:
        print_error(f"Failed to verify email: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Success message
    print_header("Success")
    print(f"\n[OK] Superadmin account created successfully!\n")
    print("-" * 60)
    print(f"Username: {username}")
    print(f"Email: {email}")
    print(f"Admin Level: Superadmin (is_admin=1)")
    print(f"Email Verified: Yes")
    print("-" * 60 + "\n")
    
    print("You can now use these credentials to:")
    print("  1. Login via /api/login endpoint")
    print("  2. Register additional admin users via /api/register")
    print("  3. Access admin-only endpoints\n")
    
    print_info("Next steps:")
    print("  - Run database migrations: py migrations/migrate.py")
    print("  - Test login: POST /api/login with your credentials")
    print("  - Create more admins: POST /api/register (requires JWT from superadmin)\n")


if __name__ == "__main__":
    main()
