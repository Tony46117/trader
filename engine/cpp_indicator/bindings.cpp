#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "indicators.h"

namespace py = pybind11;

PYBIND11_MODULE(fast_indicators, m) {
    m.doc() = "High-speed technical indicators for trading framework";

    // MACDResult binding
    py::class_<trader::MACDResult>(m, "MACDResult")
        .def(py::init<>())
        .def_readwrite("macd_line", &trader::MACDResult::macd_line)
        .def_readwrite("signal_line", &trader::MACDResult::signal_line)
        .def_readwrite("histogram", &trader::MACDResult::histogram);

    // BBResult binding
    py::class_<trader::BBResult>(m, "BBResult")
        .def(py::init<>())
        .def_readwrite("upper", &trader::BBResult::upper)
        .def_readwrite("middle", &trader::BBResult::middle)
        .def_readwrite("lower", &trader::BBResult::lower);

    // StochRSIResult binding
    py::class_<trader::StochRSIResult>(m, "StochRSIResult")
        .def(py::init<>())
        .def_readwrite("k", &trader::StochRSIResult::k)
        .def_readwrite("d", &trader::StochRSIResult::d);

    // Functions
    m.def("compute_rsi", &trader::compute_rsi,
          py::arg("data"), py::arg("period") = 14,
          "Compute Relative Strength Index");

    m.def("compute_macd", &trader::compute_macd,
          py::arg("data"), py::arg("fast") = 12, py::arg("slow") = 26, py::arg("signal") = 9,
          "Compute MACD indicator");

    m.def("compute_bollinger_bands", &trader::compute_bollinger_bands,
          py::arg("data"), py::arg("period") = 20, py::arg("std_dev") = 2.0,
          "Compute Bollinger Bands");

    m.def("compute_atr", &trader::compute_atr,
          py::arg("high"), py::arg("low"), py::arg("close"), py::arg("period") = 14,
          "Compute Average True Range");

    m.def("compute_ema", &trader::compute_ema,
          py::arg("data"), py::arg("period"),
          "Compute Exponential Moving Average");

    m.def("compute_sma", &trader::compute_sma,
          py::arg("data"), py::arg("period"),
          "Compute Simple Moving Average");

    m.def("compute_stoch_rsi", &trader::compute_stoch_rsi,
          py::arg("data"), py::arg("period") = 14, py::arg("k_period") = 3, py::arg("d_period") = 3,
          "Compute Stochastic RSI");

    m.def("rolling_correlation", &trader::rolling_correlation,
          py::arg("a"), py::arg("b"), py::arg("window") = 20,
          "Compute rolling correlation between two series");
}
