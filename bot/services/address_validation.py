"""Address validation and geocoding services."""

import logging
from typing import Optional, Dict, Any

import httpx
from ..config import get_settings
from ..models import LocationData, AddressValidationResult

logger = logging.getLogger(__name__)


class AddressValidationService:
    """Service for validating and standardizing addresses."""

    def __init__(self):
        self.settings = get_settings()
        self.client = httpx.AsyncClient(timeout=30.0)

    async def validate_address(
        self, address: str, country_code: str = None
    ) -> AddressValidationResult:
        """
        Validate and standardize an address using Google Places API.

        Args:
            address: The address string to validate
            country_code: ISO country code (defaults to config setting)

        Returns:
            AddressValidationResult with validation details
        """
        if (
            not self.settings.ENABLE_ADDRESS_VALIDATION
            or not self.settings.GOOGLE_PLACES_API_KEY
        ):
            # Return basic validation without API call
            return AddressValidationResult(
                is_valid=bool(address.strip()),
                formatted_address=address.strip(),
                original_address=address,
                confidence_score=None,
                components=None,
                suggestions=None,
            )

        country_code = country_code or self.settings.DEFAULT_COUNTRY_CODE

        try:
            response = await self._call_google_address_validation(address, country_code)
            return self._parse_google_response(address, response)
        except Exception as e:
            logger.error(f"Address validation failed: {e}")
            # Fallback to basic validation
            return AddressValidationResult(
                is_valid=bool(address.strip()),
                formatted_address=address.strip(),
                original_address=address,
                confidence_score=0.5,
                components=None,
                suggestions=None,
            )

    async def reverse_geocode(self, latitude: float, longitude: float) -> Optional[str]:
        """
        Convert coordinates to a readable address.

        Args:
            latitude: GPS latitude
            longitude: GPS longitude

        Returns:
            Formatted address string or None if failed
        """
        if not self.settings.GOOGLE_PLACES_API_KEY:
            return f"Location: {latitude:.6f}, {longitude:.6f}"

        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                "latlng": f"{latitude},{longitude}",
                "key": self.settings.GOOGLE_PLACES_API_KEY,
                "result_type": "street_address|premise",
            }

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if data.get("status") == "OK" and data.get("results"):
                return data["results"][0]["formatted_address"]

            return None

        except Exception as e:
            logger.error(f"Reverse geocoding failed: {e}")
            return f"Location: {latitude:.6f}, {longitude:.6f}"

    async def geocode_address(self, address: str) -> Optional[LocationData]:
        """
        Convert address to coordinates.

        Args:
            address: Address string to geocode

        Returns:
            LocationData with coordinates or None if failed
        """
        if not self.settings.GOOGLE_PLACES_API_KEY:
            return None

        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {"address": address, "key": self.settings.GOOGLE_PLACES_API_KEY}

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if data.get("status") == "OK" and data.get("results"):
                location = data["results"][0]["geometry"]["location"]
                return LocationData(
                    latitude=location["lat"],
                    longitude=location["lng"],
                    address=data["results"][0]["formatted_address"],
                )

            return None

        except Exception as e:
            logger.error(f"Geocoding failed: {e}")
            return None

    async def _call_google_address_validation(
        self, address: str, country_code: str
    ) -> Dict[str, Any]:
        """Call Google Address Validation API."""
        url = "https://addressvalidation.googleapis.com/v1:validateAddress"

        headers = {"Content-Type": "application/json"}

        params = {"key": self.settings.GOOGLE_PLACES_API_KEY}

        payload = {
            "address": {"addressLines": [address], "regionCode": country_code},
            "enableUspsCass": True,
        }

        response = await self.client.post(
            url, json=payload, headers=headers, params=params
        )
        response.raise_for_status()

        return response.json()

    def _parse_google_response(
        self, original_address: str, response: Dict[str, Any]
    ) -> AddressValidationResult:
        """Parse Google Address Validation API response."""
        result = response.get("result", {})
        verdict = result.get("verdict", {})
        address = result.get("address", {})

        # Determine if address is valid
        is_valid = (
            verdict.get("addressComplete", False)
            and verdict.get("hasInferredComponents", True) is not True
        )

        # Get formatted address
        formatted_address = address.get("formattedAddress", original_address)

        # Extract confidence score (0-1)
        confidence_score = None
        if "geocode" in result:
            geocode = result["geocode"]
            if "plusCode" in geocode:
                # Use plus code as confidence indicator (rough approximation)
                confidence_score = 0.9 if is_valid else 0.5

        # Extract address components
        components = {}
        if "components" in address:
            for component in address["components"]:
                component_type = component.get("componentType", {}).get(
                    "name", "unknown"
                )
                component_value = component.get("componentName", {}).get("text", "")
                if component_value:
                    components[component_type] = component_value

        return AddressValidationResult(
            is_valid=is_valid,
            formatted_address=formatted_address,
            original_address=original_address,
            confidence_score=confidence_score,
            components=components if components else None,
            suggestions=None,  # Google doesn't provide suggestions in this API
        )

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Global service instance
_address_service: Optional[AddressValidationService] = None


def get_address_service() -> AddressValidationService:
    """Get the global address validation service instance."""
    global _address_service
    if _address_service is None:
        _address_service = AddressValidationService()
    return _address_service


async def close_address_service():
    """Close the global address service."""
    global _address_service
    if _address_service:
        await _address_service.close()
        _address_service = None
