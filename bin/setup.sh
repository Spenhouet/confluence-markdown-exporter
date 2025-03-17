#!/bin/bash
source bin/activate-venv.sh

RECOMMENDED_VSCODE_EXTENSIONS=$(grep -v '//' .vscode/extensions.json | jq -r '.recommendations[]')
echo -e "\nDetected recommended VS code extensions:"
echo "${RECOMMENDED_VSCODE_EXTENSIONS[@]}"

echo -e "\nInstalling recommended VS code extensions:"
echo "${RECOMMENDED_VSCODE_EXTENSIONS[@]}" | xargs -L 1 code --install-extension