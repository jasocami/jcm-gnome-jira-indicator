# Jira Indicator: developer commands (test, dev link, package). Users only need ./install.sh.
# Run "make" or "make help" to list the targets.

NAME       := jcm-gnome-jira-indicator
UUID       := $(shell python3 -c "import json; print(json.load(open('metadata.json'))['uuid'])")
VERSION    := $(shell python3 -c "import json; print(json.load(open('metadata.json'))['version-name'])")
EXT_DIR    := $(HOME)/.local/share/gnome-shell/extensions/$(UUID)
CONFIG_DIR := $(or $(XDG_CONFIG_HOME),$(HOME)/.config)/$(NAME)
STATE_DIR  := $(or $(XDG_STATE_HOME),$(HOME)/.local/state)/$(NAME)
FILES      := metadata.json extension.js fetch.py config.example.ini MANUAL.md
ZIP        := dist/$(UUID).shell-extension.zip

.DEFAULT_GOAL := help
.PHONY: help check install dev config enable disable uninstall test fetch pack

help: ## List the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

check: ## Check that the tools the app needs are installed
	@command -v python3 >/dev/null || { echo "Missing python3"; exit 1; }
	@command -v gnome-extensions >/dev/null || { echo "Missing gnome-extensions: is this a GNOME desktop?"; exit 1; }
	@echo "All tools found."

install: ## Install the extension for your user (same as ./install.sh)
	@./install.sh

dev: check config ## Link this folder instead of copying (for development)
	@rm -rf "$(EXT_DIR)"
	@mkdir -p "$(dir $(EXT_DIR))"
	@ln -s "$(CURDIR)" "$(EXT_DIR)"
	@echo "Linked $(EXT_DIR) -> $(CURDIR)"

config: ## Create your config from the example (never overwrites an existing one)
	@mkdir -p "$(CONFIG_DIR)"
	@if [ -f "$(CONFIG_DIR)/config.ini" ]; then \
		echo "Config already exists, left as is: $(CONFIG_DIR)/config.ini"; \
	else \
		cp config.example.ini "$(CONFIG_DIR)/config.ini" && chmod 600 "$(CONFIG_DIR)/config.ini"; \
		echo "Created $(CONFIG_DIR)/config.ini: fill in domain, email and token"; \
	fi

enable: ## Turn the extension on
	gnome-extensions enable $(UUID)

disable: ## Turn the extension off
	gnome-extensions disable $(UUID)

uninstall: ## Remove the extension and its state (keeps your config)
	-@gnome-extensions disable $(UUID) 2>/dev/null
	@rm -rf "$(EXT_DIR)" "$(STATE_DIR)"
	@echo "Removed. Your config is still in $(CONFIG_DIR); delete it by hand if you want."

test: ## Run the unit tests (no network)
	python3 -m unittest discover -s tests -v

fetch: ## Call Jira for real with your config, and show the JSON
	python3 fetch.py | python3 -m json.tool

pack: ## Build the release zip in dist/
	@mkdir -p dist
	@rm -f "$(ZIP)"
	@zip -q -r "$(ZIP)" $(FILES)
	@echo "Built $(ZIP) ($(NAME) $(VERSION))"
