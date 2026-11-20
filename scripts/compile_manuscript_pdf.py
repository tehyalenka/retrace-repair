#!/usr/bin/env python3
"""
Compile a publication-quality scholarly manuscript PDF for RETRACE
using ReportLab Platypus.

Produces: paper/manuscript.pdf
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#4B5563"))

        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "RETRACE: Do Unit Tests Guarantee Invariant Correctness in Autonomous Program Repair?")
            self.drawRightString(612 - 54, 750, "Lenka, November 2026")
            self.setStrokeColor(colors.HexColor("#D1D5DB"))
            self.setLineWidth(0.5)
            self.line(54, 744, 612 - 54, 744)

        # Footer (all pages)
        self.setStrokeColor(colors.HexColor("#D1D5DB"))
        self.setLineWidth(0.5)
        self.line(54, 45, 612 - 54, 45)

        footer_text = "Release Tag: v1.9.0-research-release | Artifact Seal SHA-256 (65 sealed fixtures per model)"
        self.drawString(54, 32, footer_text)
        self.drawRightString(612 - 54, 32, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


def build_pdf():
    os.makedirs("paper", exist_ok=True)
    pdf_path = "paper/manuscript.pdf"

    # Letter is 612 x 792 pt. Margins: 54 pt (0.75 in)
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=21,
        alignment=1, # Center
        textColor=colors.HexColor("#111827"),
        spaceAfter=8,
    )

    author_style = ParagraphStyle(
        "Author",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        alignment=1,
        textColor=colors.HexColor("#1F2937"),
    )

    meta_style = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        alignment=1,
        textColor=colors.HexColor("#4B5563"),
        spaceAfter=12,
    )

    abstract_title = ParagraphStyle(
        "AbstractTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        alignment=1,
        textColor=colors.HexColor("#111827"),
        spaceAfter=4,
    )

    abstract_body = ParagraphStyle(
        "AbstractBody",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=12,
        alignment=4, # Justify
        textColor=colors.HexColor("#1F2937"),
        leftIndent=20,
        rightIndent=20,
        spaceAfter=14,
    )

    h1 = ParagraphStyle(
        "SectionH1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True,
    )

    h2 = ParagraphStyle(
        "SectionH2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True,
    )

    body = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=9.5,
        leading=13.5,
        alignment=4, # Justify
        textColor=colors.HexColor("#1F2937"),
        spaceAfter=6,
    )

    bullet = ParagraphStyle(
        "Bullet",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=9,
        leading=13,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3,
        textColor=colors.HexColor("#1F2937"),
    )

    table_cell = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#1F2937"),
    )

    table_header = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.white,
    )

    caption_style = ParagraphStyle(
        "Caption",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=10.5,
        alignment=1,
        textColor=colors.HexColor("#4B5563"),
        spaceBefore=4,
        spaceAfter=8,
    )

    story = []

    # Title
    story.append(Paragraph("Do Unit Tests Guarantee Invariant Correctness?<br/>An Empirical Evaluation of Autonomous Program Repair on Distributed Systems Invariants", title_style))
    story.append(Paragraph("<b>Tehya Lenka</b>", author_style))
    story.append(Paragraph("Independent Research Project &bull; lenkatehya@gmail.com<br/>Artifact Repository: github.com/tehyalenka/retrace-repair &bull; Release: v1.9.0-research-release", meta_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E5E7EB"), spaceBefore=2, spaceAfter=8))

    # Abstract
    story.append(Paragraph("ABSTRACT", abstract_title))
    abstract_text = (
        "Autonomous program repair (APR) systems powered by Large Language Models (LLMs) predominantly rely on unit test suites "
        "as their primary oracle for patch synthesis and validation. However, whether passing visible unit tests guarantees the preservation "
        "of complex software invariants remains an open empirical question. In this paper, we introduce <b>RETRACE</b>, an autonomous repair "
        "evaluation framework featuring physical dual-suite oracle isolation, disposable workspace replication, and cryptographic evidence sealing. "
        "We conduct an empirical study across <b>30 enterprise distributed systems tasks</b> spanning six architectural clusters: transactional "
        "durability, concurrency primitives, fault tolerance sagas, multi-tenant isolation, traffic resource pools, and coordination consensus.<br/><br/>"
        "Across 180 controlled matrix evaluations evaluating two distinct model families (Groq <code>openai/gpt-oss-120b</code> and Alibaba "
        "<code>qwen/qwen3.8-27b</code>), we benchmark three repair paradigms: (1) stochastic <b>Resampling</b>, (2) standard iterative <b>Failure Feedback</b>, "
        "and (3) disposable <b>Counterfactual Replay</b>. Our central finding is that <b>public-test success substantially overestimates held-out invariant "
        "correctness across both model families</b>. While iterative feedback achieved an 83.3%–86.7% public pass rate (25–26/30 tasks), held-out invariant "
        "success was only 23.3%–43.3% (7–13/30 tasks). In <b>40.0 percentage points</b> of tasks on the 120B model (12/30) and <b>63.3 percentage points</b> "
        "on the 27B model (19/30), LLM-generated patches successfully silenced visible test failures while silently breaking hidden architectural invariants. "
        "While Counterfactual Replay achieved the highest nominal success on the 120B model (46.7%), paired exact McNemar tests indicate that the difference "
        "is not statistically significant (p = 1.000), while incurring an 80.5% token cost premium. Crucially, non-significant McNemar results reflect "
        "bounded statistical power at N = 30 rather than mathematical equivalence. On the smaller 27B model, iterative feedback induced hyper-fixation "
        "on public traceback assertions, underperforming single-shot resampling (23.3% vs. 30.0%). We conclude with an empirical analysis of when "
        "speculative candidate exploration avoids local minima versus where localized feedback is computationally optimal."
    )
    story.append(Paragraph(abstract_text, abstract_body))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E5E7EB"), spaceBefore=4, spaceAfter=8))

    # Section 1: Introduction
    story.append(Paragraph("1. Introduction", h1))
    story.append(Paragraph(
        "Automated Program Repair (APR) has transitioned from heuristic search and constraint solving toward generative foundation models. "
        "Modern LLM coding agents typically rely on an iterative feedback loop: an initial patch is evaluated against visible unit tests; "
        "if tests fail, the stderr output, tracebacks, and assertion messages are appended to the conversational context for subsequent refinement turns. "
        "Despite high pass rates on benchmarks like SWE-bench and Defects4J, a critical vulnerability persists: <b>oracle overfitting</b>. "
        "In production concurrent and distributed systems, localized unit tests rarely constitute an exhaustive formal specification. "
        "A generated patch can easily satisfy visible test assertions while violating broader systemic invariants, such as two-phase commit rollback completeness, "
        "lease fencing tokens, fair lock starvation boundaries, or multi-tenant isolation.", body))
    story.append(Paragraph(
        "When repair agents are evaluated exclusively against visible tests, the evaluation cannot distinguish between genuine invariant restoration "
        "and specification exploitation (patches that alter control flow solely to silence failing assertions). This paper investigates this gap through three research questions:", body))
    story.append(Paragraph("&bull; <b>RQ1 (The Invariant Gap):</b> To what extent does passing visible unit tests predict success against held-out architectural invariant suites?", bullet))
    story.append(Paragraph("&bull; <b>RQ2 (Comparative Effectiveness):</b> Does speculative exploration via disposable workspace replay outperform standard failure feedback in discovering invariant-preserving repairs?", bullet))
    story.append(Paragraph("&bull; <b>RQ3 (Computational Cost & Tradeoffs):</b> What is the inference budget tradeoff (in model calls and token consumption) across repair paradigms?", bullet))

    # Section 2: Architecture
    story.append(Paragraph("2. RETRACE System Architecture", h1))
    story.append(Paragraph(
        "RETRACE enforces three architectural principles: physical dual-suite oracle containment, disposable workspace exploration, and tamper-evident cryptographic provenance.", body))
    story.append(Paragraph(
        "<b>Dual-Suite Isolation:</b> Visible unit tests (<code>test_public.py</code>) reside in the repository workspace. Held-out invariant suites "
        "(<code>heldout.py</code>) and reference solutions are quarantined outside the repository. Zero prompt leakage is mathematically verified prior to every evaluation.", bullet))
    story.append(Paragraph(
        "<b>Disposable Workspace Replay:</b> Rather than mutating a single working directory, speculative candidate patches are evaluated in isolated temporary filesystem clones in <code>/tmp</code>. Only candidates passing all public tests are scored and ranked.", bullet))
    story.append(Paragraph(
        "<b>Cryptographic Provenance:</b> Every evaluation produces pre-run snapshots of input digests and post-run execution captures sealed into an immutable SHA-256 evidence manifest (<code>evidence-manifest.json</code>).", bullet))

    # Section 3: Methodology
    story.append(Paragraph("3. Experimental Methodology", h1))
    story.append(Paragraph(
        "We evaluated <b>30 enterprise distributed systems tasks</b> grouped into six architectural clusters: Transactional Durability (6 tasks), "
        "Concurrency & CRDTs (5 tasks), Fault Tolerance Sagas (6 tasks), Multi-Tenant Isolation (5 tasks), Traffic & Resource Pools (5 tasks), and "
        "Coordination & Consensus (3 tasks). All tasks were hardened using an automated AST mutation engine (142 mutants generated, 116 killed, achieving an <b>81.7% mutation kill score</b>).", body))

    # Table 1: Config
    story.append(Paragraph("<b>Table 1: Standardized Experimental Configuration Across Arms</b>", h2))
    config_data = [
        [Paragraph("<b>Dimension</b>", table_header), Paragraph("<b>Operational Specification</b>", table_header)],
        [Paragraph("Evaluated Models", table_cell), Paragraph("<code>openai/gpt-oss-120b</code> (Groq), <code>qwen/qwen3.8-27b</code> (Alibaba via Groq)", table_cell)],
        [Paragraph("Attempt Budget (K)", table_cell), Paragraph("K = 2 attempts maximum per arm (sequential turns or exploratory branches)", table_cell)],
        [Paragraph("Sampling Temperature", table_cell), Paragraph("T = 0.7 for stochastic Resampling; T = 0.0 for deterministic Feedback & Replay", table_cell)],
        [Paragraph("Random Seed Base", table_cell), Paragraph("Pinned seed 42 forwarded to provider endpoints for request reproducibility", table_cell)],
        [Paragraph("Format Retries", table_cell), Paragraph("Bounded to &le; 2 structured retries on malformed JSON edit specifications", table_cell)],
        [Paragraph("Rate-Limit Backoff", table_cell), Paragraph("Autonomous 240s window backoff with durable on-disk checkpoints on HTTP 429", table_cell)],
        [Paragraph("Prompt Isolation", table_cell), Paragraph("Public tests only; held-out verifiers and reference implementations strictly quarantined", table_cell)],
        [Paragraph("Execution Sandbox", table_cell), Paragraph("Ephemeral temporary working directories in <code>/tmp</code>; root repository never mutated", table_cell)],
        [Paragraph("Token Accounting", table_cell), Paragraph("Direct provider-reported prompt and completion token counts audited from API responses", table_cell)],
    ]
    t_config = Table(config_data, colWidths=[120, 384])
    t_config.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#F9FAFB"), colors.white]),
    ]))
    story.append(t_config)
    story.append(Spacer(1, 10))

    # Section 4: Results
    story.append(Paragraph("4. Empirical Results", h1))
    story.append(Paragraph(
        "A total of 180 controlled matrix evaluations were executed across both model families. Figure 1 and Table 2 present the headline comparison.", body))

    # Embedded Chart Image
    chart_img_path = "paper/retrace_results_chart.png"
    if os.path.exists(chart_img_path):
        story.append(Image(chart_img_path, width=490, height=230))
        story.append(Paragraph("<i>Figure 1: Public test pass rates vs. held-out invariant pass rates across 3 repair paradigms and 2 model families (N = 30 tasks, 180 evaluations). Descriptive results illustrating the severe invariant overestimation gap.</i>", caption_style))

    # Table 2: Benchmark Results
    story.append(Paragraph("<b>Table 2: Cross-Model Enterprise Benchmark Performance Summary (N = 30 tasks, 180 runs)</b>", h2))
    res_data = [
        [Paragraph("<b>Strategy</b>", table_header), Paragraph("<b>Model</b>", table_header),
         Paragraph("<b>Public Pass</b>", table_header), Paragraph("<b>Held-Out Pass</b>", table_header),
         Paragraph("<b>Gap (pp)</b>", table_header), Paragraph("<b>Calls</b>", table_header),
         Paragraph("<b>Tokens</b>", table_header), Paragraph("<b>Tok / Succ</b>", table_header)],
        [Paragraph("Resample", table_cell), Paragraph("GPT-OSS-120B", table_cell), Paragraph("73.3% (22/30)", table_cell), Paragraph("43.3% (13/30)", table_cell), Paragraph("30.0 pp", table_cell), Paragraph("31", table_cell), Paragraph("90,248", table_cell), Paragraph("6,942.2", table_cell)],
        [Paragraph("Resample", table_cell), Paragraph("Qwen-27B", table_cell), Paragraph("66.7% (20/30)", table_cell), Paragraph("30.0% (9/30)", table_cell), Paragraph("36.7 pp", table_cell), Paragraph("36", table_cell), Paragraph("73,285", table_cell), Paragraph("8,142.8", table_cell)],
        [Paragraph("Feedback", table_cell), Paragraph("GPT-OSS-120B", table_cell), Paragraph("<b>83.3% (25/30)</b>", table_cell), Paragraph("43.3% (13/30)", table_cell), Paragraph("40.0 pp", table_cell), Paragraph("32", table_cell), Paragraph("123,488", table_cell), Paragraph("9,499.1", table_cell)],
        [Paragraph("Feedback", table_cell), Paragraph("Qwen-27B", table_cell), Paragraph("<b>86.7% (26/30)</b>", table_cell), Paragraph("23.3% (7/30)", table_cell), Paragraph("<b>63.3 pp</b>", table_cell), Paragraph("30", table_cell), Paragraph("79,944", table_cell), Paragraph("11,420.6", table_cell)],
        [Paragraph("Replay", table_cell), Paragraph("GPT-OSS-120B", table_cell), Paragraph("<b>83.3% (25/30)</b>", table_cell), Paragraph("<b>46.7% (14/30)</b>", table_cell), Paragraph("36.6 pp", table_cell), Paragraph("57", table_cell), Paragraph("222,880", table_cell), Paragraph("15,920.0", table_cell)],
        [Paragraph("Replay", table_cell), Paragraph("Qwen-27B", table_cell), Paragraph("<b>86.7% (26/30)</b>", table_cell), Paragraph("20.0% (6/30)", table_cell), Paragraph("<b>66.7 pp</b>", table_cell), Paragraph("54", table_cell), Paragraph("155,111", table_cell), Paragraph("25,851.8", table_cell)],
    ]
    t_res = Table(res_data, colWidths=[55, 75, 68, 70, 52, 32, 58, 54])
    t_res.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#F9FAFB"), colors.white]),
    ]))
    story.append(t_res)
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>4.1 RQ1: The Public-to-Held-Out Invariant Gap</b>", h2))
    story.append(Paragraph(
        "On GPT-OSS-120B, Feedback achieved an 83.3% public pass rate, but only 43.3% held-out invariant correctness (a 40.0 percentage point drop). "
        "In 12 of 30 tasks, patches silenced visible CI tests while violating hidden invariants. "
        "On Qwen-27B, the gap widened dramatically to <b>63.3 percentage points</b> (19/30 = 63.33%): Feedback passed visible tests in 26/30 tasks (86.7%) "
        "but satisfied held-out invariants in only 7/30 tasks (23.3%). Visible unit tests consistently overestimate invariant correctness across models.", body))

    story.append(Paragraph("<b>4.2 RQ2: Statistical Significance (McNemar Paired Tests)</b>", h2))
    story.append(Paragraph(
        "Exact two-tailed paired McNemar tests were conducted on the held-out invariant suite (N = 30):<br/>"
        "&bull; <b>GPT-OSS-120B (Replay vs. Feedback):</b> 10 both pass, 13 both fail, 4 Replay-only wins, 3 Feedback-only wins (discordant 4 vs. 3, <b>p = 1.000</b>).<br/>"
        "&bull; <b>Qwen-27B (Replay vs. Feedback):</b> 4 both pass, 21 both fail, 2 Replay-only wins, 3 Feedback-only wins (discordant 2 vs. 3, <b>p = 1.000</b>).<br/>"
        "<b>Interpretation:</b> The experimental evidence does not support the hypothesis that Replay is statistically superior to Feedback. "
        "Importantly, a non-significant result (p = 1.000) <b>does not establish equivalence</b> between the strategies; rather, it reflects bounded "
        "statistical power at N = 30, where subtle effect sizes cannot be distinguished from random variance.", body))

    story.append(Paragraph("<b>4.3 RQ3: Inference Budget Economics</b>", h2))
    story.append(Paragraph(
        "Replay incurred an <b>80.5% token cost premium</b> over Feedback on GPT-OSS-120B (222,880 vs. 123,488 tokens; 15,920 vs. 9,499 tokens per held-out success). "
        "The marginal cost of the single additional repair gained by Replay was 99,392 tokens. On Qwen-27B, Replay required 25,851 tokens per success "
        "compared to 8,143 for single-shot Resampling.", body))

    # Section 5: Qualitative Analysis
    story.append(Paragraph("5. Qualitative Trade-off Analysis", h1))
    story.append(Paragraph(
        "<b>When Replay Prevents Overfitting:</b> In <code>enterprise_circuit_breaker</code>, Feedback observed a reset timeout error and inserted a blanket reset clearing failure counters prematurely, satisfying visible assertions but breaking half-open probation invariants. Replay explored disposable sandboxes and selected a candidate that preserved probation semantics.", bullet))
    story.append(Paragraph(
        "<b>When Feedback is Optimal:</b> In <code>enterprise_wal_replay</code>, the failure was an unhandled <code>EOFError</code> on log truncation. Feedback resolved the defect in 1 turn (1,200 tokens) with a clean exception guard. Replay explored multi-file framing headers, consuming 8,000 tokens without success. For localized defects, Feedback is vastly more economical.", bullet))

    # Section 6: Threats to Validity
    story.append(Paragraph("6. Threats to Validity & Methodological Boundaries", h1))
    story.append(Paragraph("&bull; <b>Synthetic Benchmark Realism:</b> Tasks are curated enterprise distributed patterns (200–800 LOC) rather than multi-million-line legacy enterprise monoliths.", bullet))
    story.append(Paragraph("&bull; <b>Sample Size & Statistical Power (N = 30):</b> Evaluating 30 tasks limits the statistical power of paired McNemar tests. Detecting smaller effect sizes requires larger task banks.", bullet))
    story.append(Paragraph("&bull; <b>Model & Provider Variation:</b> We evaluated two open-weights models (120B and 27B) hosted via Groq Cloud. Proprietary inference optimizations (e.g. FP8 serving) and reasoning models (e.g. o3-mini) may alter dynamics.", bullet))
    story.append(Paragraph("&bull; <b>Verifier Oracle Completeness:</b> Despite an 81.7% mutation kill score, dynamic test execution cannot formally prove the absence of subtle concurrency race conditions.", bullet))

    # Section 7: Conclusion & References
    story.append(Paragraph("7. Conclusion", h1))
    story.append(Paragraph(
        "This empirical study demonstrates that in enterprise distributed systems repair, <b>passing public unit tests is an unreliable indicator of invariant correctness</b>. "
        "Across 180 controlled evaluations, public test pass rates (83.3%–86.7%) dramatically overestimated held-out correctness (20.0%–46.7%). "
        "While Counterfactual Replay provides defense against overfitting in state machines, it incurs an 80.5% token premium without statistically significant dominance (p = 1.000). "
        "All code, execution logs, and cryptographic manifests are publicly available at release tag <code>v1.9.0-research-release</code>.", body))

    story.append(Spacer(1, 6))
    story.append(Paragraph("References", h1))
    story.append(Paragraph("[1] C. E. Jimenez et al., 'SWE-bench: Can Language Models Resolve Real-World GitHub Issues?' <i>ICLR</i>, 2024.<br/>"
                           "[2] R. Just et al., 'Defects4J: A database of existing faults for Java programs,' <i>ISSTA</i>, 2014.<br/>"
                           "[3] C. Le Goues et al., 'GenProg: A generic method for automated software repair,' <i>IEEE TSE</i>, 2012.<br/>"
                           "[4] Y. Li et al., 'Competition-level code generation with AlphaCode,' <i>Science</i>, vol. 378, 2022.<br/>"
                           "[5] N. Shinn et al., 'Reflexion: Language agents with verbal reinforcement learning,' <i>NeurIPS</i>, 2023.<br/>"
                           "[6] E. K. Smith et al., 'Is the cure worse than the disease? Overfitting in APR,' <i>ESEC/FSE</i>, 2015.<br/>"
                           "[7] Q. McNemar, 'Note on the sampling error of the difference between correlated proportions,' <i>Psychometrika</i>, 1947.", ParagraphStyle("Refs", parent=body, fontSize=7.5, leading=10.5)))

    # Build the document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully compiled publication PDF to: {pdf_path}")
    print(f"PDF size: {os.path.getsize(pdf_path):,} bytes")

if __name__ == "__main__":
    build_pdf()
