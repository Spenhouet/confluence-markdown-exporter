# Contributing

Any contribution is welcome.

## How do I get set up?

### Install jq

```bash
sudo apt-get install jq
```

### Install pyenv

This guide is based on https://github.com/pyenv/pyenv#installation. In case this guide no longer works, see if there was a change to the linked guide.

#### Install Required Packages

There are some packages required for pyenv to work properly. Please install them:

```bash
sudo apt-get install gcc make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
```

#### Load pyenv Source from GitHub

```bash
git clone https://github.com/pyenv/pyenv.git $HOME/.pyenv
```

#### Add pyenv paths to `.profile` and `.bashrc`

Execute the following lines (copy and paste into your terminal):

```bash
sed -Ei -e '/^([^#]|$)/ {a \
export PYENV_ROOT="$HOME/.pyenv"
a \
export PATH="$PYENV_ROOT/bin:$PATH"
a \
' -e ':a' -e '$!{n;ba};}' ~/.profile
echo 'eval "$(pyenv init --path)"' >> ~/.profile
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
```

#### Restart the Shell

```bash
source $HOME/.profile
source $HOME/.bashrc
```

#### Check out pyenv-virtualenv into plugin directory

```bash
git clone https://github.com/pyenv/pyenv-virtualenv.git $(pyenv root)/plugins/pyenv-virtualenv
```

Add pyenv virtualenv-init to your shell to enable auto-activation of virtualenvs. This is entirely optional but pretty useful. See "Activate virtualenv" below.

```bash
echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc
exec "$SHELL"
```

### Install Virtual Environment

Run `./bin/venv.sh`.
