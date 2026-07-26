# Makefile for fast_indicators C++ pybind11 module
# Uses python312-dev environment

PYTHON := $(HOME)/python312-dev/bin/python3.12
PYBIND11_INCLUDE := $(shell $(PYTHON) -c "import pybind11; print(pybind11.get_include())" 2>/dev/null)
PYTHON_INCLUDE := $(shell $(PYTHON) -c "from sysconfig import get_path; print(get_path('include'))" 2>/dev/null)
PYTHON_EXT_SUFFIX := $(shell $(PYTHON) -c "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX'))")
SITE_PACKAGES := $(shell $(PYTHON) -c "import site; print(site.getsitepackages()[0])" 2>/dev/null)

# Fallback include path: check multiple python versions, prefer the host python version
PYTHON_INCLUDE_FALLBACK := $(shell ls -d /usr/include/python3.14 /usr/include/python3.12 /usr/include/python3.11 /usr/include/python3.10 2>/dev/null | head -1)
# Also check for python3.14 specifically since that's what's on the system
HOST_PYTHON_INCLUDE := /usr/include/python3.14

CXX := g++
CXXFLAGS := -O3 -Wall -shared -std=c++17 -fPIC
INCLUDES := -I$(PYTHON_INCLUDE) -I$(PYTHON_INCLUDE_FALLBACK) -I$(HOST_PYTHON_INCLUDE) -I$(PYBIND11_INCLUDE)

TARGET := fast_indicators$(PYTHON_EXT_SUFFIX)
SOURCES := indicators.cpp bindings.cpp

all: $(TARGET)
	@echo "✅ Built $(TARGET)"
	@echo "📦 Copying to $(SITE_PACKAGES)/"
	cp $(TARGET) $(SITE_PACKAGES)/$(TARGET)
	@echo "✅ Installed to site-packages"

$(TARGET): $(SOURCES) indicators.h
	$(CXX) $(CXXFLAGS) $(INCLUDES) $(SOURCES) -o $(TARGET)

install: $(TARGET)
	cp $(TARGET) ../$(TARGET)
	@echo "✅ Installed to engine/ directory"

clean:
	rm -f $(TARGET) *.o

.PHONY: all install clean
