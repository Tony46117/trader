#ifndef TRADER_INDICATORS_H
#define TRADER_INDICATORS_H

#include <vector>
#include <string>

namespace trader {

/**
 * Compute RSI (Relative Strength Index)
 * @param data Input price series
 * @param period RSI period (default 14)
 * @return RSI values (same length, first `period` values are NaN)
 */
std::vector<double> compute_rsi(const std::vector<double>& data, int period = 14);

/**
 * Compute MACD (Moving Average Convergence Divergence)
 * @param data Input price series
 * @param fast Fast EMA period
 * @param slow Slow EMA period
 * @param signal Signal EMA period
 * @return Tuple of {macd_line, signal_line, histogram}
 */
struct MACDResult {
    std::vector<double> macd_line;
    std::vector<double> signal_line;
    std::vector<double> histogram;
};
MACDResult compute_macd(const std::vector<double>& data, int fast = 12, int slow = 26, int signal = 9);

/**
 * Compute Bollinger Bands
 * @param data Input price series
 * @param period Rolling window period
 * @param std_dev Standard deviation multiplier
 * @return Tuple of {upper, middle, lower}
 */
struct BBResult {
    std::vector<double> upper;
    std::vector<double> middle;
    std::vector<double> lower;
};
BBResult compute_bollinger_bands(const std::vector<double>& data, int period = 20, double std_dev = 2.0);

/**
 * Compute ATR (Average True Range)
 * @param high High prices
 * @param low Low prices
 * @param close Close prices
 * @param period ATR period
 * @return ATR values
 */
std::vector<double> compute_atr(const std::vector<double>& high,
                                 const std::vector<double>& low,
                                 const std::vector<double>& close,
                                 int period = 14);

/**
 * Compute EMA (Exponential Moving Average)
 * @param data Input price series
 * @param period EMA period
 * @return EMA values
 */
std::vector<double> compute_ema(const std::vector<double>& data, int period);

/**
 * Compute SMA (Simple Moving Average)
 * @param data Input price series
 * @param period SMA period
 * @return SMA values
 */
std::vector<double> compute_sma(const std::vector<double>& data, int period);

/**
 * Compute Stochastic RSI
 * @param data Input price series
 * @param period RSI period
 * @param k_period K smoothing period
 * @param d_period D smoothing period
 * @return Tuple of {K, D}
 */
struct StochRSIResult {
    std::vector<double> k;
    std::vector<double> d;
};
StochRSIResult compute_stoch_rsi(const std::vector<double>& data, int period = 14,
                                  int k_period = 3, int d_period = 3);

/**
 * Compute rolling correlation between two series
 */
std::vector<double> rolling_correlation(const std::vector<double>& a,
                                         const std::vector<double>& b,
                                         int window = 20);

} // namespace trader

#endif // TRADER_INDICATORS_H
