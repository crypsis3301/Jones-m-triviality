#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plot cumulative probabilities P_m(N) for Jm-triviality across crossing numbers.

P_m(N) = Pr(m appears in knots with up to N crossings)
       = sum_{i<=N} [n(i crossings) / n(total up to 19)] * Pr(m | i)
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import rcParams

# Number of prime knots by crossing number (from OEIS A002863)
KNOT_COUNTS = {
    3: 1,
    4: 1,
    5: 2,
    6: 3,
    7: 7,
    8: 21,
    9: 49,
    10: 165,
    11: 552,
    12: 2176,
    13: 9988,
    14: 46972,
    15: 253293,
    16: 1388705,
    17: 8053393,
    18: 48266466,
    19: 294130458
}

# Color schemes
COLOR_SCHEMES = {
    'green': {
        1: '#70DFFF',  # Cyan
        2: '#70DFFF',  
        3: '#70DFCC',  
        4: '#70DFAA',  
        5: '#70DF99',  
        6: '#70DF88',  
        7: '#70DF77',  
        8: '#70DF66',  
        9: '#70DF55',  
        10: '#70DF44',
        'shadow': 'rgba(50, 255, 155, 0.3)',
        'title': '#00FFFF',
        'bg': '#000000',
        'text': '#FFFFFF',
        'grid': '#00FFFF'
    },
    'purple': {
        1: '#A03FFF',
        2: '#903FFF',  
        3: '#803FCC',  
        4: '#703FAA',  
        5: '#603F88',  
        6: '#503F66',  
        7: '#403F55',  
        8: '#303F44',  
        9: '#203F33',
        10: '#103F22',
        'shadow': 'rgba(150, 55, 255, 0.3)',
        'title': '#A01FFF',
        'bg': '#000000',
        'text': '#FFFFFF',
        'grid': '#A01FFF'
    },
    'light': {
        # Standard black lines for light background
        **{i: '#000000' for i in range(1, 11)},
        'bg': '#FFFFFF',
        'text': '#000000',
        'grid': '#CCCCCC'
    }
}

def compute_cumulative_probabilities(jm_probs_file):
    """
    Compute P_m(N) for each m and N.
    
    Args:
        jm_probs_file: Path to JSON with conditional probabilities
        
    Returns:
        dict: {m: [P_m(3), P_m(4), ..., P_m(17)]}
    """
    # Load conditional probabilities
    with open(jm_probs_file, 'r') as f:
        jm_probs = json.load(f)
    
    # Total knots up to 17 crossings
    total_knots = sum(KNOT_COUNTS.values())
    
    # Initialize cumulative probabilities for each m
    # m ranges from 2 to max observed (around 10)
    max_m = 10
    P_m = {m: [] for m in range(2, max_m + 1)}
    
    # For each crossing number N from 3 to 19
    for N in range(3, 20):
        # Compute P_m(N) for each m
        for m in range(2, max_m + 1):
            cumulative_prob = 0.0
            
            # Sum over all crossing numbers i <= N
            for i in range(3, N + 1):
                n_i = KNOT_COUNTS[i]
                str_i = str(i)
                
                # Get Pr(m | i) from the JSON
                if str_i in jm_probs:
                    probs_i = jm_probs[str_i]
                    # probs_i = [Pr(m=2|i), Pr(m=3|i), ..., Pr(m=max_m|i)]
                    # Index: m-2 gives us Pr(m | i)
                    m_index = m - 2
                    if m_index < len(probs_i):
                        pr_m_given_i = probs_i[m_index]
                    else:
                        pr_m_given_i = 0.0
                else:
                    # For crossing numbers 3-7, only m=2 exists
                    pr_m_given_i = 1.0 if m == 2 else 0.0
                
                # Add weighted contribution
                cumulative_prob += (n_i / total_knots) * pr_m_given_i
            
            P_m[m].append(cumulative_prob)
    
    return P_m


