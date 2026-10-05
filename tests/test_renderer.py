import datetime as dt
from pathlib import Path

from pypdf import PdfReader

from signal_matin.mock_data import construire_demo
from signal_matin.models import DensityMode
from signal_matin.normalizer import normaliser_edition
from signal_matin.pdf import generer_pdf, inspecter_html
from signal_matin.renderer import render_html


EXPECTED_PAGES = {
    DensityMode.COMPACT: 4,
    DensityMode.STANDARD: 6,
    DensityMode.EXTENDED: 5,
}


def test_html_has_expected_pages_and_sections():
    demo = construire_demo(dt.date(2026, 9, 26))
    for mode, count in EXPECTED_PAGES.items():
        edition = normaliser_edition(demo, mode=mode)
        html = render_html(edition)
        assert html.count('class="sheet ') == count
        assert "Signal Matin" in html
        assert "En bref, en detail" in html


def test_front_page_keeps_local_section_visible_without_local_news():
    edition = normaliser_edition(
        construire_demo(dt.date(2026, 9, 26)), mode="standard"
    ).model_copy(update={"tech": [], "tech_news": []})
    html = render_html(edition)
    first_page = html.split('<section class="sheet page-1', 1)[1].split(
        '<section class="sheet page-2', 1
    )[0]

    assert "<h2>Local</h2>" in first_page
    assert "Aucune actualite locale disponible ce matin." in first_page


def test_front_page_prioritizes_local_articles_in_compact_block():
    edition = normaliser_edition(
        construire_demo(dt.date(2026, 9, 26)), mode="standard"
    )
    html = render_html(edition)
    first_page = html.split('<section class="sheet page-1', 1)[1].split(
        '<section class="sheet page-2', 1
    )[0]
    local = first_page.split('class="briefs front-local-briefs"', 1)[1].split(
        "</section>", 1
    )[0]

    assert all(item.title[:120] in local for item in edition.tech[:2])
    assert local.count("Lire l'article complet") == sum(
        bool(item.source and item.source.url) for item in edition.tech[:2]
    )
    assert first_page.index("front-local-briefs") < first_page.index(
        '<section class="briefs">'
    )


def test_curiosity_page_and_briefs_detail_illustration_are_removed():
    edition = normaliser_edition(
        construire_demo(dt.date(2026, 9, 26)), mode="standard"
    )
    html = render_html(edition)

    assert "Veille &amp; curiosites" not in html
    assert 'class="briefs-detail-floor"' not in html


def test_no_major_overflow():
    demo = construire_demo(dt.date(2026, 9, 26))
    for mode in EXPECTED_PAGES:
        edition = normaliser_edition(demo, mode=mode)
        layout = inspecter_html(render_html(edition))
        assert not [page for page in layout if page["overflow"]]


def test_pdf_is_a4(tmp_path):
    edition = normaliser_edition(
        construire_demo(dt.date(2026, 9, 26)), mode="standard")
    path = generer_pdf(edition, tmp_path / "signal-matin.pdf")
    reader = PdfReader(str(path))
    assert len(reader.pages) == len(inspecter_html(render_html(edition)))
    for page in reader.pages:
        assert abs(float(page.mediabox.width) - 595.28) < 1.0
        assert abs(float(page.mediabox.height) - 841.89) < 1.0


def test_tech_pagination_depends_on_text_volume():
    edition = normaliser_edition(
        construire_demo(dt.date(2026, 9, 26)), mode="standard")
    assert len(edition.tech_news) == 5
    assert "tech-continuation-page" not in render_html(edition)

    long_items = [
        item.model_copy(update={"expanded_summary": "Texte developpe. " * 70})
        for item in edition.tech_news
    ]
    html = render_html(edition.model_copy(update={"tech_news": long_items}))
    assert "Local - suite" in html
    assert "tech-continuation-page" in html


def test_extra_news_and_tech_create_pages_without_omission():
    edition = normaliser_edition(
        construire_demo(dt.date(2026, 9, 26)), mode="standard")
    source_item = edition.news.all_secondary()[0]
    news_items = [
        source_item.model_copy(update={"title": f"Sujet actualite unique {index}"})
        for index in range(20)
    ]
    tech_items = [
        edition.tech_news[index % len(edition.tech_news)].model_copy(
            update={"title": f"Sujet technologie unique {index}"}
        )
        for index in range(9)
    ]
    curiosity_items = [
        edition.curiosity_news[index % len(edition.curiosity_news)].model_copy(
            update={"title": f"Sujet curiosite unique {index}"}
        )
        for index in range(8)
    ]
    edition = edition.model_copy(update={
        "news": edition.news.model_copy(update={
            "world": news_items[:12],
            "france": news_items[12:],
            "economy": [], "society": [], "science": [], "culture": [],
        }),
        "tech_news": tech_items,
    })
    html = render_html(edition)
    assert html.count('class="sheet ') == 8
    for item in [*news_items, *tech_items]:
        assert item.title in html
    for item in curiosity_items:
        assert item.title not in html
    assert "tech-continuation is-four" in html
    assert "Veille &amp; curiosites" not in html


def test_large_daily_variation_creates_balanced_continuation_pages():
    edition = normaliser_edition(
        construire_demo(dt.date(2026, 9, 26)), mode="extended")
    css = (
        (Path(__file__).resolve().parents[1] / "web" / "signal_matin.css")
        .read_text(encoding="utf-8")
        + """
        .page-news .news-opening { min-height: 190mm; }
        .page-news .news-followups { min-height: 190mm; columns: 1; }
        .page-news .news-followups .news-card { min-height: 90mm; padding-bottom: 8mm; }
        .page-news .news-followups .news-card p { font-size: 13pt; line-height: 1.65; }
        """
    )
    layout = inspecter_html(render_html(edition, css=css))
    assert len(layout) > EXPECTED_PAGES[DensityMode.EXTENDED]
    assert not [page for page in layout if page["overflow"]]
    adaptive = [page for page in layout if page["adaptive"]]
    assert adaptive
    assert all(page["used_ratio"] >= 0.52 or page["sparse"] for page in adaptive)


def test_delayed_print_reuses_real_task_action():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "programmer_impression_signal_matin.ps1"
    ).read_text(encoding="utf-8")
    assert "$SourceAction.Execute" in script
    assert "$SourceAction.Arguments" in script
    assert "Start-ScheduledTask -TaskName $TacheSource" not in script
