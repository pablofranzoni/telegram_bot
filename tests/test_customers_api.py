"""Unit tests for the /api/customers REST endpoint (read-only)."""

from unittest.mock import patch

import pytest

from shared.dtos import CustomerDTO


# Helpers
def _make_customer(
    customer_id: int = 1,
    name: str = "Pablo Franzoni",
    telegram_id: str = "7225069015",
    email: str = "pablo@example.com",
) -> CustomerDTO:
    return CustomerDTO(
        id=customer_id,
        name=name,
        telegram_id=telegram_id,
        email=email,
    )


# ===========================================================================
#  GET /api/customers (PROTECTED - Requires JWT token)
# ===========================================================================
class TestListCustomers:
    """Test cases for GET /api/customers endpoint."""

    def test_list_customers_without_token_returns_401(self, client):
        """Test that listing customers without JWT token returns 401."""
        response = client.get("/api/customers")

        assert response.status_code == 401
        data = response.get_json()
        assert data['status'] == 'error'

    def test_list_customers_with_invalid_token_returns_401(self, client):
        """Test that listing customers with invalid JWT token returns 401."""
        response = client.get(
            "/api/customers",
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data['status'] == 'error'

    def test_list_customers_with_valid_token_returns_200(self, client, auth_headers):
        """Test that listing customers with valid JWT token returns 200."""
        customers = [
            _make_customer(1),
            _make_customer(2, name="Ana García", telegram_id="1234567890"),
        ]

        with patch(
            "routes.customers_routes.customer_service.list_customers",
            return_value=(customers, 2),
        ):
            response = client.get("/api/customers", headers=auth_headers)

        assert response.status_code == 200
        body = response.get_json()
        assert len(body["customers"]) == 2
        assert body["customers"][0]["id"] == 1
        assert body["customers"][0]["name"] == "Pablo Franzoni"
        assert body["customers"][0]["telegram_id"] == "7225069015"
        assert body["customers"][0]["email"] == "pablo@example.com"
        assert body["customers"][1]["name"] == "Ana García"
        assert body["pagination"]["total"] == 2
        assert body["pagination"]["page"] == 1
        assert body["pagination"]["per_page"] == 10
        assert body["pagination"]["total_pages"] == 1

    def test_list_customers_with_pagination(self, client, auth_headers):
        """Test customers list with pagination parameters."""
        customers = [_make_customer(11)]

        with patch(
            "routes.customers_routes.customer_service.list_customers",
            return_value=(customers, 1),
        ) as mock_list:
            response = client.get(
                "/api/customers?page=2&per_page=10",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.get_json()
        assert body["pagination"]["page"] == 2
        assert body["pagination"]["per_page"] == 10
        mock_list.assert_called_once_with(page=2, per_page=10)

    def test_list_customers_empty_returns_200(self, client, auth_headers):
        """Test that empty customers list returns 200."""
        with patch(
            "routes.customers_routes.customer_service.list_customers",
            return_value=([], 0),
        ):
            response = client.get("/api/customers", headers=auth_headers)

        assert response.status_code == 200
        body = response.get_json()
        assert body["customers"] == []
        assert body["pagination"]["total"] == 0
        assert body["pagination"]["total_pages"] == 0

    def test_list_customers_invalid_pagination_returns_400(self, client, auth_headers):
        """Test that invalid pagination parameters return 400."""
        response = client.get(
            "/api/customers?page=abc",
            headers=auth_headers,
        )

        assert response.status_code == 400

    def test_list_customers_omits_none_fields(self, client, auth_headers):
        """Test that customers with null telegram_id/email are still returned."""
        customers = [_make_customer(1, telegram_id=None, email=None)]

        with patch(
            "routes.customers_routes.customer_service.list_customers",
            return_value=(customers, 1),
        ):
            response = client.get("/api/customers", headers=auth_headers)

        assert response.status_code == 200
        body = response.get_json()
        assert body["customers"][0]["telegram_id"] is None
        assert body["customers"][0]["email"] is None


# ===========================================================================
#  Write methods (POST, PUT, DELETE) should not be allowed
# ===========================================================================
class TestCustomersReadOnlyConstraints:
    """Test that write operations are not allowed on customers listing."""

    @pytest.mark.parametrize("method", ["post", "put", "delete", "patch"])
    def test_write_methods_return_405(self, client, method):
        """Test that write methods on /api/customers return 405 Method Not Allowed."""
        response = getattr(client, method)("/api/customers", json={})
        assert response.status_code == 405
