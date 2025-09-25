# Makefile for LCM Convoy Message Monitor

# Compiler and flags
CC = gcc
CFLAGS = -Wall -Wextra -std=c99 -g -I/opt/homebrew/include -I/usr/local/include $(shell pkg-config --cflags glib-2.0 2>/dev/null || echo "")
LDFLAGS = -L/opt/homebrew/lib -L/usr/local/lib -llcm $(shell pkg-config --libs glib-2.0 2>/dev/null || echo "-lglib-2.0")

# Directories
LCM_GEN_DIR = lcm_generated
SRC_DIR = .
BUILD_DIR = build

# LCM schema file
LCM_SCHEMA = convoy_messages.lcm

# Generated files from LCM schema
LCM_GENERATED_C = $(LCM_GEN_DIR)/convoy_heartbeat_t.c \
                  $(LCM_GEN_DIR)/convoy_warning_t.c \
                  $(LCM_GEN_DIR)/convoy_mode_t.c \
                  $(LCM_GEN_DIR)/convoy_status_t.c

LCM_GENERATED_H = $(LCM_GEN_DIR)/convoy_heartbeat_t.h \
                  $(LCM_GEN_DIR)/convoy_warning_t.h \
                  $(LCM_GEN_DIR)/convoy_mode_t.h \
                  $(LCM_GEN_DIR)/convoy_status_t.h

# Object files
LCM_OBJECTS = $(LCM_GENERATED_C:.c=.o)
MONITOR_OBJECTS = $(BUILD_DIR)/lcm_monitor.o

# Target executable
TARGET = lcm_monitor

# Default target
all: $(TARGET)

# Create build directory
$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

# Create LCM generated directory
$(LCM_GEN_DIR):
	mkdir -p $(LCM_GEN_DIR)

# Generate LCM bindings
$(LCM_GENERATED_C) $(LCM_GENERATED_H): $(LCM_SCHEMA) | $(LCM_GEN_DIR)
	@echo "Generating LCM bindings..."
	lcm-gen -c --c-cpath $(LCM_GEN_DIR) --c-hpath $(LCM_GEN_DIR) $(LCM_SCHEMA)

# Generate Python bindings (optional)
python-bindings: $(LCM_SCHEMA) | $(LCM_GEN_DIR)
	@echo "Generating Python LCM bindings..."
	lcm-gen -p --ppath $(LCM_GEN_DIR) $(LCM_SCHEMA)

# Compile LCM generated files
$(LCM_GEN_DIR)/%.o: $(LCM_GEN_DIR)/%.c $(LCM_GEN_DIR)/%.h
	@echo "Compiling $<..."
	$(CC) $(CFLAGS) -I$(LCM_GEN_DIR) -c $< -o $@

# Compile main program
$(BUILD_DIR)/lcm_monitor.o: lcm_monitor.c $(LCM_GENERATED_H) | $(BUILD_DIR)
	@echo "Compiling lcm_monitor.c..."
	$(CC) $(CFLAGS) -I$(LCM_GEN_DIR) -c lcm_monitor.c -o $@

# Link the final executable
$(TARGET): $(LCM_OBJECTS) $(MONITOR_OBJECTS)
	@echo "Linking $(TARGET)..."
	$(CC) $(LCM_OBJECTS) $(MONITOR_OBJECTS) $(LDFLAGS) -o $(TARGET)
	@echo "Build complete! Run with: ./$(TARGET)"

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf $(BUILD_DIR) $(LCM_GEN_DIR) $(TARGET)

# Install dependencies (Ubuntu/Debian)
install-deps-ubuntu:
	sudo apt-get update
	sudo apt-get install -y build-essential pkg-config liblcm-dev libglib2.0-dev

# Install dependencies (macOS with Homebrew)
install-deps-macos:
	brew install lcm glib pkg-config

# Test the installation
test: $(TARGET)
	@echo "Testing LCM installation..."
	@echo "Starting lcm-spy in background (if available)..."
	@if command -v lcm-spy >/dev/null 2>&1; then \
		echo "You can run 'lcm-spy' in another terminal to see LCM traffic graphically"; \
	fi
	@echo "Starting $(TARGET) - press Ctrl+C to stop"
	./$(TARGET)

# Show help
help:
	@echo "Available targets:"
	@echo "  all                Build the LCM monitor program"
	@echo "  python-bindings    Generate Python LCM bindings"
	@echo "  clean              Remove build artifacts"
	@echo "  install-deps-ubuntu Install dependencies on Ubuntu/Debian"
	@echo "  install-deps-macos Install dependencies on macOS"
	@echo "  test               Build and run the monitor"
	@echo "  help               Show this help"
	@echo ""
	@echo "Usage after building:"
	@echo "  ./$(TARGET)        Monitor all channels"
	@echo "  ./$(TARGET) -c HEARTBEAT  Monitor only heartbeat messages"
	@echo "  ./$(TARGET) -h     Show program help"

.PHONY: all clean install-deps-ubuntu install-deps-macos test help python-bindings