#!/bin/bash

VENV_NAME="confluence-markdown-exporter"

eval "$(pyenv init -)" # initialize pyenv for current shell
eval "$(pyenv virtualenv-init -)" # initialize pyenv-virtualenv for current shell

if ! pyenv shell $VENV_NAME; then # activate virtualenv for current shell
    echo "Run bin/venv.sh first."
    exit 1
fi