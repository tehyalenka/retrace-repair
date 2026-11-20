"""Generate the final, publication-grade RETRACE ablation results figure with exact scientific calibration."""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

os.environ['MPLCONFIGDIR'] = '/tmp/mpl_cache'
os.makedirs('/tmp/mpl_cache', exist_ok=True)

fig = plt.figure(figsize=(19, 12.5), dpi=300)
fig.patch.set_facecolor('#0b0f19') # Very dark slate navy

# Palette
c_bg = '#0b0f19'
c_card = '#151e2e'
c_card_inner = '#0d1522'
c_border = '#26354a'
c_border_light = '#3b4f69'
c_text_title = '#f8fafc'
c_text_main = '#e2e8f0'
c_text_muted = '#94a3b8'

c_blue = '#38bdf8'      # Config 1 (Baseline)
c_indigo = '#818cf8'    # Config 3 (AST-Only)
c_amber = '#fbbf24'     # Config 2 (Prompt-Only)
c_purple = '#c084fc'    # Config 4 (Combined)
c_emerald = '#34d399'   # Success / Pass
c_rose = '#f43f5e'      # Failure / Regression

# =========================================================================
# HEADER & TITLE BLOCK
# =========================================================================
fig.text(0.5, 0.965, 'RETRACE v2.0 Controlled Candidate-Selection Ablation: Empirical Findings', 
         ha='center', va='top', fontsize=18, fontweight='bold', color=c_text_title)
fig.text(0.5, 0.940, 'Factorial Disentanglement of AST Structural Ranking & Invariant Contract Prompting across 6 Enterprise State-Machine Fixtures',
         ha='center', va='top', fontsize=11, color=c_text_muted)

# Helper function to create styled card background
def add_card(ax, title, subtitle=''):
    ax.set_facecolor(c_card)
    for spine in ax.spines.values():
        spine.set_color(c_border)
        spine.set_linewidth(1.2)
    if title:
        ax.text(0.035, 0.935, title, transform=ax.transAxes, fontsize=11.5, fontweight='bold', color=c_text_title, va='top')
    if subtitle:
        ax.text(0.035, 0.865, subtitle, transform=ax.transAxes, fontsize=8.8, color=c_text_muted, va='top')

# =========================================================================
# TOP ROW: 3 KEY METRIC PANELS
# =========================================================================

# -------------------------------------------------------------
# Panel A: Factorial 2x2 Pass Rates with Uncertainty (Top Left)
# -------------------------------------------------------------
ax1 = fig.add_axes([0.045, 0.61, 0.285, 0.29])
add_card(ax1, 'Factorial Arms: Held-Out Pass Rate (N=6)', 'Identical 50.0% (3/6) pass rate across all 4 configurations')

configs = ['Config 1\nBaseline\n(Std+Greedy)', 'Config 3\nAST-Only\n(Std+AST)', 'Config 2\nPrompt-Only\n(Inv+Greedy)', 'Config 4\nCombined\n(Inv+AST)']
rates = [50.0, 50.0, 50.0, 50.0]
# Wilson 95% score interval for 3/6 is [18.8%, 81.2%] -> lower err = 31.2%, upper err = 31.2%
yerr = [[31.2, 31.2, 31.2, 31.2], [31.2, 31.2, 31.2, 31.2]]
colors = [c_blue, c_indigo, c_amber, c_purple]

bars = ax1.bar(range(4), rates, color=colors, width=0.52, edgecolor=c_border_light, linewidth=1.2, zorder=3)
ax1.errorbar(range(4), rates, yerr=yerr, fmt='none', ecolor='#94a3b8', elinewidth=1.6, capsize=4.5, capthick=1.4, zorder=4)

ax1.set_ylim(0, 105)
ax1.set_ylabel('Held-Out Pass Rate (%)', color=c_text_muted, fontsize=9)
ax1.set_xticks(range(4))
ax1.set_xticklabels(configs, color=c_text_main, fontsize=8)
ax1.tick_params(colors=c_text_muted, labelsize=8)
ax1.grid(axis='y', color='#26354a', linestyle='--', alpha=0.6, zorder=0)

for bar in bars:
    yval = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 2.5, f'{yval:.0f}% (3/6)', ha='center', va='bottom',
             fontsize=9, fontweight='bold', color=c_text_title)

ax1.text(0.5, 0.05, 'Wilson 95% CI: [18.8%, 81.2%] (High Small-Sample Uncertainty)\nPaired Difference across All Arms: Δ = 0.0 pp',
         transform=ax1.transAxes, ha='center', fontsize=7.5, color='#94a3b8', style='italic')

