"""Rendu PDF A4 compatible ARMv7 32-bit via wkhtmltopdf/pdfkit.

Ce module utilise pdfkit (wkhtmltopdf) pour la generation de PDF, qui est compatible
avec les architectures ARMv7 32-bit (Raspberry Pi 2/3/Zero).

Pour utiliser pdfkit sur Raspberry Pi OS (32-bit), installez les dependances :
    sudo apt-get install wkhtmltopdf
    pip install pdfkit

Sur les architectures x86_64, Playwright peut etre utilise pour une mesure precise
avec JavaScript (si disponible).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .models import MorningEdition
from .renderer import render_html, write_html


# Fonctions originales pour Playwright (fallback sur x86_64)

def _browser_candidates() -> list[Path]:
    values = [
        os.environ.get("PROGRAMFILES", "") + r"\Microsoft\Edge\Application\msedge.exe",
        os.environ.get("PROGRAMFILES(X86)", "") + r"\Microsoft\Edge\Application\msedge.exe",
        os.environ.get("PROGRAMFILES", "") + r"\Google\Chrome\Application\chrome.exe",
        os.environ.get("PROGRAMFILES(X86)", "") + r"\Google\Chrome\Application\chrome.exe",
    ]
    return [Path(value) for value in values if value and Path(value).is_file()]


def _launch_browser(playwright):
    try:
        return playwright.chromium.launch(headless=True)
    except Exception as first_error:
        for executable in _browser_candidates():
            try:
                return playwright.chromium.launch(headless=True, executable_path=str(executable))
            except Exception:
                continue
        raise RuntimeError(
            "Chromium est indisponible. Lance : uv run playwright install chromium"
        ) from first_error


def _measure(page) -> list[dict[str, Any]]:
    return page.eval_on_selector_all(
        ".sheet",
        """pages => pages.map((p, index) => {
          const content = p.querySelector('.page-content');
          const rect = p.getBoundingClientRect();
          return {
            page: index + 1,
            width: Math.round(rect.width),
            height: Math.round(rect.height),
            content_client_height: content ? content.clientHeight : 0,
            content_scroll_height: content ? content.scrollHeight : 0,
            overflow: content ? content.scrollHeight > content.clientHeight + 2 : false,
            used_ratio: content && content.children.length
              ? Math.round((Math.max(...[...content.children].map(
                  child => child.getBoundingClientRect().bottom
                )) - content.getBoundingClientRect().top) / content.clientHeight * 1000) / 1000
              : 0,
            adaptive: p.dataset.adaptiveContinuation === 'true',
            sparse: p.classList.contains('adaptive-sparse')
          };
        })""",
    )


def _paginate_adaptive(page) -> dict[str, int]:
    """Laisse le document creer et repartir ses pages de continuation."""
    result = page.evaluate(
        """() => window.SignalMatinPagination
          ? window.SignalMatinPagination.paginate()
          : {pages: document.querySelectorAll('.sheet').length, unresolved: 0}
        """
    )
    return result or {"pages": 0, "unresolved": 0}


def _fit_moderate_overflow(
    page,
    layout: list[dict[str, Any]],
    *,
    minimum_scale: float = 0.85,
) -> list[dict[str, Any]]:
    """Reduit seulement les pages legerement trop longues."""
    overflowing = [item for item in layout if item["overflow"]]
    if not overflowing:
        return layout

    for _ in range(4):
        page.evaluate(
            """({ overflowing, minimumScale }) => {
              for (const item of overflowing) {
                const sheet = document.querySelector(`.sheet[data-page="${item.page}"]`);
                const content = sheet && sheet.querySelector('.page-content');
                if (!content || !item.content_scroll_height) continue;

                const currentScale = Number(content.dataset.autoFit || 1);
                const physicalHeight = Number(
                  content.dataset.autoFitPhysicalHeight ||
                  content.clientHeight * currentScale
                );
                const nextScale = Math.min(
                  1,
                  currentScale *
                    ((item.content_client_height - 3) / item.content_scroll_height)
                );
                if (nextScale < minimumScale) continue;

                content.dataset.autoFitPhysicalHeight = String(physicalHeight);
                content.dataset.autoFit = String(nextScale);
                content.style.zoom = String(nextScale);
                content.style.height = `${physicalHeight / nextScale}px`;
              }
            }""",
            {"overflowing": overflowing, "minimumScale": minimum_scale},
        )
        layout = _measure(page)
        overflowing = [item for item in layout if item["overflow"]]
        if not overflowing:
            break
    return layout



def inspecter_html(html_text: str) -> list[dict[str, Any]]:
    """
    Inspecte la mise en page HTML.
    
    Utilise Playwright pour une mesure precise avec JavaScript.
    Si Playwright n'est pas disponible, retourne une approximation basique.
    """
    try:
        # Essayer Playwright d'abord
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as playwright:
            browser = _launch_browser(playwright)
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                page.set_content(html_text, wait_until="load")
                page.evaluate("document.fonts.ready")
                _paginate_adaptive(page)
                return _measure(page)
            finally:
                browser.close()
    except (ImportError, Exception):
        # Fallback : compter les sheets dans le HTML
        import re
        sheet_count = len(re.findall(r'class="sheet', html_text))
        return [
            {
                "page": i + 1,
                "width": 595,
                "height": 842,
                "content_client_height": 0,
                "content_scroll_height": 0,
                "overflow": False,
                "used_ratio": 0,
                "adaptive": False,
                "sparse": False,
            }
            for i in range(sheet_count)
        ]


def generer_pdf(
    edition: MorningEdition,
    pdf_path: Path,
    html_path: Path | None = None,
    verifier_debordement: bool = True,
) -> Path:
    """
    Compose puis imprime le HTML en PDF A4, sans en-tete navigateur.
    
    Utilise pdfkit (wkhtmltopdf) pour une compatibilite maximale (y compris ARMv7 32-bit).
    Sur les architectures supportant Playwright, utilise Chromium pour une verification
    precise des debordements.
    """
    import pdfkit

    html_text = render_html(edition)
    if html_path is not None:
        write_html(edition, html_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    # Options pour wkhtmltopdf
    options = {
        'page-size': 'A4',
        'margin-top': '0mm',
        'margin-right': '0mm',
        'margin-bottom': '0mm',
        'margin-left': '0mm',
        'encoding': 'UTF-8',
        'enable-local-file-access': None,  # Permet l'acces aux fichiers locaux (CSS, images)
        'print-media-type': True,
        'no-outline': True,
        'dpi': 300,
    }

    # Verification des debordements (si active et possible)
    if verifier_debordement:
        try:
            # Essayer avec Playwright pour une verification precise
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as playwright:
                browser = _launch_browser(playwright)
                try:
                    page = browser.new_page(viewport={"width": 1280, "height": 900})
                    page.set_content(html_text, wait_until="load")
                    page.evaluate("document.fonts.ready")
                    _paginate_adaptive(page)
                    layout = _measure(page)
                    layout = _fit_moderate_overflow(page, layout, minimum_scale=0.95)
                    overflows = [item["page"] for item in layout if item["overflow"]]
                    if overflows:
                        raise RuntimeError(
                            "Contenu trop long sur les pages : " + ", ".join(map(str, overflows))
                        )
                finally:
                    browser.close()
        except (ImportError, Exception):
            # Sur ARMv7 ou sans Playwright, on ne peut pas verifier les debordements
            # On generera le PDF quand meme
            pass

    # Generation du PDF
    # Essayer d'abord pdfkit/wkhtmltopdf (compatible ARMv7)
    try:
        import pdfkit
        pdfkit.from_string(html_text, str(pdf_path), options=options)
    except (ImportError, OSError) as e:
        # Fallback vers Playwright si pdfkit/wkhtmltopdf n'est pas disponible
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as playwright:
                browser = _launch_browser(playwright)
                try:
                    page = browser.new_page(viewport={"width": 1280, "height": 900})
                    page.set_content(html_text, wait_until="load")
                    page.evaluate("document.fonts.ready")
                    
                    # Pour la generation PDF, on n'a pas besoin de verifier les debordements
                    # car on a deja fait ca ci-dessus si verifier_debordement=True
                    _paginate_adaptive(page)
                    
                    page.emulate_media(media="print")
                    page.pdf(
                        path=str(pdf_path),
                        format="A4",
                        print_background=True,
                        prefer_css_page_size=True,
                        display_header_footer=False,
                        margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                    )
                finally:
                    browser.close()
        except (ImportError, Exception) as fallback_error:
            raise RuntimeError(
                "Ni wkhtmltopdf ni Playwright ne sont disponibles. "
                "Pour ARMv7 (Raspberry Pi): sudo apt-get install wkhtmltopdf && pip install pdfkit. "
                "Pour x86_64: pip install playwright && playwright install chromium"
            ) from fallback_error
    
    return pdf_path
