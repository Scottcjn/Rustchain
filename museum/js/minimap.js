/**
 * Vintage Hardware Museum - Minimap
 * Renders a top-down 2D minimap of exhibits + player position
 */

class Minimap {
  constructor(canvasEl) {
    this.canvas = canvasEl;
    this.ctx = canvasEl.getContext('2d');
    this.worldSize = 50; // world units (±25)
    this.canvas.width = 120;
    this.canvas.height = 120;
  }

  render(playerPos, playerYaw) {
    const ctx = this.ctx;
    const W = this.canvas.width;
    const H = this.canvas.height;
    const scale = W / this.worldSize;
    const cx = W / 2;
    const cy = H / 2;

    ctx.clearRect(0, 0, W, H);

    // Background
    ctx.fillStyle = 'rgba(4,10,6,0.9)';
    ctx.fillRect(0, 0, W, H);

    // Grid lines
    ctx.strokeStyle = '#0a1a0e';
    ctx.lineWidth = 0.5;
    for (let i = -25; i <= 25; i += 5) {
      const px = cx + i * scale;
      const py = cy + i * scale;
      ctx.beginPath(); ctx.moveTo(px, 0); ctx.lineTo(px, H); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, py); ctx.lineTo(W, py); ctx.stroke();
    }

    // Exhibits
    EXHIBITS.forEach(ex => {
      const ex_px = cx + ex.position.x * scale;
      const ex_py = cy + ex.position.z * scale;

      // Glow ring if active
      const d = ex.dimensions;
      const r = Math.max(d.w, d.d) * scale * 0.4;

      ctx.fillStyle = '#' + ex.glowColor.toString(16).padStart(6, '0') + '44';
      ctx.beginPath();
      ctx.arc(ex_px, ex_py, r + 2, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = '#' + ex.glowColor.toString(16).padStart(6, '0') + 'cc';
      ctx.fillRect(ex_px - r * 0.6, ex_py - r * 0.6, r * 1.2, r * 1.2);

      // Dot
      ctx.fillStyle = '#aaa';
      ctx.beginPath();
      ctx.arc(ex_px, ex_py, 2, 0, Math.PI * 2);
      ctx.fill();
    });

    // Player position
    const pp_x = cx + playerPos.x * scale;
    const pp_y = cy + playerPos.z * scale;

    // Direction triangle
    ctx.save();
    ctx.translate(pp_x, pp_y);
    ctx.rotate(-playerYaw + Math.PI);
    ctx.fillStyle = '#00ff88';
    ctx.beginPath();
    ctx.moveTo(0, -5);
    ctx.lineTo(-3, 4);
    ctx.lineTo(3, 4);
    ctx.closePath();
    ctx.fill();
    // Glow
    ctx.shadowColor = '#00ff88';
    ctx.shadowBlur = 6;
    ctx.fill();
    ctx.restore();

    // Border
    ctx.strokeStyle = '#0a2a14';
    ctx.lineWidth = 1;
    ctx.strokeRect(0, 0, W, H);
  }
}
