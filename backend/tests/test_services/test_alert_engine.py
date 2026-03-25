"""
Tests for the alert condition evaluator.

The evaluator is the core logic of the alert engine. It takes a condition dict
and market data dict, returning whether the condition is met.
"""

import pytest
from app.services.alert_engine import evaluate_condition


class TestEvaluateCondition:
    """Tests for the evaluate_condition function."""

    # Price condition tests
    def test_price_greater_than_met(self):
        condition = {"metric": "price", "operator": ">", "value": 150}
        market_data = {"price": 155.30}
        met, actual = evaluate_condition(condition, market_data)
        assert met is True
        assert actual == 155.30

    def test_price_greater_than_not_met(self):
        condition = {"metric": "price", "operator": ">", "value": 150}
        market_data = {"price": 145.00}
        met, actual = evaluate_condition(condition, market_data)
        assert met is False
        assert actual == 145.00

    def test_price_less_than_met(self):
        condition = {"metric": "price", "operator": "<", "value": 150}
        market_data = {"price": 145.00}
        met, actual = evaluate_condition(condition, market_data)
        assert met is True
        assert actual == 145.00

    def test_price_less_than_not_met(self):
        condition = {"metric": "price", "operator": "<", "value": 150}
        market_data = {"price": 155.30}
        met, actual = evaluate_condition(condition, market_data)
        assert met is False
        assert actual == 155.30

    def test_price_greater_equal_met_equal(self):
        condition = {"metric": "price", "operator": ">=", "value": 150}
        market_data = {"price": 150.00}
        met, actual = evaluate_condition(condition, market_data)
        assert met is True
        assert actual == 150.00

    def test_price_greater_equal_met_greater(self):
        condition = {"metric": "price", "operator": ">=", "value": 150}
        market_data = {"price": 155.30}
        met, actual = evaluate_condition(condition, market_data)
        assert met is True
        assert actual == 155.30

    def test_price_less_equal_met_equal(self):
        condition = {"metric": "price", "operator": "<=", "value": 150}
        market_data = {"price": 150.00}
        met, actual = evaluate_condition(condition, market_data)
        assert met is True
        assert actual == 150.00

    def test_price_equal_met(self):
        condition = {"metric": "price", "operator": "==", "value": 150}
        market_data = {"price": 150.00}
        met, actual = evaluate_condition(condition, market_data)
        assert met is True
        assert actual == 150.00

    def test_price_equal_not_met(self):
        condition = {"metric": "price", "operator": "==", "value": 150}
        market_data = {"price": 150.01}
        met, actual = evaluate_condition(condition, market_data)
        assert met is False
        assert actual == 150.01

    # RSI condition tests
    def test_rsi_oversold_met(self):
        """RSI below 30 = oversold."""
        condition = {"metric": "rsi", "operator": "<", "value": 30}
        market_data = {"rsi": 25.5, "price": 150}
        met, actual = evaluate_condition(condition, market_data)
        assert met is True
        assert actual == 25.5

    def test_rsi_oversold_not_met(self):
        condition = {"metric": "rsi", "operator": "<", "value": 30}
        market_data = {"rsi": 45.0, "price": 150}
        met, actual = evaluate_condition(condition, market_data)
        assert met is False
        assert actual == 45.0

    def test_rsi_overbought_met(self):
        """RSI above 70 = overbought."""
        condition = {"metric": "rsi", "operator": ">", "value": 70}
        market_data = {"rsi": 75.2, "price": 150}
        met, actual = evaluate_condition(condition, market_data)
        assert met is True
        assert actual == 75.2

    # HV rank condition tests
    def test_hv_rank_elevated_met(self):
        """HV rank above 70 = elevated volatility."""
        condition = {"metric": "hv_rank", "operator": ">", "value": 70}
        market_data = {"hv_rank": 82.0, "price": 150}
        met, actual = evaluate_condition(condition, market_data)
        assert met is True
        assert actual == 82.0

    def test_hv_rank_low_met(self):
        """HV rank below 30 = low volatility."""
        condition = {"metric": "hv_rank", "operator": "<", "value": 30}
        market_data = {"hv_rank": 18.5, "price": 150}
        met, actual = evaluate_condition(condition, market_data)
        assert met is True
        assert actual == 18.5

    # Edge cases and error handling
    def test_missing_metric_in_condition(self):
        condition = {"operator": ">", "value": 150}
        market_data = {"price": 155.30}
        met, actual = evaluate_condition(condition, market_data)
        assert met is False
        assert actual is None

    def test_missing_operator_in_condition(self):
        condition = {"metric": "price", "value": 150}
        market_data = {"price": 155.30}
        met, actual = evaluate_condition(condition, market_data)
        assert met is False
        assert actual is None

    def test_missing_value_in_condition(self):
        condition = {"metric": "price", "operator": ">"}
        market_data = {"price": 155.30}
        met, actual = evaluate_condition(condition, market_data)
        assert met is False
        assert actual is None

    def test_metric_not_in_market_data(self):
        condition = {"metric": "rsi", "operator": "<", "value": 30}
        market_data = {"price": 155.30}  # No RSI data
        met, actual = evaluate_condition(condition, market_data)
        assert met is False
        assert actual is None

    def test_invalid_operator(self):
        condition = {"metric": "price", "operator": "!=", "value": 150}
        market_data = {"price": 155.30}
        met, actual = evaluate_condition(condition, market_data)
        assert met is False
        assert actual is None

    def test_empty_condition(self):
        condition = {}
        market_data = {"price": 155.30}
        met, actual = evaluate_condition(condition, market_data)
        assert met is False
        assert actual is None

    def test_empty_market_data(self):
        condition = {"metric": "price", "operator": ">", "value": 150}
        market_data = {}
        met, actual = evaluate_condition(condition, market_data)
        assert met is False
        assert actual is None

    def test_value_zero_works(self):
        """Ensure value=0 doesn't trigger falsy check."""
        condition = {"metric": "change_pct", "operator": "<=", "value": 0}
        market_data = {"change_pct": -2.5}
        met, actual = evaluate_condition(condition, market_data)
        assert met is True
        assert actual == -2.5

    # Type coercion tests
    def test_string_number_in_market_data(self):
        """Market data might have string numbers from JSON."""
        condition = {"metric": "price", "operator": ">", "value": 150}
        market_data = {"price": "155.30"}  # String instead of float
        met, actual = evaluate_condition(condition, market_data)
        assert met is True
        assert actual == 155.30

    def test_integer_values(self):
        condition = {"metric": "volume", "operator": ">", "value": 1000000}
        market_data = {"volume": 1500000}
        met, actual = evaluate_condition(condition, market_data)
        assert met is True
        assert actual == 1500000.0


class TestMultipleConditionTypes:
    """Test various alert condition scenarios."""

    def test_earnings_surprise_positive(self):
        """EPS beat condition."""
        condition = {"metric": "eps", "operator": ">", "value": 4.0}
        market_data = {"eps": 4.25}
        met, actual = evaluate_condition(condition, market_data)
        assert met is True

    def test_earnings_surprise_negative(self):
        """EPS miss condition."""
        condition = {"metric": "eps", "operator": "<", "value": 4.0}
        market_data = {"eps": 3.85}
        met, actual = evaluate_condition(condition, market_data)
        assert met is True

    def test_support_break(self):
        """Price breaks below support level."""
        condition = {"metric": "price", "operator": "<", "value": 145.0}
        market_data = {"price": 143.50, "support": 145.0}
        met, actual = evaluate_condition(condition, market_data)
        assert met is True

    def test_resistance_break(self):
        """Price breaks above resistance level."""
        condition = {"metric": "price", "operator": ">", "value": 160.0}
        market_data = {"price": 162.30, "resistance": 160.0}
        met, actual = evaluate_condition(condition, market_data)
        assert met is True
