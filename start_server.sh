#!/bin/bash
# Script de démarrage du serveur Signal Matin

cd "$(dirname "$0")"

echo "=========================================="
echo "Démarrage du serveur Signal Matin"
echo "=========================================="
echo ""

# Vérifier que le venv existe
if [ -d ".venv" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
    echo "⚠️  Attention: utilisation de python3 système (pas de venv)"
fi

# Démarrer le serveur
echo "Démarrage du serveur sur http://localhost:5000"
echo "Appuyez sur Ctrl+C pour arrêter"
echo ""

$PYTHON app.py