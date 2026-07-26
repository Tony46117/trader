#include "indicators.h"
#include <cmath>
#include <algorithm>
#include <stdexcept>
#include <numeric>

namespace trader {

// ── Internal helpers ──────────────────────────────────────────────────

static double nan_value() {
    return std::numeric_limits<double>::quiet_NaN();
}

static bool is_nan(double val) {
    return std::isnan(val);
}

static std::vector<double> compute_ema_impl(const std::vector<double>& data, int period) {
    std::vector<double> result(data.size(), nan_value());
    if (data.empty() || period <= 0 || (int)data.size() < period) return result;

    double multiplier = 2.0 / (period + 1.0);
    double ema = data[0];
    result[0] = ema;

    for (size_t i = 1; i < data.size(); ++i) {
        ema = (data[i] - ema) * multiplier + ema;
        result[i] = ema;
    }
    return result;
}

static std::vector<double> compute_sma_impl(const std::vector<double>& data, int period) {
    std::vector<double> result(data.size(), nan_value());
    if (data.empty() || period <= 0 || (int)data.size() < period) return result;

    double sum = 0.0;
    for (int i = 0; i < period && i < (int)data.size(); ++i) {
        sum += data[i];
    }
    result[period - 1] = sum / period;

    for (size_t i = (size_t)period; i < data.size(); ++i) {
        sum = sum - data[i - period] + data[i];
        result[i] = sum / period;
    }
    return result;
}

// ── Public API ────────────────────────────────────────────────────────

std::vector<double> compute_rsi(const std::vector<double>& data, int period) {
    std::vector<double> result(data.size(), nan_value());
    if ((int)data.size() <= period) return result;

    std::vector<double> gains(data.size(), 0.0);
    std::vector<double> losses(data.size(), 0.0);

    for (size_t i = 1; i < data.size(); ++i) {
        double diff = data[i] - data[i - 1];
        if (diff > 0) {
            gains[i] = diff;
        } else {
            losses[i] = -diff;
        }
    }

    // First average
    double avg_gain = 0.0, avg_loss = 0.0;
    for (int i = 1; i <= period; ++i) {
        avg_gain += gains[i];
        avg_loss += losses[i];
    }
    avg_gain /= period;
    avg_loss /= period;

    double rs = (avg_loss == 0.0) ? 100.0 : avg_gain / avg_loss;
    result[period] = 100.0 - (100.0 / (1.0 + rs));

    // Subsequent values using smoothed method
    for (size_t i = (size_t)period + 1; i < data.size(); ++i) {
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period;
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period;
        rs = (avg_loss == 0.0) ? 100.0 : avg_gain / avg_loss;
        result[i] = 100.0 - (100.0 / (1.0 + rs));
    }

    return result;
}

MACDResult compute_macd(const std::vector<double>& data, int fast, int slow, int signal) {
    MACDResult result;
    if ((int)data.size() < slow + signal) return result;

    auto ema_fast = compute_ema_impl(data, fast);
    auto ema_slow = compute_ema_impl(data, slow);

    result.macd_line.resize(data.size(), nan_value());
    for (size_t i = 0; i < data.size(); ++i) {
        if (!is_nan(ema_fast[i]) && !is_nan(ema_slow[i])) {
            result.macd_line[i] = ema_fast[i] - ema_slow[i];
        }
    }

    // Compute signal line as EMA of MACD line
    std::vector<double> macd_clean(data.size(), 0.0);
    size_t start_idx = 0;
    for (size_t i = 0; i < data.size(); ++i) {
        if (!is_nan(result.macd_line[i])) {
            macd_clean[i] = result.macd_line[i];
            if (start_idx == 0) start_idx = i;
        }
    }

    if (start_idx > 0) {
        result.signal_line = compute_ema_impl(macd_clean, signal);
    }

    result.histogram.resize(data.size(), nan_value());
    for (size_t i = 0; i < data.size(); ++i) {
        if (!is_nan(result.macd_line[i]) && !is_nan(result.signal_line[i])) {
            result.histogram[i] = result.macd_line[i] - result.signal_line[i];
        }
    }

    return result;
}

BBResult compute_bollinger_bands(const std::vector<double>& data, int period, double std_dev) {
    BBResult result;
    result.upper.resize(data.size(), nan_value());
    result.middle.resize(data.size(), nan_value());
    result.lower.resize(data.size(), nan_value());

    if ((int)data.size() < period) return result;

    auto sma = compute_sma_impl(data, period);

    for (size_t i = (size_t)(period - 1); i < data.size(); ++i) {
        double mean = sma[i];
        double sq_sum = 0.0;
        for (size_t j = i - (size_t)period + 1; j <= i; ++j) {
            sq_sum += (data[j] - mean) * (data[j] - mean);
        }
        double std = std::sqrt(sq_sum / period);
        result.middle[i] = mean;
        result.upper[i] = mean + (std * std_dev);
        result.lower[i] = mean - (std * std_dev);
    }

    return result;
}

std::vector<double> compute_atr(const std::vector<double>& high,
                                 const std::vector<double>& low,
                                 const std::vector<double>& close,
                                 int period) {
    std::vector<double> result(high.size(), nan_value());
    if (high.size() != low.size() || high.size() != close.size()) return result;
    if ((int)high.size() <= period) return result;

    std::vector<double> tr(high.size(), 0.0);
    tr[0] = high[0] - low[0];

    for (size_t i = 1; i < high.size(); ++i) {
        double hl = high[i] - low[i];
        double hc = std::abs(high[i] - close[i - 1]);
        double lc = std::abs(low[i] - close[i - 1]);
        tr[i] = std::max({hl, hc, lc});
    }

    // First ATR is simple mean
    double atr_val = 0.0;
    for (int i = 1; i <= period; ++i) {
        atr_val += tr[i];
    }
    atr_val /= period;
    result[period] = atr_val;

    // Smoothed ATR
    for (size_t i = (size_t)period + 1; i < high.size(); ++i) {
        atr_val = ((atr_val * (period - 1)) + tr[i]) / period;
        result[i] = atr_val;
    }

    return result;
}

std::vector<double> compute_ema(const std::vector<double>& data, int period) {
    return compute_ema_impl(data, period);
}

std::vector<double> compute_sma(const std::vector<double>& data, int period) {
    return compute_sma_impl(data, period);
}

StochRSIResult compute_stoch_rsi(const std::vector<double>& data, int period,
                                  int k_period, int d_period) {
    StochRSIResult result;
    auto rsi = compute_rsi(data, period);

    result.k.resize(data.size(), nan_value());
    result.d.resize(data.size(), nan_value());

    for (size_t i = (size_t)period; i < data.size(); ++i) {
        if (is_nan(rsi[i])) continue;

        double min_rsi = rsi[i];
        double max_rsi = rsi[i];
        for (size_t j = i - (size_t)period + 1; j <= i; ++j) {
            if (!is_nan(rsi[j])) {
                min_rsi = std::min(min_rsi, rsi[j]);
                max_rsi = std::max(max_rsi, rsi[j]);
            }
        }

        double range = max_rsi - min_rsi;
        if (range > 0.0) {
            result.k[i] = ((rsi[i] - min_rsi) / range) * 100.0;
        } else {
            result.k[i] = 50.0;
        }
    }

    // Smooth K to get D
    if (k_period > 1) {
        for (size_t i = (size_t)(period + k_period - 1); i < data.size(); ++i) {
            double sum = 0.0;
            int count = 0;
            for (size_t j = i - (size_t)k_period + 1; j <= i; ++j) {
                if (!is_nan(result.k[j])) {
                    sum += result.k[j];
                    count++;
                }
            }
            if (count > 0) {
                result.d[i] = sum / count;
            }
        }
    } else {
        result.d = result.k;
    }

    return result;
}

std::vector<double> rolling_correlation(const std::vector<double>& a,
                                         const std::vector<double>& b,
                                         int window) {
    std::vector<double> result(a.size(), nan_value());
    if (a.size() != b.size() || (int)a.size() < window) return result;

    for (size_t i = (size_t)(window - 1); i < a.size(); ++i) {
        double sum_a = 0.0, sum_b = 0.0;
        double sum_aa = 0.0, sum_bb = 0.0, sum_ab = 0.0;

        for (size_t j = i - (size_t)window + 1; j <= i; ++j) {
            sum_a += a[j];
            sum_b += b[j];
            sum_aa += a[j] * a[j];
            sum_bb += b[j] * b[j];
            sum_ab += a[j] * b[j];
        }

        double n = (double)window;
        double num = n * sum_ab - sum_a * sum_b;
        double den_a = n * sum_aa - sum_a * sum_a;
        double den_b = n * sum_bb - sum_b * sum_b;
        double den = std::sqrt(den_a * den_b);

        result[i] = (den > 0.0) ? (num / den) : 0.0;
    }

    return result;
}

} // namespace trader
