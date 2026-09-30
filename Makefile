# AWGCTL_LANG: build language (en|ru). Named AWGCTL_LANG, not LANG, because
# LANG is a standard shell/locale env var and would be overridden by it.
PREFIX      ?= /usr/local
AWGCTL_LANG ?= en
BUILD_DIR    = build
TARGET       = $(BUILD_DIR)/awgctl

.PHONY: all build test install uninstall clean

all: build

test:
	# Local automated tests only; server_smoke.py is optional and manual.
	python3 -m unittest discover -s tests -p 'test_*.py' -v

build:
	@mkdir -p $(BUILD_DIR)
	python3 build.py --lang=$(AWGCTL_LANG) --output=$(TARGET)

install: build
	install -Dm755 $(TARGET) $(DESTDIR)$(PREFIX)/bin/awgctl

uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/awgctl

clean:
	rm -rf $(BUILD_DIR)
