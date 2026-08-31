PREFIX ?= /usr/local
LANG   ?= en
BUILD_DIR = build
TARGET = $(BUILD_DIR)/awgctl

.PHONY: all build install uninstall clean

all: build

build:
	@mkdir -p $(BUILD_DIR)
	python3 build.py --lang=$(LANG) --output=$(TARGET)

install: build
	install -Dm755 $(TARGET) $(DESTDIR)$(PREFIX)/bin/awgctl

uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/awgctl

clean:
	rm -rf $(BUILD_DIR)
