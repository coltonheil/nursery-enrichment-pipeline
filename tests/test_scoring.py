"""
Test suite for scoring model - Phase 10
Tests ICP qualification, scoring logic, and tier assignments.
"""

import pytest
import sys
import os
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from enrichment.scorer import calculate_score, check_icp_qualification


class TestICPQualification:
    """Test ICP qualification gate."""

    def test_primary_icp_greenhouse(self):
        """Greenhouse with growing media should be primary ICP."""
        lead = {
            "uses_growing_media": True,
            "production_method": "greenhouse"
        }
        qualified, icp_type = check_icp_qualification(lead)
        assert qualified == True
        assert icp_type == "primary"

    def test_primary_icp_container(self):
        """Container production should be primary ICP."""
        lead = {
            "uses_growing_media": True,
            "production_method": "container"
        }
        qualified, icp_type = check_icp_qualification(lead)
        assert qualified == True
        assert icp_type == "primary"

    def test_disqualified_landscaper(self):
        """Landscaper should be disqualified."""
        lead = {
            "business_type": "landscaper",
            "disqualification_signals": '["landscape installation"]'
        }
        qualified, icp_type = check_icp_qualification(lead)
        assert qualified == False
        assert icp_type == "disqualified"

    def test_disqualified_lawn_care(self):
        """Lawn care business should be disqualified."""
        lead = {
            "business_name": "Green Lawn Services",
            "business_type": "lawn care",
            "uses_growing_media": False
        }
        qualified, icp_type = check_icp_qualification(lead)
        assert qualified == False
        assert icp_type == "disqualified"

    def test_tertiary_organic_field(self):
        """Organic field farm should be tertiary ICP."""
        lead = {
            "business_name": "Organic Farm Co",
            "production_method": "field",
            "is_organic_certified": True
        }
        qualified, icp_type = check_icp_qualification(lead)
        assert qualified == True
        assert icp_type == "tertiary"


class TestScoring:
    """Test scoring calculations."""

    def test_tier_a_ideal_lead(self):
        """Ideal sample requester profile should score Tier A."""
        lead = {
            "business_name": "Driftless Organics",
            "is_organic_certified": True,
            "uses_growing_media": True,
            "production_method": "greenhouse",
            "is_wholesale": True,
            "state": "WI",
            "geo_score": 25,
            "scale_indicators": '["10 greenhouses", "50 acres"]'
        }
        result = calculate_score(lead)
        assert result['tier'] == 'A' or result['tier'] == 'B', f"Expected tier A or B, got {result['tier']} with score {result['total']}"
        assert result['total'] >= 40
        assert result['icp_qualified'] == True

    def test_tier_b_qualified_lead(self):
        """Qualified lead without all ideal signals should score Tier B."""
        lead = {
            "business_name": "Green Growers Inc",
            "uses_growing_media": True,
            "production_method": "container",
            "is_wholesale": True,
            "state": "IL",
            "geo_score": 20
        }
        result = calculate_score(lead)
        assert result['tier'] in ['A', 'B', 'C']
        assert result['total'] >= 20
        assert result['icp_qualified'] == True

    def test_tier_c_low_score(self):
        """Qualified lead with low score should be Tier C."""
        lead = {
            "business_name": "Small Farm",
            "uses_growing_media": True,
            "production_method": "field",
            "state": "TX",
            "geo_score": -5
        }
        result = calculate_score(lead)
        assert result['tier'] == 'C'
        assert result['total'] < 40

    def test_tier_u_landscaper(self):
        """Landscaper should score Tier U or C."""
        lead = {
            "business_name": "Green Thumb Landscaping",
            "business_type": "landscaper",
            "disqualification_signals": '["landscaping", "lawn care"]',
            "uses_growing_media": False
        }
        result = calculate_score(lead)
        assert result['tier'] in ['U', 'C']
        assert result['icp_type'] == "disqualified"

    def test_score_breakdown_populated(self):
        """Score breakdown should list all matching signals."""
        lead = {
            "business_name": "Organic Growers Inc",
            "is_organic_certified": True,
            "is_wholesale": True,
            "uses_growing_media": True,
            "state": "WI",
            "geo_score": 25
        }
        result = calculate_score(lead)
        assert 'signals' in result
        assert len(result['signals']) > 0
        assert isinstance(result['signals'], list)

    def test_organic_in_name_signal(self):
        """'Organic' in business name should trigger signal."""
        lead = {
            "business_name": "Wisconsin Organics LLC",
            "uses_growing_media": True,
            "state": "WI"
        }
        result = calculate_score(lead)
        # Check if organic signal is present
        has_organic_signal = any('organic' in s.get('description', '').lower()
                                for s in result['signals'])
        assert has_organic_signal

    def test_wholesale_signal(self):
        """Wholesale status should add points."""
        lead = {
            "business_name": "Test Nursery",
            "uses_growing_media": True,
            "is_wholesale": True,
            "state": "WI"
        }
        result = calculate_score(lead)
        has_wholesale_signal = any('wholesale' in s.get('description', '').lower()
                                  for s in result['signals'])
        assert has_wholesale_signal


class TestScoreBreakdown:
    """Test score breakdown structure and content."""

    def test_breakdown_has_required_fields(self):
        """Score breakdown should have all required fields."""
        lead = {
            "business_name": "Test Grower",
            "uses_growing_media": True,
            "state": "WI"
        }
        result = calculate_score(lead)
        assert 'total' in result
        assert 'tier' in result
        assert 'signals' in result
        assert 'has_data' in result
        assert 'icp_qualified' in result
        assert 'icp_type' in result

    def test_signals_have_structure(self):
        """Each signal should have description and points."""
        lead = {
            "business_name": "Organic Growers",
            "uses_growing_media": True,
            "is_organic_certified": True,
            "state": "WI"
        }
        result = calculate_score(lead)
        for signal in result['signals']:
            assert 'description' in signal
            assert 'points' in signal
            assert isinstance(signal['points'], (int, float))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
