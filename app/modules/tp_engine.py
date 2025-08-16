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
        bias = trend_data.get('bias', 'neutral').lower()
        confidence = trend_data.get('confidence', 0.5)
        momentum = trend_data.get('momentum', 1.0)

        entry_price = risk_profile.get('entry_price', smc_data.get('key_level', 1.0))
        risk_ratio = risk_profile.get('risk_ratio', 2.0)

        # Ensure confidence is between 0 and 1
        if confidence > 1:
            confidence = confidence / 100

        # Calculate base TP distance based on confidence and momentum
        price_multiplier = (momentum * confidence) if (momentum * confidence) > 0.01 else 0.01
        
        # Use SMC zones to anchor TP prediction
        if bias == 'bullish':
            order_block = smc_data.get('order_block', entry_price)
            liquidity_zone = smc_data.get('liquidity_zone', entry_price)
            
            # Choose the higher value for bullish bias
            if isinstance(order_block, dict) and 'zone' in order_block:
                # Parse zone string like "183.20 -- 184.75"
                zone_parts = order_block['zone'].split('--')
                order_block_price = float(zone_parts[-1].strip()) if len(zone_parts) > 1 else entry_price
            else:
                order_block_price = float(order_block) if order_block else entry_price
                
            base_tp = max(order_block_price, liquidity_zone, entry_price)
            tp_distance = abs(base_tp - entry_price) * price_multiplier
            tp_level = base_tp + tp_distance
            
            sl_level = entry_price - (tp_distance / risk_ratio)
            
        elif bias == 'bearish':
            order_block = smc_data.get('order_block', entry_price)
            liquidity_zone = smc_data.get('liquidity_zone', entry_price)
            
            # Parse order block if it's a dict with zone
            if isinstance(order_block, dict) and 'zone' in order_block:
                zone_parts = order_block['zone'].split('--')
                order_block_price = float(zone_parts[0].strip()) if len(zone_parts) > 1 else entry_price
            else:
                order_block_price = float(order_block) if order_block else entry_price
                
            base_tp = min(order_block_price, liquidity_zone, entry_price)
            tp_distance = abs(entry_price - base_tp) * price_multiplier
            tp_level = base_tp - tp_distance
            
            sl_level = entry_price + (tp_distance / risk_ratio)
            
        else:  # neutral
            tp_level = entry_price
            sl_level = entry_price

        # Create multiple TP levels
        tp_levels = []
        if bias != 'neutral':
            if bias == 'bullish':
                tp_levels = [
                    round(entry_price + (tp_level - entry_price) * 0.5, 4),  # 50% to TP
                    round(tp_level, 4)  # Full TP
                ]
            else:  # bearish
                tp_levels = [
                    round(entry_price - (entry_price - tp_level) * 0.5, 4),  # 50% to TP
                    round(tp_level, 4)  # Full TP
                ]
        else:
            tp_levels = [entry_price]

        # Format TP zone
        if len(tp_levels) >= 2:
            tp_zone = f"{tp_levels[0]} -- {tp_levels[-1]}"
        else:
            tp_zone = str(tp_levels[0]) if tp_levels else str(entry_price)

        return {
            'bias': bias,
            'tp_level': round(tp_level, 4),
            'sl_level': round(sl_level, 4),
            'tp_zone': tp_zone,
            'levels': tp_levels,
            'confidence': confidence,
            'source': 'tp_engine'
        }

    except Exception as e:
        print(f"[TP Engine] Error: {e}")
        entry_price = risk_profile.get('entry_price', 1.0)
        return {
            'tp_level': entry_price,
            'sl_level': entry_price,
            'tp_zone': str(entry_price),
            'levels': [entry_price],
            'bias': 'neutral',
            'confidence': 0.0,
            'error': str(e)
        }
