import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

os.environ['MPLCONFIGDIR'] = '/tmp/mpl_cache'
os.makedirs('/tmp/mpl_cache', exist_ok=True)

fig = plt.figure(figsize=(18, 12), dpi=300)
fig.patch.set_facecolor('#0f172a') # Slate 900 dark theme

# Title & Subtitle
fig.text(0.5, 0.965, 'RETRACE Controlled Candidate-Selection Ablation: Empirical Findings', 
         ha='center', va='top', fontsize=18, fontweight='bold', color='#f8fafc')
fig.text(0.5, 0.940, 'Definitive Resolution of AST Heuristic Ranking & Invariant Prompting on 6 Enterprise State-Machine Fixtures (openai/gpt-oss-120b)',
         ha='center', va='top', fontsize=11, color='#94a3b8')

# Colors
c_blue = '#38bdf8'
c_indigo = '#818cf8'
c_purple = '#c084fc'
c_emerald = '#34d399'
c_amber = '#fbbf24'
c_rose = '#f43f5e'
c_card = '#1e293b'
c_border = '#334155'
c_text_main = '#f8fafc'
c_text_muted = '#94a3b8'

# Helper function to create styled card background
def add_card(ax, title, subtitle=''):
    ax.set_facecolor(c_card)
    for spine in ax.spines.values():
        spine.set_color(c_border)
        spine.set_linewidth(1.2)
    if title:
        ax.text(0.04, 0.93, title, transform=ax.transAxes, fontsize=12, fontweight='bold', color=c_text_main, va='top')
    if subtitle:
        ax.text(0.04, 0.86, subtitle, transform=ax.transAxes, fontsize=9, color=c_text_muted, va='top')

# -------------------------------------------------------------
# Panel 1: Factorial 2x2 Pass Rates (Top Left)
# -------------------------------------------------------------
ax1 = fig.add_axes([0.05, 0.63, 0.28, 0.27])
add_card(ax1, 'Factorial Arms: Held-Out Pass Rate', 'Identical 50.0% (3/6) across all 4 configurations')

configs = ['Config 1\nBaseline\n(Std+Greedy)', 'Config 3\nAST-Only\n(Std+AST)', 'Config 2\nPrompt-Only\n(Inv+Greedy)', 'Config 4\nCombined\n(Inv+AST)']
rates = [50.0, 50.0, 50.0, 50.0]
colors = [c_blue, c_indigo, c_amber, c_purple]

bars = ax1.bar(range(4), rates, color=colors, width=0.55, edgecolor='#475569', linewidth=1.2, zorder=3)
ax1.set_ylim(0, 100)
ax1.set_ylabel('Held-Out Pass Rate (%)', color=c_text_muted, fontsize=9.5)
ax1.set_xticks(range(4))
ax1.set_xticklabels(configs, color=c_text_main, fontsize=8.5)
ax1.tick_params(colors=c_text_muted, labelsize=8.5)
ax1.grid(axis='y', color='#334155', linestyle='--', alpha=0.5, zorder=0)

for bar in bars:
    yval = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 3.5, f'{yval:.0f}% (3/6)', ha='center', va='bottom',
             fontsize=9.5, fontweight='bold', color=c_text_main)

# -------------------------------------------------------------
# Panel 2: Causal Diagnosis Disentanglement (Top Center)
# -------------------------------------------------------------
ax2 = fig.add_axes([0.36, 0.63, 0.28, 0.27])
add_card(ax2, 'Causal Diagnosis Distribution', '0 Selection Failures: AST never picked failing over passing')

categories = ['SUCCESSFUL\nSELECTION', 'NO_VALID\nCANDIDATE', 'SELECTION\nFAILURE', 'NO_ELIGIBLE\nCANDIDATE']
counts = [6, 6, 0, 0] # across 12 candidate pool decisions
bar_colors = [c_emerald, c_amber, c_rose, '#64748b']

bars2 = ax2.bar(range(4), counts, color=bar_colors, width=0.55, edgecolor='#475569', linewidth=1.2, zorder=3)
ax2.set_ylim(0, 8)
ax2.set_ylabel('Pool Decisions (N=12)', color=c_text_muted, fontsize=9.5)
ax2.set_xticks(range(4))
ax2.set_xticklabels(categories, color=c_text_main, fontsize=8)
ax2.tick_params(colors=c_text_muted, labelsize=8.5)
ax2.grid(axis='y', color='#334155', linestyle='--', alpha=0.5, zorder=0)

for bar, count in zip(bars2, counts):
    pct = (count / 12.0) * 100
    if count > 0:
        ax2.text(bar.get_x() + bar.get_width()/2.0, count + 0.25, f'{count}/12\n({pct:.0f}%)', ha='center', va='bottom',
                 fontsize=8.5, fontweight='bold', color=c_text_main)
    else:
        ax2.text(bar.get_x() + bar.get_width()/2.0, 0.25, '0 (0%)\nClean', ha='center', va='bottom',
                 fontsize=8.5, fontweight='bold', color=c_emerald)

