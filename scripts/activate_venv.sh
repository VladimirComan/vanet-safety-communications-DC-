#!/usr/bin/env bash
# Source this file to activate the VANET Python environment
# Usage: source activate_venv.sh

VENV_DIR="/opt/vanet-venv"

if [[ -d "${VENV_DIR}" ]]; then
    source "${VENV_DIR}/bin/activate"
    echo "VANET Python environment activated."
    echo "Python: $(which python)"
    echo "Pip: $(which pip)"
else
    echo "Error: Virtual environment not found at ${VENV_DIR}"
    echo "Run install_prerequisites.sh first."
fi
