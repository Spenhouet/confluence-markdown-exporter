#!/bin/bash
cd $(dirname -- "$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )") # cd to workspace folder

source bin/activate-venv.sh

if pip install -r requirements.txt -r requirements-dev.txt; then
    echo -e "\nPip packages were installed successfully."
else
    echo -e "\nPip packages were not installed. See the error message above for more details."
fi