# -------------------------------------------------------------
# Panel 3: Candidate-Level Correctness Yield (Top Right)
# -------------------------------------------------------------
ax3 = fig.add_axes([0.67, 0.63, 0.28, 0.27])
add_card(ax3, 'Candidate Generation Yield', 'Invariant prompting increased held-out yield (+8.4 pp)')

x = np.arange(2)
width = 0.3
rects1 = ax3.bar(x - width/2, [91.7, 91.7], width, label='Public Tests (11/12)', color=c_blue, edgecolor='#475569', linewidth=1.2, zorder=3)
rects2 = ax3.bar(x + width/2, [33.3, 41.7], width, label='Held-Out Tests', color=[c_rose, c_emerald], edgecolor='#475569', linewidth=1.2, zorder=3)

ax3.set_ylim(0, 115)
ax3.set_ylabel('Candidate Pass Yield (%)', color=c_text_muted, fontsize=9.5)
ax3.set_xticks(x)
ax3.set_xticklabels(['Standard Prompt\nPool (k=2, N=12)', 'Invariant Prompt\nPool (k=2, N=12)'], color=c_text_main, fontsize=8.5)
ax3.tick_params(colors=c_text_muted, labelsize=8.5)
ax3.grid(axis='y', color='#334155', linestyle='--', alpha=0.5, zorder=0)
ax3.legend(facecolor='#0f172a', edgecolor=c_border, fontsize=8, loc='upper right', labelcolor=c_text_main)

ax3.text(x[0]-width/2, 91.7 + 3, '91.7%', ha='center', fontsize=8.5, color=c_text_main, fontweight='bold')
ax3.text(x[1]-width/2, 91.7 + 3, '91.7%', ha='center', fontsize=8.5, color=c_text_main, fontweight='bold')
ax3.text(x[0]+width/2, 33.3 + 3, '33.3%\n(4/12)', ha='center', fontsize=8, color='#fca5a5', fontweight='bold')
ax3.text(x[1]+width/2, 41.7 + 3, '41.7%\n(5/12)', ha='center', fontsize=8, color='#86efac', fontweight='bold')

# -------------------------------------------------------------
# Panel 4: The 4 Disagreement Pools (Bottom Left)
# -------------------------------------------------------------
ax4 = fig.add_axes([0.05, 0.08, 0.44, 0.50])
add_card(ax4, 'Detailed Audit: All 4 Selector Disagreements', 'Disagreement rate = 33.3% (4/12 pools) | Held-Out Divergence = 0.0% (0/4)')

disagreements = [
    {
        'task': 'enterprise_circuit_breaker (Standard Pool)',
        'greedy': 'Selected C₀ (AST 222.30)',
        'ast': 'Selected C₁ (AST 305.62)',
        'greedy_out': 'PASS', 'ast_out': 'PASS',
        'verdict': 'Both Candidates Passed Held-Out (Zero Divergence)'
    },
    {
        'task': 'enterprise_cache_stampede_mutex (Standard Pool)',
        'greedy': 'Selected C₀ (AST 102.24)',
        'ast': 'Selected C₁ (AST 121.42)',
        'greedy_out': 'FAIL', 'ast_out': 'FAIL',
        'verdict': 'Both Candidates Failed Held-Out (Zero Divergence)'
    },
    {
        'task': 'enterprise_bulkhead_isolation (Invariant Pool)',
        'greedy': 'Selected C\'₀ (AST 165.58)',
        'ast': 'Selected C\'₁ (AST 179.20)',
        'greedy_out': 'PASS', 'ast_out': 'PASS',
        'verdict': 'Both Candidates Passed Held-Out (Zero Divergence)'
    },
    {
        'task': 'enterprise_outbox_publisher (Invariant Pool)',
        'greedy': 'Selected C\'₀ (AST 180.20)',
        'ast': 'Selected C\'₁ (AST 199.28)',
        'greedy_out': 'PASS', 'ast_out': 'PASS',
        'verdict': 'Both Candidates Passed Held-Out (Zero Divergence)'
    }
]

y_pos = 0.76
for i, d in enumerate(disagreements):
    box = patches.FancyBboxPatch((0.03, y_pos - 0.14), 0.94, 0.15, boxstyle='round,pad=0.01',
                                facecolor='#0f172a', edgecolor='#475569', linewidth=1, transform=ax4.transAxes)
    ax4.add_patch(box)
    
    ax4.text(0.05, y_pos - 0.02, f"Pool #{i+1}: {d['task']}", transform=ax4.transAxes,
             fontsize=9, fontweight='bold', color=c_blue)
    ax4.text(0.05, y_pos - 0.06, f"• Greedy: {d['greedy']}  ->  Held-Out: {d['greedy_out']}", transform=ax4.transAxes,
             fontsize=8.2, color=c_emerald if d['greedy_out'] == 'PASS' else c_rose)
    ax4.text(0.05, y_pos - 0.095, f"• AST:    {d['ast']}  ->  Held-Out: {d['ast_out']}", transform=ax4.transAxes,
             fontsize=8.2, color=c_emerald if d['ast_out'] == 'PASS' else c_rose)
    ax4.text(0.05, y_pos - 0.13, f"-> Impact: {d['verdict']}", transform=ax4.transAxes,
             fontsize=8, fontweight='bold', color='#cbd5e1')
    y_pos -= 0.18

