"""
Generate publication-quality grouped bar charts comparing Public vs. Held-Out
repair success across three strategies and two frontier model families.
"""

import os
import matplotlib.pyplot as plt
import numpy as np

def generate_chart():
    os.makedirs("docs", exist_ok=True)
    os.makedirs("paper", exist_ok=True)

    # Data
    # 30 tasks total per model
    # GPT-OSS-120B:
    #   Resample: Public 22/30 (73.3%), Held-out 13/30 (43.3%)
    #   Feedback: Public 25/30 (83.3%), Held-out 13/30 (43.3%)
    #   Replay:   Public 25/30 (83.3%), Held-out 14/30 (46.7%)
    # Qwen-27B:
    #   Resample: Public 20/30 (66.7%), Held-out 9/30 (30.0%)
    #   Feedback: Public 26/30 (86.7%), Held-out 7/30 (23.3%)
    #   Replay:   Public 26/30 (86.7%), Held-out 6/30 (20.0%)

    models = ["GPT-OSS-120B (Groq)", "Qwen3.8-27B (Alibaba)"]
    strategies = ["Resample", "Feedback", "Replay"]

    gpt_public = [73.3, 83.3, 83.3]
    gpt_heldout = [43.3, 43.3, 46.7]

    qwen_public = [66.7, 86.7, 86.7]
    qwen_heldout = [30.0, 23.3, 20.0]

    # Style configuration
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Helvetica", "Arial", "DejaVu Sans"]
    plt.rcParams["axes.edgecolor"] = "#333333"
    plt.rcParams["axes.linewidth"] = 0.8

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5.2), sharey=True, dpi=300)

    x = np.arange(len(strategies))
    width = 0.35

    # Color palette
    color_public = "#2563EB"   # Royal Blue
    color_heldout = "#DC2626"  # Crimson / Dark Red

    # Panel 1: GPT-OSS-120B
    rects1 = ax1.bar(x - width/2, gpt_public, width, label="Visible Public Tests", color=color_public, edgecolor="#1D4ED8", alpha=0.9)
    rects2 = ax1.bar(x + width/2, gpt_heldout, width, label="Held-Out Invariants", color=color_heldout, edgecolor="#B91C1C", alpha=0.9)

    ax1.set_title("openai/gpt-oss-120b\n(Frontier 120B Baseline)", fontsize=12, fontweight="bold", pad=12)
    ax1.set_xticks(x)
    ax1.set_xticklabels(strategies, fontsize=11, fontweight="medium")
    ax1.set_ylabel("Pass Rate (%)", fontsize=11, fontweight="bold")
    ax1.set_ylim(0, 105)
    ax1.grid(axis="y", linestyle="--", alpha=0.3, zorder=0)
    ax1.set_axisbelow(True)

    # Value labels for GPT
    for rect in rects1:
        h = rect.get_height()
        ax1.annotate(f"{h:.1f}%",
                    xy=(rect.get_x() + rect.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=9, fontweight="bold", color="#1E3A8A")

    for rect in rects2:
        h = rect.get_height()
        ax1.annotate(f"{h:.1f}%",
                    xy=(rect.get_x() + rect.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=9, fontweight="bold", color="#7F1D1D")

    # Annotate gap on Feedback
    ax1.annotate("−40.0 pp\nGap",
                 xy=(1, 63.3), xytext=(1, 62),
                 ha="center", va="center",
                 bbox=dict(boxstyle="round,pad=0.3", fc="#FEF2F2", ec="#EF4444", lw=1),
                 fontsize=8.5, fontweight="bold", color="#991B1B")

    # Panel 2: Qwen-27B
    rects3 = ax2.bar(x - width/2, qwen_public, width, label="Visible Public Tests", color=color_public, edgecolor="#1D4ED8", alpha=0.9)
    rects4 = ax2.bar(x + width/2, qwen_heldout, width, label="Held-Out Invariants", color=color_heldout, edgecolor="#B91C1C", alpha=0.9)

    ax2.set_title("qwen/qwen3.8-27b\n(Cross-Family 27B Comparison)", fontsize=12, fontweight="bold", pad=12)
    ax2.set_xticks(x)
    ax2.set_xticklabels(strategies, fontsize=11, fontweight="medium")
    ax2.grid(axis="y", linestyle="--", alpha=0.3, zorder=0)
    ax2.set_axisbelow(True)

    # Value labels for Qwen
    for rect in rects3:
        h = rect.get_height()
        ax2.annotate(f"{h:.1f}%",
                    xy=(rect.get_x() + rect.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=9, fontweight="bold", color="#1E3A8A")

    for rect in rects4:
        h = rect.get_height()
        ax2.annotate(f"{h:.1f}%",
                    xy=(rect.get_x() + rect.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=9, fontweight="bold", color="#7F1D1D")

    # Annotate gap on Feedback
    ax2.annotate("−63.3 pp\nGap",
                 xy=(1, 55.0), xytext=(1, 55.0),
                 ha="center", va="center",
                 bbox=dict(boxstyle="round,pad=0.3", fc="#FEF2F2", ec="#EF4444", lw=1),
                 fontsize=8.5, fontweight="bold", color="#991B1B")

    # Shared Legend
    handles, labels = ax1.get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.05),
               ncol=2, frameon=True, fontsize=10, edgecolor="#D1D5DB")

    plt.suptitle("Public vs. Held-Out Repair Success: 30-Task Enterprise Benchmark (N = 30 tasks, 180 runs)",
                 fontsize=13, fontweight="bold", y=1.09)

    plt.figtext(0.5, -0.04,
                "Descriptive empirical results. Passing visible unit tests severely overestimates held-out invariant correctness across both model families.\n"
                "Paired McNemar exact tests between Feedback and Replay indicate no statistically significant difference (p = 1.000).",
                ha="center", fontsize=9, style="italic", color="#4B5563")

    plt.tight_layout()

    png_path = "docs/retrace_results_chart.png"
    svg_path = "docs/retrace_results_chart.svg"
    paper_png = "paper/retrace_results_chart.png"

    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    fig.savefig(svg_path, bbox_inches="tight")
    fig.savefig(paper_png, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Generated chart saved to:\n  - {png_path}\n  - {svg_path}\n  - {paper_png}")

if __name__ == "__main__":
    generate_chart()