def plot_cumulative_probabilities(P_m, output_file='jm_cumulative_probs.pdf', 
                                 dark_theme=False, color_scheme='green'):
    """
    Create a professional plot of P_m(N) vs N.
    
    Args:
        P_m: Dictionary {m: [P_m(3), ..., P_m(18)]}
        output_file: Output filename (PDF recommended for papers)
        dark_theme: If True, use dark background
        color_scheme: 'green', 'purple', or 'light'
    """
    # Select color scheme
    if dark_theme:
        if color_scheme not in ['green', 'purple']:
            color_scheme = 'green'
        colors = COLOR_SCHEMES[color_scheme]
    else:
        colors = COLOR_SCHEMES['light']
    
    # Set up matplotlib for publication-quality plots
    rcParams['font.family'] = 'serif'
    rcParams['font.serif'] = ['DeJaVu Serif']
    rcParams['font.size'] = 11
    rcParams['axes.linewidth'] = 1.0
    rcParams['lines.linewidth'] = 1.5
    rcParams['xtick.major.width'] = 1.0
    rcParams['ytick.major.width'] = 1.0
    
    # Create figure with appropriate background
    fig = plt.figure(figsize=(10, 7), facecolor=colors['bg'], constrained_layout=True)
    ax = fig.add_subplot(111, facecolor=colors['bg'])
    
    # Crossing numbers on x-axis (data goes from 3 to 19)
    N_values = np.arange(3, 20)
    
    # Plot P_m(N) for m in [3, 10]
    lines_data = {}
    for m in range(3, 11):
        if m in P_m and P_m[m]:
            line, = ax.plot(
                N_values, 
                P_m[m],
                linestyle='-',
                color=colors[m],
                linewidth=2.0 if dark_theme else 1.5
            )
            lines_data[m] = (N_values, P_m[m])
    
    # Add inline labels near the end of each line
    for m, (x_vals, y_vals) in lines_data.items():
        # Position label at the right end of the line
        x_label = x_vals[-1] + 0.3
        y_label = y_vals[-1]
        
        bbox_props = dict(
            boxstyle='round,pad=0.3', 
            facecolor=colors['bg'] if dark_theme else 'white',
            edgecolor='none', 
            alpha=0.9
        )
        
        ax.text(
            x_label,
            y_label,
            f'$J_{{{m}}}$',
            fontsize=11,
            verticalalignment='center',
            horizontalalignment='left',
            color=colors[m],
            bbox=bbox_props
        )
    
    # Labels and title with appropriate colors
    ax.set_xlabel('Number of crossings $N$', fontsize=13, color=colors['text'])
    ax.set_ylabel('$P_m(N)$', fontsize=13, color=colors['text'])
    
    # Set text colors for ticks
    ax.tick_params(axis='x', colors=colors['text'])
    ax.tick_params(axis='y', colors=colors['text'])
    
    # Set spine colors
    for spine in ax.spines.values():
        spine.set_edgecolor(colors['text'])
        spine.set_linewidth(1.0)
    
    # Set logarithmic scale on y-axis
    ax.set_yscale('log')
    
    # Grid with appropriate color
    if dark_theme:
        ax.grid(True, alpha=0.2, color=colors['grid'], linestyle=':', linewidth=0.5)
    else:
        ax.grid(True, alpha=0.3, color=colors['grid'], linestyle='--', linewidth=0.5)
    
    # Set axis limits - extend x-axis to 20
    ax.set_xlim(3, 20)
    
    # Set y-axis limits with some padding
    all_values = [val for m in range(3, 11) if m in P_m and P_m[m] for val in P_m[m] if val > 0]
    if all_values:
        y_min = min(all_values)
        y_max = max(all_values)
        ax.set_ylim(y_min * 0.5, y_max * 2)
    

    # X-axis ticks at every crossing number up to 20
    ax.set_xticks(np.arange(3, 21))
    
    # Detect output format from filename
    output_format = output_file.split('.')[-1].lower()
    
    # Save settings
    save_kwargs = {
        'dpi': 300,
        'facecolor': fig.get_facecolor(),
        'edgecolor': 'none'
    }
    
    # Save the main file
    plt.savefig(output_file, **save_kwargs)
    print(f"✓ Saved plot to {output_file}")
    
    # Save PNG preview only if output is PDF
    if output_format == 'pdf':
        png_file = output_file.replace('.pdf', '.png')
        plt.savefig(png_file, **save_kwargs)
        print(f"✓ Saved PNG preview to {png_file}")
    
    plt.show()
    plt.close(fig)


def print_statistics(P_m):
    """
    Print summary statistics of cumulative probabilities.
    """
    print("\n" + "="*70)
    print("Cumulative Probability Statistics P_m(N)")
    print("="*70)
    print(f"{'m':<5} {'P_m(8)':<12} {'P_m(12)':<12} {'P_m(17)':<12} {'Growth':<12}")
    print("-"*70)
    
    for m in range(3, 11):
        if m in P_m and P_m[m]:
            p_8 = P_m[m][5] if len(P_m[m]) > 5 else 0.0  # N=8 is index 5
            p_12 = P_m[m][9] if len(P_m[m]) > 9 else 0.0  # N=12 is index 9
            p_17 = P_m[m][14] if len(P_m[m]) > 14 else 0.0  # N=17 is index 14
            
            if p_8 > 0:
                growth = f"{p_17/p_8:.2f}x"
            else:
                growth = "N/A"
            
            print(f"{m:<5} {p_8:<12.6f} {p_12:<12.6f} {p_17:<12.6f} {growth:<12}")
    
    print("="*70)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Plot cumulative probabilities of Jm-triviality"
    )
    parser.add_argument(
        'json_file',
        help='JSON file with conditional probabilities Pr(m|i)'
    )
    parser.add_argument(
        '-o', '--output',
        default='jm_cumulative_probs.pdf',
        help='Output file (default: jm_cumulative_probs.pdf)'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Print statistics table'
    )
    parser.add_argument(
        '--dark',
        action='store_true',
        help='Use dark theme (black background with neon colors)'
    )
    parser.add_argument(
        '--scheme',
        choices=['green', 'purple'],
        default='green',
        help='Color scheme for dark theme (default: green)'
    )
    
    args = parser.parse_args()
    
    # Compute cumulative probabilities
    print("Computing cumulative probabilities P_m(N)...")
    P_m = compute_cumulative_probabilities(args.json_file)
    
    # Print statistics if requested
    if args.stats:
        print_statistics(P_m)
    
    # Create plot
    print("\nGenerating plot...")
    plot_cumulative_probabilities(P_m, args.output, 
                                 dark_theme=args.dark,
                                 color_scheme=args.scheme)


if __name__ == '__main__':
    main()