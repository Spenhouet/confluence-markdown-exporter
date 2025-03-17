#!/bin/bash
eval "$(pyenv init -)" # initialize pyenv for current shell
eval "$(pyenv virtualenv-init -)" # initialize pyenv-virtualenv for current shell

VENV_NAME="confluence-markdown-exporter"
PYTHON_VERSION=$(<.python-version)

cd $(dirname -- "$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )") # cd to workspace folder
pyenv install -s $PYTHON_VERSION
pyenv virtualenv-delete -f $VENV_NAME

if pyenv virtualenv $PYTHON_VERSION $VENV_NAME; then
    pyenv shell $VENV_NAME # activate virtualenv for current shell
    bin/pip.sh
    bin/setup.sh
    echo -e "\nVirtualenv '$VENV_NAME' was created successfully. Follow these instructions to activate it:"
    echo -e "   1) Press Ctrl + Shift + P in VS Code and choose 'Python: Select Interpreter'."
    echo -e "   2) Choose 'Python: Select Interpreter'."
    echo -e "   3) Choose: 'Use Python from python.defaultInterpreterPath setting'."
    echo -e "   4) Reopen your VS Code terminals or restart VS code."
else
    echo -e "\nPyenv does not seem to be installed."
fi
