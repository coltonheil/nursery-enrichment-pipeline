"""
Test suite for geographic scoring - Phase 10
Tests state-based geographic proximity scoring.
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from enrichment.scorer import calculate_geo_score, normalize_state, extract_state_from_address


class TestGeoScoring:
    """Test geographic scoring by state."""

    def test_wisconsin_bonus(self):
        """Wisconsin (local) should get +25 points."""
        lead = {"state": "WI"}
        assert calculate_geo_score(lead) == 25

    def test_wisconsin_full_name(self):
        """Wisconsin spelled out should also work."""
        lead = {"state": "Wisconsin"}
        assert calculate_geo_score(lead) == 25

    def test_regional_states(self):
        """Regional states (IL, MN, IA, MI) should get +20 points."""
        for state in ["IL", "MN", "IA", "MI"]:
            lead = {"state": state}
            assert calculate_geo_score(lead) == 20, f"State {state} should score 20"

    def test_near_states(self):
        """Near states should get +10 points."""
        for state in ["IN", "OH", "MO", "NE", "KY"]:
            lead = {"state": state}
            assert calculate_geo_score(lead) == 10, f"State {state} should score 10"

    def test_mid_states(self):
        """Mid-distance states should get 0 points."""
        for state in ["NY", "PA", "CO", "AZ"]:
            lead = {"state": state}
            assert calculate_geo_score(lead) == 0, f"State {state} should score 0"

    def test_far_states(self):
        """Far states should get -5 penalty."""
        for state in ["TX", "CA", "FL", "WA", "OR"]:
            lead = {"state": state}
            assert calculate_geo_score(lead) == -5, f"State {state} should score -5"

    def test_missing_state(self):
        """Missing state should get 0 points."""
        lead = {}
        assert calculate_geo_score(lead) == 0


class TestStateNormalization:
    """Test state name normalization."""

    def test_normalize_abbreviations(self):
        """State abbreviations should normalize correctly."""
        assert normalize_state("WI") == "WI"
        assert normalize_state("wi") == "WI"
        assert normalize_state("IL") == "IL"

    def test_normalize_full_names(self):
        """Full state names should normalize to abbreviations."""
        assert normalize_state("Wisconsin") == "WI"
        assert normalize_state("wisconsin") == "WI"
        assert normalize_state("Illinois") == "IL"
        assert normalize_state("Minnesota") == "MN"
        assert normalize_state("California") == "CA"

    def test_normalize_invalid_state(self):
        """Invalid state names should return None."""
        assert normalize_state("InvalidState") is None
        assert normalize_state("XY") is None
        assert normalize_state("") is None


class TestAddressExtraction:
    """Test state extraction from addresses."""

    def test_extract_state_from_address(self):
        """Should extract state abbreviation from address."""
        address = "123 Main St, Madison, WI 53703"
        assert extract_state_from_address(address) == "WI"

    def test_extract_state_multiple_commas(self):
        """Should handle addresses with multiple commas."""
        address = "456 Oak Ave, Suite 200, Chicago, IL 60601"
        assert extract_state_from_address(address) == "IL"

    def test_extract_state_full_name(self):
        """Should extract full state names from address."""
        address = "789 Pine Rd, Minneapolis, Minnesota 55401"
        assert extract_state_from_address(address) == "MN"

    def test_address_no_state(self):
        """Should return None if no state found."""
        address = "123 Main Street"
        result = extract_state_from_address(address)
        assert result is None or result == ""

    def test_address_extraction_in_geo_score(self):
        """Geo score should use address if state field is missing."""
        lead = {"address": "123 Main St, Madison, WI 53703"}
        assert calculate_geo_score(lead) == 25


class TestGeoScoreIntegration:
    """Test geographic scoring integration with full leads."""

    def test_state_priority_over_address(self):
        """State field should take priority over address."""
        lead = {
            "state": "WI",
            "address": "123 Main St, Chicago, IL 60601"
        }
        # Should use state field (WI) not address (IL)
        assert calculate_geo_score(lead) == 25

    def test_fallback_to_address(self):
        """Should fallback to address if state is missing."""
        lead = {
            "address": "456 Oak Ave, Minneapolis, MN 55401"
        }
        assert calculate_geo_score(lead) == 20


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
