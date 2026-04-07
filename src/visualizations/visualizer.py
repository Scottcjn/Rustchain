import json
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


def visualize_hardware_fingerprint(data):
    """Creates a radar chart visualizing the hardware fingerprint data."""
    categories = list(data.keys())
    values = list(data.values())
    
    N = len(categories)
    angles = [n / float(N) * 2 * 3.141592653589793 for n in range(N)]  # Convert to radians
    values += values[:1]  # Repeat the first value to close the circle
    angles += angles[:1]

    ax = plt.subplot(111, polar=True)
    ax.set_theta_offset(0)
    ax.set_theta_direction(-1)

    # Draw one axe per variable and add labels
    plt.xticks(angles[:-1], categories)

    # Draw ylabels
    ax.set_rlabel_position(0)  # Move radial labels away from plotted line
    plt.yticks([0.2, 0.4, 0.6, 0.8, 1.0], ["0.2", "0.4", "0.6", "0.8", "1.0"], color="grey", size=7)
    plt.ylim(0, 1)

    # Plot and fill
    ax.plot(angles, values, color='blue', linewidth=2, linestyle='solid')
    ax.fill(angles, values, color='blue', alpha=0.4)

    plt.title("Hardware Fingerprint Visualization", size=20, color='blue', weight='bold')
    plt.show()