# -------------------------------------------------------------
# Panel B: Pool-Level Causal Diagnosis (Top Center)
# -------------------------------------------------------------
ax2 = fig.add_axes([0.355, 0.61, 0.290, 0.29])
add_card(ax2, 'Pool-Level Causal Diagnosis (12 Unique Pools)', '0 Selection Failures: AST never chose a failing patch over an eligible passing one')

categories = ['SUCCESSFUL\nSELECTION', 'NO_VALID\nCANDIDATE', 'SELECTION\nFAILURE', 'NO_ELIGIBLE\nCANDIDATE']
counts = [6, 6, 0, 0] # across 12 candidate pools
bar_colors = [c_emerald, c_amber, c_rose, '#64748b']

bars2 = ax2.bar(range(4), counts, color=bar_colors, width=0.52, edgecolor=c_border_light, linewidth=1.2, zorder=3)
ax2.set_ylim(0, 8.2)
ax2.set_ylabel('Unique Candidate Pools (N=12)', color=c_text_muted, fontsize=9)
ax2.set_xticks(range(4))
ax2.set_xticklabels(categories, color=c_text_main, fontsize=7.8)
ax2.tick_params(colors=c_text_muted, labelsize=8)
ax2.grid(axis='y', color='#26354a', linestyle='--', alpha=0.6, zorder=0)

for bar, count in zip(bars2, counts):
    pct = (count / 12.0) * 100
    if count > 0:
        ax2.text(bar.get_x() + bar.get_width()/2.0, count + 0.22, f'{count}/12\n({pct:.0f}%)', ha='center', va='bottom',
                 fontsize=8.5, fontweight='bold', color=c_text_title)
    else:
        ax2.text(bar.get_x() + bar.get_width()/2.0, 0.22, '0 / 12\n(0.0%)', ha='center', va='bottom',
                 fontsize=8.5, fontweight='bold', color=c_emerald)

ax2.text(0.5, 0.05, 'Classification over 12 unique pools (6 Std + 6 Inv)\nNO_VALID_CANDIDATE denotes candidate-generation failure',
         transform=ax2.transAxes, ha='center', fontsize=7.5, color='#94a3b8', style='italic')

# -------------------------------------------------------------
# Panel C: Candidate-Level Correctness Yield (Top Right)
# -------------------------------------------------------------
ax3 = fig.add_axes([0.670, 0.61, 0.285, 0.29])
add_card(ax3, 'Candidate Generation Yield (k=2, N=12/arm)', 'Invariant prompting yielded descriptive +8.3 pp held-out gain')

x = np.arange(2)
width = 0.28
rects1 = ax3.bar(x - width/2, [91.7, 91.7], width, label='Public Smoke Pass (11/12)', color=c_blue, edgecolor=c_border_light, linewidth=1.2, zorder=3)
rects2 = ax3.bar(x + width/2, [33.3, 41.7], width, label='Held-Out Pass (4/12 vs 5/12)', color=[c_rose, c_emerald], edgecolor=c_border_light, linewidth=1.2, zorder=3)

ax3.set_ylim(0, 115)
ax3.set_ylabel('Candidate Pass Yield (%)', color=c_text_muted, fontsize=9)
ax3.set_xticks(x)
ax3.set_xticklabels(['Standard Prompt Arm\n(Pool N=12 candidates)', 'Invariant Prompt Arm\n(Pool N=12 candidates)'], color=c_text_main, fontsize=8)
ax3.tick_params(colors=c_text_muted, labelsize=8)
ax3.grid(axis='y', color='#26354a', linestyle='--', alpha=0.6, zorder=0)
ax3.legend(facecolor=c_card_inner, edgecolor=c_border, fontsize=7.8, loc='upper right', labelcolor=c_text_main)

ax3.text(x[0]-width/2, 91.7 + 2.5, '91.7%', ha='center', fontsize=8.2, color=c_text_title, fontweight='bold')
ax3.text(x[1]-width/2, 91.7 + 2.5, '91.7%', ha='center', fontsize=8.2, color=c_text_title, fontweight='bold')
ax3.text(x[0]+width/2, 33.3 + 2.5, '33.3%\n(4/12)', ha='center', fontsize=8, color='#fca5a5', fontweight='bold')
ax3.text(x[1]+width/2, 41.7 + 2.5, '41.7%\n(5/12)', ha='center', fontsize=8, color='#86efac', fontweight='bold')

