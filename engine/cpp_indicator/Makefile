# TRADER — C++ Indicators Makefile
#
# REQUIREMENTS:
#   - python3.12-venv at $(HOME)/python312-dev
#   - pybind11 installed in the venv
#   - python3.12-devel (Fedora: sudo dnf install python3.12-devel)
#
# Usage:
#   make PYTHON=~/python312-dev/bin/python3.12

PYTHON := $(HOME)/python312-dev/bin/python3.12

PYBIND11_INCLUDE := $(shell $(PYTHON) -c "import pybind11; print(pybind11.get_include())" 2>/dev/null)
PYTHON_INCLUDE := $(shell $(PYTHON) -c "from sysconfig import get_path; print(get_path('include'))" 2>/dev/null)
PYTHON_EXT := $(shell $(PYTHON) -c "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX'))")
SITE_PKG := $(shell $(PYTHON) -c "import site; print(site.getsitepackages()[0])" 2>/dev/null)

CXX := g++
CXXFLAGS := -O3 -Wall -shared -std=c++17 -fPIC
INCLUDES := -I$(PYTHON_INCLUDE) -I$(PYBIND11_INCLUDE)

TARGET := fast_indicators$(PYTHON_EXT)
SOURCES := indicators.cpp bindings.cpp

all: $(TARGET)
	@echo "✅ Built $(TARGET)"
	cp $(TARGET) $(SITE_PKG)/$(TARGET) 2>/dev/null; cp $(TARGET) ../$(TARGET) 2>/dev/null
	@echo "✅ Installed"

$(TARGET): $(SOURCES) indicators.h
	$(CXX) $(CXXFLAGS) $(INCLUDES) $(SOURCES) -o $(TARGET)

install: $(TARGET)
	cp $(TARGET) ../$(TARGET)
	@echo "✅ Installed to engine/"

clean:
	rm -f $(TARGET) *.o ../$(TARGET)

.PHONY: all install clean
