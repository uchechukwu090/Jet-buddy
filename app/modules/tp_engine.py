# ==============================================================================
# FILE: app/modules/tp_engine.py
# ==============================================================================
# Predictive Take-Profit Engine using trend analysis and SMC structure

def generate_tp_prediction(trend_data: dict, smc_data: dict, risk_profile: dict) -> dict:
    """
    Predicts TP and SL levels based on trend bias, SMC zones, and risk profile.
    Inputs:
        trend_data: {'bias': str, 'confidence': float, 'momentum': float}
        smc_data: {'order_block': float, 'liquidity_zone': float, 'key_level': float}
        risk_profile: {'risk_ratio': float, 'entry_price': float}
    Returns:
        dict with predicted TP and SL levels
    """
    try:
        bias = trend_data.get('bias', 'neutral')
        confidence = trend_data.get('confidence', 50)
        momentum = trend_data.get('momentum', 1.0)

        entry_price = risk_profile.get('entry_price', smc_data.get('key_level', 1.0))
        risk_ratio = risk_profile.get('risk_ratio', 2.0)

        # Use SMC zones to anchor TP prediction
        if bias == 'bullish':
            base_tp = max(smc_data['order_block'], smc_data['liquidity_zone'])
            tp_level = base_tp + (momentum * confidence / 100)
            sl_level = entry_price - ((tp_level - entry_price) / risk_ratio)
        elif bias == 'bearish':
            base_tp = min(smc_data['order_block'], smc_data['liquidity_zone'])
            tp_level = base_tp - (momentum * confidence / 100)
            sl_level = entry_price + ((entry_price - tp_level) / risk_ratio)
        else:
            tp_level = entry_price
            sl_level = entry_price

        return {
            'bias': bias,
            'tp_level': round(tp_level, 4),
            'sl_level': round(sl_level, 4),
            'confidence': confidence,
            'source': 'tp_engine'
        }

    except Exception as e:
        print(f"[TP Engine] Error: {e}")
        return {'tp_level': 0.0, 'sl_level': 0.0, 'error': str(e)}
