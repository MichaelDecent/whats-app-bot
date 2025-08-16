import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

from bot.services.address_validation import AddressValidationService
from bot.models import AddressValidationResult


@pytest.mark.asyncio
async def test_address_validation_without_api():
    """Test address validation when API is disabled."""
    with patch("bot.services.address_validation.get_settings") as mock_settings:
        mock_settings.return_value.ENABLE_ADDRESS_VALIDATION = False
        mock_settings.return_value.GOOGLE_PLACES_API_KEY = None

        service = AddressValidationService()
        result = await service.validate_address("123 Main St, Lagos")

        assert isinstance(result, AddressValidationResult)
        assert result.is_valid is True
        assert result.formatted_address == "123 Main St, Lagos"
        assert result.original_address == "123 Main St, Lagos"

        await service.close()


@pytest.mark.asyncio
async def test_reverse_geocode_without_api():
    """Test reverse geocoding when API is disabled."""
    with patch("bot.services.address_validation.get_settings") as mock_settings:
        mock_settings.return_value.GOOGLE_PLACES_API_KEY = None

        service = AddressValidationService()
        result = await service.reverse_geocode(6.5244, 3.3792)  # Lagos coordinates

        assert result == "Location: 6.524400, 3.379200"

        await service.close()


@pytest.mark.asyncio
async def test_address_validation_with_api_success():
    """Test address validation with successful API response."""
    mock_response_data = {
        "result": {
            "verdict": {"addressComplete": True, "hasInferredComponents": False},
            "address": {"formattedAddress": "123 Main Street, Lagos, Nigeria"},
        }
    }

    with patch("bot.services.address_validation.get_settings") as mock_settings:
        mock_settings.return_value.ENABLE_ADDRESS_VALIDATION = True
        mock_settings.return_value.GOOGLE_PLACES_API_KEY = "test_key"
        mock_settings.return_value.DEFAULT_COUNTRY_CODE = "NG"

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            service = AddressValidationService()
            result = await service.validate_address("123 Main St")

            assert result.is_valid is True
            assert result.formatted_address == "123 Main Street, Lagos, Nigeria"
            assert result.original_address == "123 Main St"

            await service.close()


@pytest.mark.asyncio
async def test_reverse_geocode_with_api_success():
    """Test reverse geocoding with successful API response."""
    mock_response_data = {
        "status": "OK",
        "results": [{"formatted_address": "123 Main Street, Lagos, Nigeria"}],
    }

    with patch("bot.services.address_validation.get_settings") as mock_settings:
        mock_settings.return_value.GOOGLE_PLACES_API_KEY = "test_key"

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            service = AddressValidationService()
            result = await service.reverse_geocode(6.5244, 3.3792)

            assert result == "123 Main Street, Lagos, Nigeria"

            await service.close()


@pytest.mark.asyncio
async def test_address_validation_api_failure():
    """Test address validation when API fails."""
    with patch("bot.services.address_validation.get_settings") as mock_settings:
        mock_settings.return_value.ENABLE_ADDRESS_VALIDATION = True
        mock_settings.return_value.GOOGLE_PLACES_API_KEY = "test_key"
        mock_settings.return_value.DEFAULT_COUNTRY_CODE = "NG"

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = Exception("API Error")

            service = AddressValidationService()
            result = await service.validate_address("123 Main St")

            # Should fallback to basic validation
            assert result.is_valid is True
            assert result.formatted_address == "123 Main St"
            assert result.original_address == "123 Main St"
            assert result.confidence_score == 0.5

            await service.close()
