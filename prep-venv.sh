#!/bin/bash

set -euo pipefail

venvpath=.venv
python -m venv $venvpath && source $venvpath/bin/activate && pip install -r ./app/requirements.txt

echo
echo "✅ Python environment for pgtester app prepared in: $venvpath/"