ax3.text(0.5, 0.05, 'Public eligibility identical (91.7% in both pools)\nDescriptive yield delta: +8.3 percentage points',
         transform=ax3.transAxes, ha='center', fontsize=7.5, color='#94a3b8', style='italic')

# =========================================================================
# BOTTOM ROW: DETAILED AUDITS & QUALITATIVE CASE STUDIES
# =========================================================================

# -------------------------------------------------------------
# Panel D: Detailed Disagreement Audit (Bottom Left)
# -------------------------------------------------------------
ax4 = fig.add_axes([0.045, 0.12, 0.445, 0.45])
add_card(ax4, 'Selector Disagreement Audit: All 4 Divergence Pools', 'Disagreement rate = 33.3% (4/12 unique pools) | Outcome-Changing Divergence = 0.0% (0/4)')

disagreements = [
    {
        'task': 'Pool #1: enterprise_circuit_breaker (Standard Pool)',
        'greedy': 'Selected C₀ (AST 222.30)', 'ast': 'Selected C₁ (AST 305.62)',
        'greedy_out': 'PASS', 'ast_out': 'PASS',
        'verdict': 'Both Candidates Passed Held-Out Invariants (Outcome Delta = 0)'
    },
    {
        'task': 'Pool #4: enterprise_cache_stampede_mutex (Standard Pool)',
        'greedy': 'Selected C₀ (AST 102.24)', 'ast': 'Selected C₁ (AST 121.42)',
        'greedy_out': 'FAIL', 'ast_out': 'FAIL',
        'verdict': 'Both Candidates Failed Held-Out Invariants (Outcome Delta = 0)'
    },
    {
        'task': 'Pool #5: enterprise_bulkhead_isolation (Invariant Pool)',
        'greedy': 'Selected C\'₀ (AST 165.58)', 'ast': 'Selected C\'₁ (AST 179.20)',
        'greedy_out': 'PASS', 'ast_out': 'PASS',
        'verdict': 'Both Candidates Passed Held-Out Invariants (Outcome Delta = 0)'
    },
    {
        'task': 'Pool #6: enterprise_outbox_publisher (Invariant Pool)',
        'greedy': 'Selected C\'₀ (AST 180.20)', 'ast': 'Selected C\'₁ (AST 199.28)',
        'greedy_out': 'PASS', 'ast_out': 'PASS',
        'verdict': 'Both Candidates Passed Held-Out Invariants (Outcome Delta = 0)'
    }
]

y_pos = 0.77
for i, d in enumerate(disagreements):
    box = patches.FancyBboxPatch((0.025, y_pos - 0.13), 0.95, 0.145, boxstyle='round,pad=0.008',
                                facecolor=c_card_inner, edgecolor=c_border, linewidth=1, transform=ax4.transAxes)
    ax4.add_patch(box)
    
    ax4.text(0.045, y_pos - 0.015, d['task'], transform=ax4.transAxes,
             fontsize=8.8, fontweight='bold', color=c_blue if 'Standard' in d['task'] else c_purple)
    
    c_g_color = c_emerald if d['greedy_out'] == 'PASS' else c_rose
    c_a_color = c_emerald if d['ast_out'] == 'PASS' else c_rose
    
    ax4.text(0.045, y_pos - 0.052, f"• Greedy: {d['greedy']}  ->  Held-Out: {d['greedy_out']}", transform=ax4.transAxes,
             fontsize=8, color=c_g_color)
    ax4.text(0.045, y_pos - 0.085, f"• AST:    {d['ast']}  ->  Held-Out: {d['ast_out']}", transform=ax4.transAxes,
             fontsize=8, color=c_a_color)
    ax4.text(0.045, y_pos - 0.118, f"-> Impact: {d['verdict']}", transform=ax4.transAxes,
             fontsize=7.8, fontweight='bold', color='#cbd5e1')
    y_pos -= 0.175

ax4.text(0.045, 0.035, 'EMPIRICAL TAKEAWAY: Switching selectors changed patch identity, but had zero effect on held-out pass rate.',
         transform=ax4.transAxes, fontsize=8, fontweight='bold', color=c_emerald)
ax4.axis('off')

# -------------------------------------------------------------
# Panel E: Qualitative Mechanism Case Studies (Bottom Right)
# -------------------------------------------------------------
ax5 = fig.add_axes([0.510, 0.12, 0.445, 0.45])
add_card(ax5, 'Prompt Mechanism Dissection & Specification Audit', 'Investigating Candidate-Generation Divergence under Invariant Prompting')

