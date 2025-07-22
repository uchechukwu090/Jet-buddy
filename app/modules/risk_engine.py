# ==============================================================================
# FILE: app/modules/risk_engine.py
# ==============================================================================
# --- Description:
# Implements the simplified KellyModule. It recommends a position size
# based on fixed tiers, determined by the aggregator's confidence score
# and the market's volatility level.

def get_position_size(confidence: float, volatility: str, risk_tier: str = 'medium') -> dict:
    """
    Recommends a position size based on a fixed tier system.
    
    Output: Dictionary with risk profile and suggested lot size.
    """
    # Adjust risk tier based on volatility and confidence
    if confidence < 0.4:
        effective_tier = 'conservative'
        reason_confidence = "Low confidence score (< 0.4)."
    elif volatility == 'high':
        effective_tier = 'conservative'
        reason_confidence = "High market volatility."
    elif confidence > 0.75 and volatility != 'high':
        effective_tier = 'aggressive'
        reason_confidence = "High confidence score (> 0.75)."
    else:
        effective_tier = risk_tier # Use user-defined default
        reason_confidence = f"Confidence score {confidence} with {volatility} volatility."

    # Define lot sizes per tier
    lot_sizes = {
        'conservative': 0.01,
        'medium': 0.10,
        'aggressive': 1.00
    }
    
    suggested_lot = lot_sizes.get(effective_tier, 0.10)
    
    reason = f"{reason_confidence} Applying '{effective_tier}' risk tier."
    
    return {
        "risk_profile": effective_tier,
        "suggested_lot_size": suggested_lot,
        "reason": reason
    }
