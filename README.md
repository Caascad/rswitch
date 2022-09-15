# How to create poetry files

```sh
nix-shell -p gcc poetry
rm poetry.lock pyproject.toml
poetry init -n --python "^3.9"
poetry add $(cat requirements.txt)

cat >>pyproject.toml<<"EOF"

[tool.poetry.scripts]
rswitch = "rswitch:main"
EOF

# Set project version
poetry version <some_version>

```
