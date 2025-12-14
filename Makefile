
PYTHON := $(shell if [ -x ".venv/bin/python" ]; then echo ".venv/bin/python"; elif command -v python3 >/dev/null 2>&1; then echo "python3"; else echo "python"; fi)
PYINSTALLER_DIST := dist
PYINSTALLER_NAME := bespokeasm

.PHONY: tests clean flake8 pyinstaller pipx-wheel

tests:
	PYTHONPATH=./src:${PYTHONPATH} $(PYTHON) -m unittest discover . -v

clean:
	find . -name '*.pyc' -delete
	find . -name '__pycache__' -delete
	rm -Rf ./build
	rm -Rf ./bespokeasm.egg-info
	rm -Rf ./dist/

flake8:
	flake8 ./src/ ./test/ --count --max-line-length=127 --statistics

pyinstaller:
	$(PYTHON) -m PyInstaller --onefile --name $(PYINSTALLER_NAME) \
		--distpath $(PYINSTALLER_DIST) --collect-all bespokeasm \
		src/bespokeasm/__main__.py
	VERSION=$$($(PYTHON) -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"); \
	OS_NAME=$$(uname -s); \
	case "$$OS_NAME" in \
		Linux*) PLATFORM=linux ;; \
		Darwin*) PLATFORM=macos ;; \
		MINGW*|MSYS*|CYGWIN*) PLATFORM=windows ;; \
		*) PLATFORM=unknown ;; \
	esac; \
	ARCH=$$(uname -m); \
	EXT=""; \
	if [ "$$PLATFORM" = "windows" ]; then EXT=".exe"; fi; \
	SRC="$(PYINSTALLER_DIST)/$(PYINSTALLER_NAME)$${EXT}"; \
	DEST="$(PYINSTALLER_DIST)/$(PYINSTALLER_NAME)-$${VERSION}-$${PLATFORM}-$${ARCH}$${EXT}"; \
	mv "$$SRC" "$$DEST"

pipx-wheel:
	$(PYTHON) -m build --wheel

# NOTE: For running GitHub Actions locally with `make act-release`,
# install `act` (https://nektosact.com/) and Docker (engine/daemon).
act-release:
	# Use --bind so build artifacts persist to the host ./dist directory
	act release --bind \
		-W .github/workflows/release-artifacts.yml \
		-j wheel -j pyinstaller-linux \
		-P ubuntu-latest=ghcr.io/catthehacker/ubuntu:act-22.04
