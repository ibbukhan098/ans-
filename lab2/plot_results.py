import sys
import matplotlib.pyplot as plt
import numpy as np

def create_performance_plot(sp_results, tl_results):
    """
    Creates and saves a grouped bar chart from the provided performance data.

    Args:
        sp_results (list): A list of 3 throughput values for Shortest-Path.
        tl_results (list): A list of 3 throughput values for Two-Level.
    """
    labels = [
        'Single Flow\n(Baseline)',
        'Parallel Flows\n(Best Case)',
        'Parallel Flows\n(Worst Case)'
    ]

    x = np.arange(len(labels))
    width = 0.35 

    fig, ax = plt.subplots(figsize=(12, 7))

    rects1 = ax.bar(x - width/2, sp_results, width, label='Shortest-Path', color='#d9534f', alpha=0.9)
    rects2 = ax.bar(x + width/2, tl_results, width, label='Two-Level', color='#5cb85c', alpha=0.9)

    ax.set_ylabel('Aggregate Throughput (Mbps)', fontsize=12)
    ax.set_title('Performance Comparison of Routing Schemes', fontsize=16, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    ax.legend(fontsize=11)

    max_throughput = max(max(sp_results), max(tl_results))
    ax.set_ylim(0, max_throughput * 1.25)

    ax.bar_label(rects1, padding=3, fmt='%.1f')
    ax.bar_label(rects2, padding=3, fmt='%.1f')

    ax.yaxis.grid(True, linestyle='--', which='major', color='grey', alpha=0.5)

    fig.tight_layout()

    output_filename = 'routing_performance_comparison.png'
    try:
        plt.savefig(output_filename, dpi=300)
        print(f"\n Plot saved successfully as '{output_filename}'")
    except Exception as e:
        print(f"\n Error saving plot: {e}")

if __name__ == '__main__':
    if len(sys.argv) != 7:
        print("\n Error: Incorrect number of arguments.")
        print("Usage: python3 plot_results.py sp_single tl_single sp_parallel_best tl_parallel_best sp_parallel_worst tl_parallel_worst")
        print("\nExample: python3 plot_results.py 14.9 14.9 15.1 29.8 15.0 15.2")
        sys.exit(1)

    try:
        data = [float(arg) for arg in sys.argv[1:]]
        sp_data = [data[0], data[2], data[4]] 
        tl_data = [data[1], data[3], data[5]]  
        
        create_performance_plot(sp_data, tl_data)

    except ValueError:
        print("\n Error: All arguments must be numbers.")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

