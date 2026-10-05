"""Serveur Flask pour Signal Matin - Journal quotidien numérique personnalisé.

Ce serveur permet de:
- Afficher la liste des journaux disponibles
- Voir et télécharger les journaux PDF
- Voir la version HTML des journaux
- Générer automatiquement un nouveau journal tous les matins à 6h
"""
from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

from flask import Flask, render_template, send_from_directory, redirect, url_for
from flask_apscheduler import APScheduler

# Configuration
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

# Initialiser Flask
app = Flask(__name__)

# Configuration des dossiers
app.template_folder = str(ROOT / "templates")
app.static_folder = str(ROOT / "static")

# Chemins des fichiers
OUTPUT_DIR = ROOT / "output"
PDF_DIR = OUTPUT_DIR / "pdf"
DATA_DIR = OUTPUT_DIR / "data"
PREVIEW_DIR = OUTPUT_DIR / "preview"

# Assurer que les dossiers existent
PDF_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

# Initialiser APScheduler
scheduler = APScheduler()
scheduler.init_app(app)


def get_python_exec() -> Path:
    """Retourne le chemin vers l'exécutable Python avec le venv."""
    python_exec = ROOT / ".venv" / "bin" / "python"
    if python_exec.exists():
        return python_exec
    
    # Essayer le chemin Windows
    python_exec = ROOT / ".venv" / "Scripts" / "python.exe"
    if python_exec.exists():
        return python_exec
    
    return Path("python3")


