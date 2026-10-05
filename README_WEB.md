# Signal Matin - Serveur Web

Ce document explique comment utiliser le serveur web pour accéder à vos journaux quotidiens.

## Structure

Le serveur web Flask permet de :
- **Visualiser** les journaux disponibles
- **Télécharger** les journaux en PDF
- **Voir la version HTML** des journaux
- **Générer automatiquement** un nouveau journal tous les matins à 6h

## Installation

### Prérequis

- Python 3.8+
- Environnement virtuel déjà configuré (`.venv/`)
- Dépendances Flask et Flask-APScheduler installées

### Dépendances supplémentaires

Si vous utilisez un nouvel environnement, installez les dépendances nécessaires :

```bash
# Depuis le répertoire du projet
.venv/bin/python -m pip install flask flask-apscheduler
```

## Démarrage

### Méthode 1: Script de démarrage

```bash
chmod +x start_server.sh
./start_server.sh
```

### Méthode 2: Commande directe

```bash
# Avec le venv
.venv/bin/python app.py

# Ou avec Python système (si venv non disponible)
python3 app.py
```

## Accès

Une fois le serveur démarré, accédez à l'application via votre navigateur :

🌐 **URL**: `http://localhost:5000`

## Fonctionnalités

### Page d'accueil (`/`)
- Affiche la liste des journaux disponibles (PDF générés)
- Trie par date (du plus récent au plus ancien)
- Affiche des badges pour "Aujourd'hui" et "Hier"
- Bouton pour générer manuellement le journal du jour

### Routes disponibles

| Route | Description |
|-------|-------------|
| `/` | Page d'accueil avec liste des journaux |
| `/journal/<date>` | Voir le journal PDF pour une date donnée |
| `/download/<date>` | Télécharger le journal PDF pour une date donnée |
| `/preview/<date>` | Voir la version HTML du journal |
| `/generate` | Générer manuellement le journal du jour |
| `/health` | Endpoint de santé (JSON) |

### Génération automatique

- **Heure**: Tous les jours à 6h00 (heure française)
- **Fuseau horaire**: Europe/Paris
- **Fonctionnement**: La tâche vérifie et génère automatiquement le journal du jour

### Exemple d'utilisation

1. **Voir le journal d'aujourd'hui**:
   - Accédez à la page d'accueil
   - Cliquez sur "📄 Voir PDF" pour le journal du jour

2. **Télécharger un journal**:
   - Cliquez sur "⬇️ Télécharger" pour sauvegarder le PDF

3. **Voir la version HTML**:
   - Cliquez sur "👁️ Aperçu HTML" pour voir la version web

4. **Génération manuelle**:
   - Cliquez sur "✨ Générer le journal d'aujourd'hui" pour forcer la génération

## Configuration

### Modifier l'heure de génération

Dans `app.py`, modifiez la ligne :

```python
scheduler.add_job(
    id="daily_generation",
    func=scheduled_generation,
    trigger="cron",
    hour=6,      # Heure (0-23)
    minute=0,    # Minute (0-59)
    timezone="Europe/Paris",
    replace_existing=True
)
```

### Changer le port du serveur

Dans `app.py`, modifiez la ligne :

```python
app.run(host="0.0.0.0", port=5000, debug=False)
```

## Structure des fichiers

```
signal-matin/
├── app.py                 # Serveur Flask
├── start_server.sh        # Script de démarrage
├── templates/
│   └── journal.html       # Template HTML
├── static/                # Fichiers statiques (CSS, JS)
│   └── signal_matin.css   # Style CSS
├── output/
│   ├── pdf/               # Journaux PDF générés
│   ├── data/              # Données JSON
│   └── preview/           # Aperçus HTML
└── main.py               # Script principal de génération
```

## Résolution des problèmes

### Problème: Port déjà utilisé

```bash
# Trouver le processus utilisant le port 5000
lsof -i :5000

# Tuer le processus
kill -9 <PID>

# Ou changer le port dans app.py
app.run(host="0.0.0.0", port=5001, debug=False)
```

### Problème: Génération échouée

- Vérifiez que `main.py` fonctionne en ligne de commande :
  ```bash
  .venv/bin/python main.py generate
  ```
- Vérifiez les permissions sur le dossier `output/`
- Consultez les logs du serveur pour les erreurs

### Problème: Fuseau horaire incorrect

- Assurez-vous que le système utilise le bon fuseau horaire
- Ou modifiez le `timezone` dans la configuration du scheduler

## Déploiement en production

Pour un déploiement en production, utilisez un serveur WSGI comme Gunicorn ou uWSGI :

### Avec Gunicorn

```bash
.venv/bin/pip install gunicorn
.venv/bin/gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

### Avec uWSGI

```bash
.venv/bin/pip install uwsgi
.venv/bin/uwsgi --http :8000 --module app:app
```

### Supervisor (pour la gestion des processus)

Créez un fichier `/etc/supervisor/conf.d/signal-matin.conf` :

```ini
[program:signal-matin]
command=/home/tobias/Bureau/signal-matin/.venv/bin/gunicorn -w 4 -b 0.0.0.0:8000 app:app
user=tobias
directory=/home/tobias/Bureau/signal-matin
autostart=true
autorestart=true
stdout_logfile=/var/log/signal-matin.log
stderr_logfile=/var/log/signal-matin-error.log
```

## Sécurité

- **Accès local uniquement** par défaut (host="0.0.0.0" permet l'accès depuis le réseau local)
- **Pas d'authentification** par défaut - ajoutez une authentification si nécessaire
- **Permissions** : Assurez-vous que l'utilisateur a les droits sur le dossier `output/`

## Mises à jour

Pour mettre à jour l'application :

1. Arrêtez le serveur
2. Mettez à jour le code
3. Installez les nouvelles dépendances si nécessaire
4. Redémarrez le serveur

## Licence

Ce projet fait partie de Signal Matin - voir le fichier LICENSE principal.