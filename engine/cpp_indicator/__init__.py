"""
C++ Accelerated Indicators — pybind11 bindings.

To compile (requires python3.12-devel):
    cd engine/cpp_indicator && make

Falls back gracefully if the module is not compiled.
"""
import sys
import os

_module_path = os.path.join(os.path.dirname(__file__), "fast_indicators.so")

HAS_CPP = False
compute_rsi = None
compute_macd = None
compute_bollinger_bands = None
compute_atr = None
compute_stoch_rsi = None
compute_ema = None
compute_sma = None

# Try loading the C++ module
if os.path.exists(_module_path):
    import importlib.util
    try:
        spec = importlib.util.spec_from_file_location("fast_indicators", _module_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            sys.modules["fast_indicators"] = mod
            spec.loader.exec_module(mod)

            compute_rsi = mod.compute_rsi
            compute_macd = mod.compute_macd
            compute_bollinger_bands = mod.compute_bollinger_bands
            compute_atr = mod.compute_atr
            compute_stoch_rsi = mod.compute_stoch_rsi
            compute_ema = mod.compute_ema
            compute_sma = mod.compute_sma
            HAS_CPP = True
    except Exception:
        pass

if not HAS_CPP:
    # Also try normal import
    try:
        import fast_indicators as _fi
        compute_rsi = _fi.compute_rsi
        compute_macd = _fi.compute_macd
        compute_bollinger_bands = _fi.compute_bollinger_bands
        compute_atr = _fi.compute_atr
        compute_stoch_rsi = _fi.compute_stoch_rsi
        compute_ema = _fi.compute_ema
        compute_sma = _fi.compute_sma
        HAS_CPP = True
    except ImportError:
        pass
