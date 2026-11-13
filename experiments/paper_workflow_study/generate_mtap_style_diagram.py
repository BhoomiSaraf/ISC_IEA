"""Generates an academic block diagram for the Enhanced ISC-IEA cryptosystem
in the EXACT style of Springer's 'Multimedia Tools and Applications' (Fig. 5 reference).
Pure black-and-white academic line drawing, clean serif typography, LaTeX math symbols,
tall vertical encryption round boxes with rotated labels, and orthogonal interconnects.
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

DIAG_DIR = "experiments/paper_workflow_study/plots"
os.makedirs(DIAG_DIR, exist_ok=True)


def generate_mtap_block_diagram():
    # Set up publication-grade serif fonts matching Springer Nature journals
    plt.rcParams["font.family"] = "serif"
    plt.rcParams["mathtext.fontset"] = "cm"  # Computer Modern math font
    plt.rcParams["font.serif"] = ["DejaVu Serif", "Times New Roman", "Computer Modern Roman", "serif"]

    # Wide aspect ratio exactly like Fig. 5 in Springer MTAP
    fig, ax = plt.subplots(figsize=(15.5, 6.2), dpi=300)
    ax.axis("off")
    ax.set_xlim(0, 20.2)
    ax.set_ylim(0, 8.2)

    # -------------------------------------------------------------------------
    # Springer Journal Running Header
    # -------------------------------------------------------------------------
    ax.text(19.4, 7.55, "Multimedia Tools and Applications",
            ha="right", va="bottom", fontsize=13, fontfamily="sans-serif", fontweight="normal", color="#000000")
    ax.plot([0.8, 19.4], [7.42, 7.42], color="#000000", lw=1.8)

    # Helper function to draw crisp rectangular boxes (Springer style)
    def draw_box(x, y, w, h, text_lines, fontsize=10, rotated=False, rot_angle=90):
        rect = patches.Rectangle((x, y), w, h, facecolor="#FFFFFF", edgecolor="#000000", linewidth=1.1, zorder=2)
        ax.add_patch(rect)
        if rotated:
            full_text = " ".join(text_lines)
            ax.text(x + w / 2, y + h / 2, full_text, ha="center", va="center",
                    fontsize=fontsize, fontweight="normal", color="#000000", rotation=rot_angle, zorder=3)
        else:
            total_lines = len(text_lines)
            if total_lines == 1:
                ax.text(x + w / 2, y + h / 2, text_lines[0], ha="center", va="center",
                        fontsize=fontsize, fontweight="normal", color="#000000", zorder=3)
            else:
                spacing = h / (total_lines + 1)
                for i, line in enumerate(text_lines):
                    line_y = y + h - (i + 1) * spacing
                    ax.text(x + w / 2, line_y, line, ha="center", va="center",
                            fontsize=fontsize, fontweight="normal", color="#000000", zorder=3)

    # Helper function for sharp black arrows
    def draw_arrow(x1, y1, x2, y2, lw=1.0):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color="#000000", lw=lw, mutation_scale=10),
                    zorder=3)

    # Helper function for solid black junction dots
    def draw_junction(x, y, radius=0.065):
        dot = patches.Circle((x, y), radius, facecolor="#000000", edgecolor="#000000", zorder=5)
        ax.add_patch(dot)

    # -------------------------------------------------------------------------
    # 1. KEY INGESTION & CHAOTIC INITIAL CONDITION DERIVATION
    # -------------------------------------------------------------------------
    # Input Arrow: 256 bit key & 128 bit nonce
    ax.text(1.75, 4.88, "256 bit key", ha="center", va="bottom", fontsize=10.5)
    ax.text(1.75, 4.52, "& 128 bit nonce", ha="center", va="top", fontsize=9.2)
    draw_arrow(0.8, 4.70, 2.7, 4.70)

    # Box 1: Generate initial conditions and parameters for the 2 2D-ISC maps
    draw_box(2.7, 3.60, 3.5, 2.20,
             ["Generate initial",
              "conditions and",
              "parameters for",
              "the 2 2D–ISC maps"],
             fontsize=9.8)

    # -------------------------------------------------------------------------
    # 2. UPPER & LOWER CHAOTIC MATRIX GENERATION BOXES
    # -------------------------------------------------------------------------
    # Upper Branch: Generate S_2 matrix (y = 5.20 to 6.20, center y = 5.70)
    draw_box(8.4, 5.20, 3.3, 1.00, [r"Generate $S_2$ matrix"], fontsize=10.5)

    # Lower Branch: Generate S_1 matrix (y = 3.50 to 4.50, center y = 4.00)
    draw_box(8.4, 3.50, 3.3, 1.00, [r"Generate $S_1$ matrix"], fontsize=10.5)

    # Upper Arrow: Box 1 -> S_2 box (at y = 5.70)
    draw_arrow(6.2, 5.70, 8.4, 5.70)
    ax.text(7.3, 5.88, r"$(x_{02}, y_{02})\ \mathrm{and}\ b_2$", ha="center", va="bottom", fontsize=10)

    # Lower Arrow: Box 1 -> S_1 box (at y = 4.00)
    draw_arrow(6.2, 4.00, 8.4, 4.00)
    ax.text(7.3, 4.18, r"$(x_{01}, y_{01})\ \mathrm{and}\ b_1$", ha="center", va="bottom", fontsize=10)

    # -------------------------------------------------------------------------
    # 3. PLAIN-IMAGE INGESTION & PREPROCESSING
    # -------------------------------------------------------------------------
    # Plain-image input arrow
    ax.text(1.85, 2.05, "Plain–image", ha="center", va="bottom", fontsize=10.5)
    ax.text(1.85, 1.62, r"$P$", ha="center", va="top", fontsize=11, fontstyle="italic")
    draw_arrow(0.8, 1.85, 3.0, 1.85)

    # Box: Plain image preprocessing & SIV coupling
    draw_box(3.0, 1.05, 3.2, 1.60,
             ["Plain image",
              "serialization and",
              "SIV hash binding"],
             fontsize=9.8)

    # SIV coupling arrow (HMAC-SHA256 from Plain image up to Initial Conditions)
    draw_arrow(4.6, 2.65, 4.6, 3.60)
    ax.text(4.8, 3.12, r"$\mathrm{HMAC}(P)$", ha="left", va="center", fontsize=8.5)

    # Arrow from Plain image box to Encryption round 1
    draw_arrow(6.2, 1.85, 12.8, 1.85)
    ax.text(9.5, 2.05, r"$P'$", ha="center", va="bottom", fontsize=11, fontstyle="italic")

    # -------------------------------------------------------------------------
    # 4. ENCRYPTION ROUND 1 (Tall vertical box)
    # y = 1.0 to 4.30, w = 1.25, h = 3.30 (top is at y = 4.30)
    # -------------------------------------------------------------------------
    draw_box(12.8, 1.00, 1.25, 3.30, ["Encryption round 1"], fontsize=10, rotated=True, rot_angle=90)

    # -------------------------------------------------------------------------
    # 5. S_1 and S_2 MATRIX CONNECTIONS (EXACT REPRODUCTION OF FIG. 5)
    # -------------------------------------------------------------------------
    # S_2 Output Line (at y = 5.70):
    # From S_2 box (x=11.7) horizontally to Encryption round 2 at x=16.7
    # Junction dot at x=13.425 (centered above Encryption round 1)
    # Arrow drops down from (13.425, 5.70) into top of Encryption round 1 at (13.425, 4.30)
    draw_arrow(11.7, 5.70, 16.7, 5.70)
    draw_junction(13.425, 5.70)
    draw_arrow(13.425, 5.70, 13.425, 4.30)
    ax.text(13.425, 5.92, r"$S_2$", ha="center", va="bottom", fontsize=11, fontstyle="italic")

    # S_1 Output Line (at y = 4.00):
    # Arrow out of S_1 box enters left side of Encryption round 1 at (12.8, 4.00)
    # Junction dot at x=12.15
    draw_arrow(11.7, 4.00, 12.8, 4.00)
    draw_junction(12.15, 4.00)
    ax.text(12.15, 3.65, r"$S_1$", ha="center", va="top", fontsize=11, fontstyle="italic")

    # From junction dot: line goes UP to y = 4.85 (above Encryption round 1),
    # then horizontal across to Encryption round 2 at x = 16.7
    ax.plot([12.15, 12.15, 16.7], [4.00, 4.85, 4.85], color="#000000", lw=1.0, zorder=2)
    draw_arrow(16.0, 4.85, 16.7, 4.85)

    # -------------------------------------------------------------------------
    # 6. DIFFUSION 2 (Intermediate vertical box)
    # -------------------------------------------------------------------------
    # From Encryption round 1 (x=14.05, y=2.60) to Diffusion 2 (x=14.65, y=2.60)
    draw_arrow(14.05, 2.60, 14.65, 2.60)
    # Box dimensions: x=14.65, y=1.50, w=1.05, h=2.20
    draw_box(14.65, 1.50, 1.05, 2.20, ["Diffusion 2"], fontsize=9.5, rotated=True, rot_angle=90)

    # -------------------------------------------------------------------------
    # 7. ENCRYPTION ROUND 2 (Tall vertical box)
    # -------------------------------------------------------------------------
    # Arrow from Diffusion 2 to Encryption round 2 at y = 2.60
    draw_arrow(15.70, 2.60, 16.7, 2.60)
    ax.text(16.20, 2.80, r"$C_1$", ha="center", va="bottom", fontsize=10.5, fontstyle="italic")

    # Box dimensions: x=16.7, y=1.40, w=1.25, h=4.70 (receives y=2.60, y=4.85, y=5.70)
    draw_box(16.7, 1.40, 1.25, 4.70, ["Encryption round 2"], fontsize=10, rotated=True, rot_angle=90)

    # -------------------------------------------------------------------------
    # 8. CIPHER-IMAGE OUTPUT
    # -------------------------------------------------------------------------
    # Arrow from Encryption round 2 (x=17.95, y=3.75) to (19.85, 3.75)
    draw_arrow(17.95, 3.75, 19.85, 3.75)
    ax.text(18.90, 4.00, "Cipher–image", ha="center", va="bottom", fontsize=10.5)
    ax.text(18.90, 3.50, r"$C_2$", ha="center", va="top", fontsize=11, fontstyle="italic")

    # -------------------------------------------------------------------------
    # 9. CAPTION (Springer style)
    # -------------------------------------------------------------------------
    ax.text(0.8, 0.45, r"$\mathbf{Fig.\ 5}$   Block diagram of the 2D-ISC based IEA",
            ha="left", va="center", fontsize=11, color="#000000")

    out_path = os.path.join(DIAG_DIR, "isc_iea_mtap_style_diagram.png")
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Generated MTAP style diagram: {out_path}")


if __name__ == "__main__":
    generate_mtap_block_diagram()