def generate_journal(date: dt.date | None = None) -> bool:
    """Génère le journal pour une date donnée en appelant main.py generate.
    
    Args:
        date: Date pour laquelle générer le journal. Si None, utilise aujourd'hui.
        
    Returns:
        True si la génération a réussi, False sinon.
    """
    if date is None:
        date = dt.date.today()
    
    try:
        python_exec = get_python_exec()
        cmd = [str(python_exec), "main.py", "generate","--mode","extended"]
        
        result = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes de timeout
        )
        
        if result.returncode == 0:
            print(f"[{dt.datetime.now().isoformat()}] Journal généré avec succès pour {date.isoformat()}")
            return True
        else:
            print(f"[{dt.datetime.now().isoformat()}] Erreur lors de la génération pour {date.isoformat()}")
            print(f"Erreur: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"[{dt.datetime.now().isoformat()}] Timeout lors de la génération du journal pour {date.isoformat()}")
        return False
    except Exception as e:
        print(f"[{dt.datetime.now().isoformat()}] Erreur inattendue: {e}")
        return False


def scheduled_generation():
    """Tâche planifiée pour générer le journal tous les jours à 6h."""
    print(f"[{dt.datetime.now().isoformat()}] Début de la génération planifiée du journal")
    success = generate_journal()
    if success:
        print(f"[{dt.datetime.now().isoformat()}] Génération planifiée terminée avec succès")
    else:
        print(f"[{dt.datetime.now().isoformat()}] Échec de la génération planifiée")


def get_available_dates() -> list[dict]:
    """Retourne la liste des dates pour lesquelles un journal existe (PDF).
    
    Returns:
        Liste de dictionnaires avec les informations sur chaque date.
    """
    dates = []
    today = dt.date.today()
    yesterday = today - dt.timedelta(days=1)
    
    if PDF_DIR.exists():
        # Lister tous les fichiers PDF et les trier par date (plus récent d'abord)
        pdf_files = sorted(PDF_DIR.glob("*.pdf"), reverse=True)
        
        for pdf_file in pdf_files:
            # Format attendu: AAAA-MM-JJ-signal-matin.pdf
            if pdf_file.stem.endswith("-signal-matin"):
                date_str = pdf_file.stem.replace("-signal-matin", "")
                try:
                    date_obj = dt.date.fromisoformat(date_str)
                    dates.append({
                        "date": date_str,
                        "formatted": date_obj.strftime("%d/%m/%Y"),
                        "day_name": date_obj.strftime("%A"),
                        "is_today": date_str == today.isoformat(),
                        "is_yesterday": date_str == yesterday.isoformat()
                    })
                except ValueError:
                    # Ignorer les fichiers qui ne correspondent pas au format
                    continue
    
    return dates


@app.route("/")
def index():
    """Page d'accueil avec la liste des journaux disponibles."""
    dates = get_available_dates()
    return render_template("journal.html", dates=dates)


@app.route("/journal/<date>")
def view_journal(date):
    """Affiche le journal PDF pour une date donnée."""
    pdf_filename = f"{date}-signal-matin.pdf"
    pdf_path = PDF_DIR / pdf_filename
    
    if pdf_path.exists():
        return send_from_directory(PDF_DIR, pdf_filename, as_attachment=False)
    else:
        # Essayer de générer si c'est aujourd'hui
        if date == dt.date.today().isoformat():
            generate_journal()
            if pdf_path.exists():
                return send_from_directory(PDF_DIR, pdf_filename, as_attachment=False)
        
        return redirect(url_for("index"))


@app.route("/download/<date>")
def download_journal(date):
    """Télécharge le journal PDF pour une date donnée."""
    pdf_filename = f"{date}-signal-matin.pdf"
    pdf_path = PDF_DIR / pdf_filename
    
    if pdf_path.exists():
        return send_from_directory(PDF_DIR, pdf_filename, as_attachment=True)
    else:
        return redirect(url_for("index"))


@app.route("/preview/<date>")
def view_preview(date):
    """Affiche la version HTML du journal."""
    html_filename = f"{date}-signal-matin.html"
    html_path = PREVIEW_DIR / html_filename
    
    if html_path.exists():
        return send_from_directory(PREVIEW_DIR, html_filename)
    else:
        # Essayer de générer
        if date == dt.date.today().isoformat():
            generate_journal()
            if html_path.exists():
                return send_from_directory(PREVIEW_DIR, html_filename)
        return redirect(url_for("index"))


@app.route("/generate")
def manual_generate():
    """Génère manuellement le journal du jour."""
    print(f"[{dt.datetime.now().isoformat()}] Génération manuelle demandée")
    success = generate_journal()
    if success:
        print(f"[{dt.datetime.now().isoformat()}] Génération manuelle terminée avec succès")
    else:
        print(f"[{dt.datetime.now().isoformat()}] Échec de la génération manuelle")
    return redirect(url_for("index"))


@app.route("/health")
def health_check():
    """Endpoint de santé pour vérifier que le serveur fonctionne."""
    return {
        "status": "ok",
        "time": dt.datetime.now().isoformat(),
        "available_dates": [d["date"] for d in get_available_dates()],
        "next_scheduled_run": "Demain à 6h00"
    }


# Configurer la tâche planifiée après l'initialisation
with app.app_context():
    # Ajouter la tâche de génération quotidienne à 6h
    scheduler.add_job(
        id="daily_generation",
        func=scheduled_generation,
        trigger="cron",
        hour=6,
        minute=0,
        timezone="Europe/Paris",  # Heure française
        replace_existing=True
    )
    
    # Vérifier que la tâche a bien été ajoutée
    jobs = scheduler.get_jobs()
    print(f"Tâches planifiées: {len(jobs)} tâche(s)")
    for job in jobs:
        print(f"  - {job.id}: {job.trigger}")


if __name__ == "__main__":
    print("=" * 70)
    print("Signal Matin - Serveur Web")
    print("=" * 70)
    
    # Générer le journal du jour si ce n'est pas déjà fait
    today_date = dt.date.today().isoformat()
    today_pdf = PDF_DIR / f"{today_date}-signal-matin.pdf"
    if not today_pdf.exists():
        print(f"Génération du journal pour {today_date}...")
        generate_journal()
    else:
        print(f"Journal pour {today_date} déjà présent.")
    
    # Lister les dates disponibles
    available_dates = get_available_dates()
    if available_dates:
        print("Dates disponibles:")
        for date_info in available_dates[:5]:  # Afficher les 5 plus récentes
            print(f"  - {date_info['formatted']} ({date_info['day_name']})")
    else:
        print("Aucun journal trouvé.")
    
    print("=" * 70)
    print("Démarrage du serveur Flask...")
    print("Accédez à l'application sur: http://localhost:5000")
    print("Génération automatique programmée tous les jours à 6h00 (heure française).")
    print("Appuyez sur Ctrl+C pour arrêter le serveur.")
    print("=" * 70)
    
    # Démarrer le serveur Flask
    try:
        app.run(host="0.0.0.0", port=8001, debug=False)
    except KeyboardInterrupt:
        print("\nArrêt du serveur...")
        scheduler.shutdown()
        print("Serveur arrêté.")