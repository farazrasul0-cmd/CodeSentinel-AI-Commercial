"""Standalone printable executive HTML report exporter."""

import html
from typing import Any

from app.infrastructure.db.models.analysis_report import AnalysisReport
from app.services.scoring_service import QualityScorecard, ScoringService

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Software Quality Executive Report - {title}</title>
    <style>
        :root {{
            --bg: #0f172a;
            --surface: #1e293b;
            --surface-border: #334155;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --primary: #6366f1;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
        }}
        @media print {{
            body {{ background: #ffffff !important; color: #0f172a !important; font-size: 12pt; }}
            .card, .rec-card {{ background: #f8fafc !important; border: 1px solid #cbd5e1 !important; page-break-inside: avoid; }}
            .no-print {{ display: none !important; }}
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
        body {{ background: var(--bg); color: var(--text-main); padding: 2rem; line-height: 1.5; }}
        .container {{ max-width: 960px; margin: 0 auto; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--surface-border); padding-bottom: 1.5rem; margin-bottom: 2rem; }}
        .title-h1 {{ font-size: 1.75rem; font-weight: 800; }}
        .meta-sub {{ font-size: 0.875rem; color: var(--text-muted); margin-top: 0.25rem; }}
        .hero-banner {{ display: flex; align-items: center; justify-content: space-between; background: var(--surface); border: 1px solid var(--surface-border); border-radius: 0.75rem; padding: 1.5rem 2rem; margin-bottom: 2rem; }}
        .overall-score {{ font-size: 3rem; font-weight: 900; color: var(--success); }}
        .grade-badge {{ display: inline-block; padding: 0.25rem 0.75rem; border-radius: 0.375rem; font-weight: 800; font-size: 1rem; }}
        .grade-A {{ background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981; }}
        .grade-B {{ background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid #38bdf8; }}
        .grade-C {{ background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid #f59e0b; }}
        .grade-D {{ background: rgba(249, 115, 22, 0.2); color: #f97316; border: 1px solid #f97316; }}
        .grade-F {{ background: rgba(239, 68, 68, 0.2); color: #ef4444; border: 1px solid #ef4444; }}
        .grid-4 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .card {{ background: var(--surface); border: 1px solid var(--surface-border); border-radius: 0.5rem; padding: 1.25rem; }}
        .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }}
        .pillar-title {{ font-weight: 700; font-size: 0.95rem; }}
        .score-large {{ font-size: 1.8rem; font-weight: 800; color: #fff; }}
        .score-max {{ font-size: 0.85rem; color: var(--text-muted); font-weight: 400; }}
        .score-sub {{ font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.5rem; }}
        .summary-text {{ font-size: 0.8rem; color: #cbd5e1; }}
        .rec-card {{ background: var(--surface); border: 1px solid var(--surface-border); border-radius: 0.5rem; padding: 1rem; margin-bottom: 0.75rem; }}
        .rec-badge {{ font-size: 0.75rem; color: var(--warning); font-weight: 600; text-transform: uppercase; margin-bottom: 0.25rem; }}
        .rec-title {{ font-size: 0.95rem; font-weight: 700; color: #fff; }}
        .rec-desc {{ font-size: 0.85rem; color: var(--text-muted); margin-top: 0.25rem; }}
        .btn-print {{ background: var(--primary); color: #fff; border: none; padding: 0.5rem 1rem; border-radius: 0.375rem; font-weight: 600; cursor: pointer; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1 class="title-h1">Quality Assessment Report</h1>
                <p class="meta-sub">Repository: <strong>{title}</strong> &bull; Total SLOC: {sloc} &bull; Tech Debt: {debt} mins</p>
            </div>
            <button class="btn-print no-print" onclick="window.print()">Print / Save PDF</button>
        </div>

        <div class="hero-banner">
            <div>
                <div style="font-size: 0.85rem; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">Repository Quality Index (RQI)</div>
                <div class="overall-score">{overall:.1f} <span style="font-size: 1.25rem; color: var(--text-muted); font-weight: 400;">/ 100</span></div>
            </div>
            <div style="text-align: right;">
                <div class="grade-badge grade-{grade}" style="font-size: 2rem; padding: 0.5rem 1.5rem;">Grade {grade}</div>
                <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.5rem;">{suppressed} False Alarm(s) Suppressed</div>
            </div>
        </div>

        <h2 style="font-size: 1.15rem; font-weight: 700; margin-bottom: 1rem;">Multi-Pillar Scores</h2>
        <div class="grid-4">
            {pillars_html}
        </div>

        <h2 style="font-size: 1.15rem; font-weight: 700; margin-bottom: 1rem;">Prioritized Actionable Roadmap</h2>
        <div>
            {recs_html}
        </div>
    </div>
</body>
</html>
"""


class HtmlReportExporter:
    """Builder for standalone printable executive HTML reports."""

    @classmethod
    def export(
        cls,
        report: AnalysisReport,
        scorecard: QualityScorecard | None = None,
        repo_name: str = "Repository",
    ) -> str:
        sc = scorecard or ScoringService.calculate_scores(
            file_metrics=report.file_metrics,
            issues=report.issues,
            reviews=report.review_comments,
            defect_predictions=report.defect_predictions,
        )

        pillars_html = cls._render_pillars(sc.pillars)
        recs_html = cls._render_recommendations(sc.recommendations)

        return HTML_TEMPLATE.format(
            title=html.escape(repo_name),
            sloc=report.total_lines_of_code,
            debt=sc.technical_debt_minutes,
            overall=sc.overall_score,
            grade=html.escape(sc.grade),
            suppressed=sc.false_positives_suppressed,
            pillars_html=pillars_html,
            recs_html=recs_html,
        )

    @staticmethod
    def _render_pillars(pillars: list[dict[str, Any]]) -> str:
        """Renders HTML cards for scorecard pillars."""
        cards = []
        for p in pillars:
            weight_pct = int(p['weight'] * 100)
            cards.append(f"""
            <div class="card">
                <div class="card-header">
                    <span class="pillar-title">{html.escape(p['name'])}</span>
                    <span class="grade-badge grade-{p['grade']}">{p['grade']}</span>
                </div>
                <div class="score-large">{p['score']:.1f}<span class="score-max">/100</span></div>
                <div class="score-sub">Weight: {weight_pct}% ({p['weighted_contribution']:.1f} pts)</div>
                <div class="summary-text">{html.escape(p['summary'])}</div>
            </div>""")
        return "".join(cards)

    @staticmethod
    def _render_recommendations(recs: list[dict[str, Any]]) -> str:
        """Renders HTML cards for prioritized refactoring actions."""
        cards = []
        for r in recs:
            cards.append(f"""
            <div class="rec-card">
                <div class="rec-badge">Rank #{r['rank']} &bull; +{r['potential_score_impact']} pts &bull; ~{r['effort_minutes']}m effort</div>
                <div class="rec-title">{html.escape(r['title'])}</div>
                <div class="rec-desc">{html.escape(r['description'])}</div>
            </div>""")
        return "".join(cards)