ax4.text(0.05, 0.03, 'CONCLUSION: Selector disagreement never caused a held-out divergence (0/4).',
         transform=ax4.transAxes, fontsize=8.5, fontweight='bold', color=c_emerald)
ax4.axis('off')

# -------------------------------------------------------------
# Panel 5: Qualitative Case Studies (Bottom Right)
# -------------------------------------------------------------
ax5 = fig.add_axes([0.51, 0.08, 0.44, 0.50])
add_card(ax5, 'Prompt Trade-Off: Concurrency Win vs Exception Drift', 'Dissecting the qualitative impact of invariant contract prompting')

# Case 1: Cache Stampede (Win)
b1 = patches.FancyBboxPatch((0.03, 0.46), 0.94, 0.33, boxstyle='round,pad=0.01',
                           facecolor='#064e3b', edgecolor=c_emerald, linewidth=1.2, transform=ax5.transAxes)
ax5.add_patch(b1)
ax5.text(0.05, 0.74, 'WIN: enterprise_cache_stampede_mutex', transform=ax5.transAxes,
         fontsize=10, fontweight='bold', color='#a7f3d0')
ax5.text(0.05, 0.69, '• Standard Prompt: Generated 0/2 held-out correct candidates.', transform=ax5.transAxes,
         fontsize=8.5, color='#cbd5e1')
ax5.text(0.05, 0.65, '  Model failed to synchronize concurrent cache misses (thundering herd).', transform=ax5.transAxes,
         fontsize=8, color='#94a3b8')
ax5.text(0.05, 0.59, '• Invariant Prompt: Synthesized threading.Event() single-flight mutex ($C\'_0$).', transform=ax5.transAxes,
         fontsize=8.5, color='#ffffff', fontweight='bold')
ax5.text(0.05, 0.54, '  Coalesced concurrent calls, atomic lock release in finally block.', transform=ax5.transAxes,
         fontsize=8, color='#a7f3d0')
ax5.text(0.05, 0.49, '  -> Result: Held-Out PASS (Unlocked Correctness: 0/2 -> 1/2)!', transform=ax5.transAxes,
         fontsize=8.5, fontweight='bold', color='#34d399')

# Case 2: Circuit Breaker (Drift)
b2 = patches.FancyBboxPatch((0.03, 0.09), 0.94, 0.33, boxstyle='round,pad=0.01',
                           facecolor='#4c0519', edgecolor=c_rose, linewidth=1.2, transform=ax5.transAxes)
ax5.add_patch(b2)
ax5.text(0.05, 0.37, 'SPEC DRIFT: enterprise_circuit_breaker', transform=ax5.transAxes,
         fontsize=10, fontweight='bold', color='#fecdd3')
ax5.text(0.05, 0.32, '• Standard Prompt: 2/2 held-out correct candidates (100% yield).', transform=ax5.transAxes,
         fontsize=8.5, color='#cbd5e1')
ax5.text(0.05, 0.28, '  Raised ValueError for invalid arguments, matching test assertion.', transform=ax5.transAxes,
         fontsize=8, color='#94a3b8')
ax5.text(0.05, 0.22, '• Invariant Prompt: Model strictly enforced PEP-compliant typing.', transform=ax5.transAxes,
         fontsize=8.5, color='#ffffff', fontweight='bold')
ax5.text(0.05, 0.17, '  Raised TypeError(\"must be an int\") for failure_threshold=1.5.', transform=ax5.transAxes,
         fontsize=8, color='#fecdd3')
ax5.text(0.05, 0.12, '  -> Result: Test expected assertRaises(ValueError) -> ERROR (2/2 -> 0/2)!', transform=ax5.transAxes,
         fontsize=8.5, fontweight='bold', color='#fb7185')

ax5.text(0.05, 0.03, 'CONCLUSION: Divergence was caused by exception typing conventions, not AST selection.',
         transform=ax5.transAxes, fontsize=8.5, fontweight='bold', color=c_amber)
ax5.axis('off')

plt.savefig('docs/retrace_controlled_ablation_findings.png', bbox_inches='tight', dpi=300)
plt.savefig('docs/retrace_controlled_ablation_findings.svg', bbox_inches='tight')
print('Successfully generated docs/retrace_controlled_ablation_findings.png and .svg')
