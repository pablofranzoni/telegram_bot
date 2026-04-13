"""Package for Telegram bot handler modules.

This package groups handler logic by feature (auth, products, cart, payments) and
exposes a stable public interface via `shared.handlers.commands`.
"""

# This file intentionally left minimal. Individual handler modules live under
# shared.handlers and are re-exported by shared.handlers.commands.
