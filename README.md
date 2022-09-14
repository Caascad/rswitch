# How to create poetry files

```sh
nix-shell -p python39Packages.virtualenv gcc poetry
virtualenv /tmp/venv
source /tmp/venv/bin/activate
pip install -r requirements.txt
rm poetry.lock pyproject.toml
poetry init -n --python "^3.9"
pip freeze | sed 's/ @.*$//' | sed '/poetry/d' | sed '/virtualenv/d' | sed '/keyring/d' | xargs poetry add

cat >>pyproject.toml<<"EOF"

[tool.poetry.scripts]
rswitch = "rswitch:main"
EOF

# Set project version
poetry version <some_version>

deactivate
rm -rf /tmp/venv
```