# Case 1: Cache Stampede (Concurrency Invariant Discovery)
b1 = patches.FancyBboxPatch((0.025, 0.48), 0.95, 0.32, boxstyle='round,pad=0.008',
                           facecolor='#092c21', edgecolor=c_emerald, linewidth=1.2, transform=ax5.transAxes)
ax5.add_patch(b1)
ax5.text(0.045, 0.755, 'CONCURRENCY INVARIANT WIN: enterprise_cache_stampede_mutex', transform=ax5.transAxes,
         fontsize=9.2, fontweight='bold', color='#a7f3d0')
ax5.text(0.045, 0.705, '• Standard Prompt: 0/2 held-out correct candidates (un-synchronized thundering herd).', transform=ax5.transAxes,
         fontsize=8, color='#cbd5e1')
ax5.text(0.045, 0.655, '• Invariant Prompt: Synthesized single-flight mutex using threading.Event() ($C\'_0$).', transform=ax5.transAxes,
         fontsize=8, color='#ffffff', fontweight='bold')
ax5.text(0.045, 0.605, '  Coalesced concurrent cache misses, releasing lock in atomic finally block.', transform=ax5.transAxes,
         fontsize=7.8, color='#a7f3d0')
ax5.text(0.045, 0.555, '• Result: Unlocked Held-Out PASS (0/2 -> 1/2 passing candidates in pool)!', transform=ax5.transAxes,
         fontsize=8, fontweight='bold', color='#34d399')

# Case 2: Circuit Breaker (Authoritative Specification Audit)
b2 = patches.FancyBboxPatch((0.025, 0.11), 0.95, 0.33, boxstyle='round,pad=0.008',
                           facecolor='#350c18', edgecolor=c_rose, linewidth=1.2, transform=ax5.transAxes)
ax5.add_patch(b2)
ax5.text(0.045, 0.395, 'SPECIFICATION AUDIT: enterprise_circuit_breaker', transform=ax5.transAxes,
         fontsize=9.2, fontweight='bold', color='#fecdd3')
ax5.text(0.045, 0.345, '• Authoritative Contract: solution/circuit.py explicitly specifies raise ValueError for non-ints.', transform=ax5.transAxes,
         fontsize=8, color='#cbd5e1')
ax5.text(0.045, 0.295, '• Invariant Prompt Bias: Directed strict PEP typing -> model raised TypeError(\"must be int\").', transform=ax5.transAxes,
         fontsize=8, color='#ffffff', fontweight='bold')
ax5.text(0.045, 0.245, '• Test Assertion: with self.assertRaises(ValueError): CircuitBreaker(d, failure_threshold=1.5).', transform=ax5.transAxes,
         fontsize=7.8, color='#fecdd3')
ax5.text(0.045, 0.195, '• Finding: Under the reference specification, the patch is genuinely incorrect.', transform=ax5.transAxes,
         fontsize=8, fontweight='bold', color='#fb7185')

ax5.text(0.045, 0.035, 'EMPIRICAL TAKEAWAY: Regression was driven by prompt-induced exception mismatch, not AST selection bias.',
         transform=ax5.transAxes, fontsize=8, fontweight='bold', color=c_amber)
ax5.axis('off')

# =========================================================================
# BOTTOM FOOTER: SCIENTIFIC CALIBRATION & SCOPE BOUNDARY
# =========================================================================
footer_text = (
    "SCIENTIFIC CALIBRATION: The controlled ablation found no evidence of AST-induced selection failure across the six evaluated tasks. "
    "Although AST ranking changed candidate selection in 4 of 12 pools, these changes did not alter held-out correctness (Δ = 0.0 pp). "
    "No aggregate interaction effect was observed between invariant prompting and AST selection in this six-task exploratory evaluation."
)
fig.text(0.5, 0.050, footer_text, ha='center', va='center', fontsize=8.2, color='#cbd5e1',
         bbox=dict(boxstyle='round,pad=0.5', facecolor='#151e2e', edgecolor='#3b4f69', linewidth=1))

output_png = 'docs/retrace_final_ablation_results.png'
output_svg = 'docs/retrace_final_ablation_results.svg'
plt.savefig(output_png, bbox_inches='tight', dpi=300)
plt.savefig(output_svg, bbox_inches='tight')
print(f"Successfully generated {output_png} and {output_svg}")
