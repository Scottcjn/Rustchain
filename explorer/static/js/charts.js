/**
 * RustChain Explorer - Real-time Charts
 * Lightweight chart rendering without external dependencies
 */

class ChartRenderer {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`[Chart] Container #${containerId} not found`);
            return;
        }

        this.options = {
            width: options.width || this.container.clientWidth || 400,
            height: options.height || options.height || 200,
            type: options.type || 'line',
            colors: options.colors || ['#8b5cf6', '#6366f1', '#3b82f6', '#10b981'],
            showLegend: options.showLegend !== false,
            showGrid: options.showGrid !== false,
            showTooltips: options.showTooltips !== false,
            animation: options.animation !== false,
            ...options
        };

        this.data = [];
        this.canvas = null;
        this.ctx = null;
        this.animationFrame = null;
        this.targetData = [];
        
        this.init();
    }

    init() {
        // Create canvas
        this.canvas = document.createElement('canvas');
        this.canvas.width = this.options.width;
        this.canvas.height = this.options.height;
        this.canvas.style.width = '100%';
        this.canvas.style.height = 'auto';
        this.container.innerHTML = '';
        this.container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');

        // Handle resize
        this.setupResizeObserver();
    }

    setupResizeObserver() {
        if (typeof ResizeObserver === 'undefined') return;

        const observer = new ResizeObserver(entries => {
            for (let entry of entries) {
                const { width, height } = entry.contentRect;
                if (width > 0 && height > 0) {
                    this.options.width = width;
                    this.options.height = height || this.options.height;
                    this.canvas.width = width;
                    this.canvas.height = height || this.options.height;
                    this.render();
                }
            }
        });

        observer.observe(this.container);
    }

    /**
     * Update chart data
     */
    update(newData) {
        this.targetData = newData;
        
        if (this.options.animation) {
            this.animate();
        } else {
            this.data = newData;
            this.render();
        }
    }

    /**
     * Animate data transition
     */
    animate() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }

        const duration = 300;
        const startTime = performance.now();
        const startData = this.data.length > 0 ? this.data : this.targetData;

        const animateFrame = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Ease out cubic
            const eased = 1 - Math.pow(1 - progress, 3);

            // Interpolate data
            if (startData.length === this.targetData.length) {
                this.data = startData.map((val, i) => {
                    const target = this.targetData[i];
                    if (typeof val === 'number' && typeof target === 'number') {
                        return val + (target - val) * eased;
                    }
                    return target;
                });
            } else {
                this.data = this.targetData;
            }

            this.render();

            if (progress < 1) {
                this.animationFrame = requestAnimationFrame(animateFrame);
            }
        };

        this.animationFrame = requestAnimationFrame(animateFrame);
    }

    /**
     * Render the chart
     */
    render() {
        if (!this.ctx) return;

        const { width, height, type } = this.options;
        
        // Clear canvas
        this.ctx.clearRect(0, 0, width, height);

        // Draw background
        this.drawBackground();

        // Draw grid
        if (this.options.showGrid) {
            this.drawGrid();
        }

        // Draw chart based on type
        switch (type) {
            case 'line':
                this.drawLineChart();
                break;
            case 'bar':
                this.drawBarChart();
                break;
            case 'pie':
                this.drawPieChart();
                break;
            case 'doughnut':
                this.drawDoughnutChart();
                break;
            case 'area':
                this.drawAreaChart();
                break;
            default:
                this.drawLineChart();
        }

        // Draw legend
        if (this.options.showLegend) {
            this.drawLegend();
        }
    }

    drawBackground() {
        const { width, height } = this.options;
        const gradient = this.ctx.createLinearGradient(0, 0, 0, height);
        gradient.addColorStop(0, 'rgba(36, 43, 61, 0.5)');
        gradient.addColorStop(1, 'rgba(36, 43, 61, 0.1)');
        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(0, 0, width, height);
    }

    drawGrid() {
        const { width, height } = this.options;
        const padding = this.getPadding();
        
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
        this.ctx.lineWidth = 1;

        // Horizontal grid lines
        const gridHeight = height - padding.top - padding.bottom;
        for (let i = 0; i <= 5; i++) {
            const y = padding.top + (gridHeight / 5) * i;
            this.ctx.beginPath();
            this.ctx.moveTo(padding.left, y);
            this.ctx.lineTo(width - padding.right, y);
            this.ctx.stroke();
        }

        // Vertical grid lines
        const gridWidth = width - padding.left - padding.right;
        if (this.data.length > 1) {
            for (let i = 0; i < this.data.length; i++) {
                const x = padding.left + (gridWidth / (this.data.length - 1)) * i;
                this.ctx.beginPath();
                this.ctx.moveTo(x, padding.top);
                this.ctx.lineTo(x, height - padding.bottom);
                this.ctx.stroke();
            }
        }
    }

    getPadding() {
        return {
            top: this.options.showLegend ? 40 : 20,
            right: 20,
            bottom: 30,
            left: 50
        };
    }

    drawLineChart() {
        const { width, height, colors } = this.options;
        const padding = this.getPadding();
        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;

        if (this.data.length < 2) return;

        const maxValue = Math.max(...this.data.map(d => typeof d === 'number' ? d : 0));
        const minValue = Math.min(...this.data.map(d => typeof d === 'number' ? d : 0));
        const range = maxValue - minValue || 1;

        // Draw line
        this.ctx.beginPath();
        this.ctx.strokeStyle = colors[0];
        this.ctx.lineWidth = 2;
        this.ctx.lineJoin = 'round';

        this.data.forEach((value, index) => {
            const x = padding.left + (chartWidth / (this.data.length - 1)) * index;
            const y = padding.top + chartHeight - ((value - minValue) / range) * chartHeight;
            
            if (index === 0) {
                this.ctx.moveTo(x, y);
            } else {
                this.ctx.lineTo(x, y);
            }
        });

        this.ctx.stroke();

        // Draw points
        this.data.forEach((value, index) => {
            const x = padding.left + (chartWidth / (this.data.length - 1)) * index;
            const y = padding.top + chartHeight - ((value - minValue) / range) * chartHeight;
            
            this.ctx.beginPath();
            this.ctx.fillStyle = colors[0];
            this.ctx.arc(x, y, 4, 0, Math.PI * 2);
            this.ctx.fill();
        });

        // Draw axis labels
        this.ctx.fillStyle = '#9aa0a6';
        this.ctx.font = '10px sans-serif';
        this.ctx.textAlign = 'right';
        this.ctx.fillText(maxValue.toFixed(2), padding.left - 5, padding.top);
        this.ctx.fillText(minValue.toFixed(2), padding.left - 5, height - padding.bottom);
    }

    drawAreaChart() {
        const { width, height, colors } = this.options;
        const padding = this.getPadding();
        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;

        if (this.data.length < 2) return;

        const maxValue = Math.max(...this.data.map(d => typeof d === 'number' ? d : 0));
        const minValue = Math.min(...this.data.map(d => typeof d === 'number' ? d : 0));
        const range = maxValue - minValue || 1;

        // Draw filled area
        this.ctx.beginPath();
        const gradient = this.ctx.createLinearGradient(0, padding.top, 0, height - padding.bottom);
        gradient.addColorStop(0, colors[0] + '60');
        gradient.addColorStop(1, colors[0] + '10');

        this.data.forEach((value, index) => {
            const x = padding.left + (chartWidth / (this.data.length - 1)) * index;
            const y = padding.top + chartHeight - ((value - minValue) / range) * chartHeight;
            
            if (index === 0) {
                this.ctx.moveTo(x, y);
            } else {
                this.ctx.lineTo(x, y);
            }
        });

        // Close the path
        const lastX = padding.left + chartWidth;
        const baselineY = height - padding.bottom;
        this.ctx.lineTo(lastX, baselineY);
        this.ctx.lineTo(padding.left, baselineY);
        this.ctx.closePath();
        this.ctx.fillStyle = gradient;
        this.ctx.fill();

        // Draw line on top
        this.drawLineChart();
    }

    drawBarChart() {
        const { width, height, colors } = this.options;
        const padding = this.getPadding();
        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;

        if (this.data.length === 0) return;

        const maxValue = Math.max(...this.data.map(d => typeof d === 'number' ? d : 0));
        const barWidth = (chartWidth / this.data.length) * 0.8;
        const barGap = (chartWidth / this.data.length) * 0.2;

        this.data.forEach((value, index) => {
            const x = padding.left + (chartWidth / this.data.length) * index + barGap / 2;
            const barHeight = maxValue > 0 ? (value / maxValue) * chartHeight : 0;
            const y = padding.top + chartHeight - barHeight;

            // Draw bar
            const gradient = this.ctx.createLinearGradient(x, y, x, y + barHeight);
            gradient.addColorStop(0, colors[index % colors.length]);
            gradient.addColorStop(1, colors[index % colors.length] + '60');
            
            this.ctx.fillStyle = gradient;
            this.ctx.fillRect(x, y, barWidth, barHeight);

            // Draw value label
            this.ctx.fillStyle = '#e8eaed';
            this.ctx.font = '10px sans-serif';
            this.ctx.textAlign = 'center';
            this.ctx.fillText(value.toFixed(1), x + barWidth / 2, y - 5);
        });
    }

    drawPieChart() {
        const { width, height, colors } = this.options;
        const centerX = width / 2;
        const centerY = height / 2;
        const radius = Math.min(width, height) / 2 - 40;

        if (this.data.length === 0) return;

        const total = this.data.reduce((sum, item) => sum + (item.value || 0), 0);
        let startAngle = -Math.PI / 2;

        this.data.forEach((item, index) => {
            const value = item.value || 0;
            const sliceAngle = (value / total) * Math.PI * 2;

            this.ctx.beginPath();
            this.ctx.moveTo(centerX, centerY);
            this.ctx.arc(centerX, centerY, radius, startAngle, startAngle + sliceAngle);
            this.ctx.closePath();
            this.ctx.fillStyle = colors[index % colors.length];
            this.ctx.fill();

            // Draw label
            const labelAngle = startAngle + sliceAngle / 2;
            const labelX = centerX + Math.cos(labelAngle) * (radius * 0.7);
            const labelY = centerY + Math.sin(labelAngle) * (radius * 0.7);
            
            this.ctx.fillStyle = '#fff';
            this.ctx.font = '12px sans-serif';
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'middle';
            this.ctx.fillText(item.label || '', labelX, labelY);

            startAngle += sliceAngle;
        });
    }

    drawDoughnutChart() {
        const { width, height, colors } = this.options;
        const centerX = width / 2;
        const centerY = height / 2;
        const outerRadius = Math.min(width, height) / 2 - 20;
        const innerRadius = outerRadius * 0.6;

        if (this.data.length === 0) return;

        const total = this.data.reduce((sum, item) => sum + (item.value || 0), 0);
        let startAngle = -Math.PI / 2;

        this.data.forEach((item, index) => {
            const value = item.value || 0;
            const sliceAngle = (value / total) * Math.PI * 2;

            // Draw doughnut slice
            this.ctx.beginPath();
            this.ctx.arc(centerX, centerY, outerRadius, startAngle, startAngle + sliceAngle);
            this.ctx.arc(centerX, centerY, innerRadius, startAngle + sliceAngle, startAngle, true);
            this.ctx.closePath();
            this.ctx.fillStyle = colors[index % colors.length];
            this.ctx.fill();

            startAngle += sliceAngle;
        });

        // Draw center text
        this.ctx.fillStyle = '#e8eaed';
        this.ctx.font = 'bold 16px sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText('Total', centerX, centerY - 10);
        this.ctx.font = 'bold 20px sans-serif';
        this.ctx.fillText(total.toFixed(0), centerX, centerY + 15);
    }

    drawLegend() {
        const { colors } = this.options;
        const padding = 10;
        const itemHeight = 20;
        const itemWidth = 100;

        if (!this.data.length || !this.data[0].label) return;

        this.ctx.font = '12px sans-serif';
        
        this.data.forEach((item, index) => {
            const x = padding;
            const y = padding + index * (itemHeight + 5);
            
            // Draw color box
            this.ctx.fillStyle = colors[index % colors.length];
            this.ctx.fillRect(x, y, 12, 12);
            
            // Draw label
            this.ctx.fillStyle = '#e8eaed';
            this.ctx.textAlign = 'left';
            this.ctx.textBaseline = 'middle';
            this.ctx.fillText(item.label || '', x + 18, y + 6);
        });
    }

    /**
     * Clear the chart
     */
    clear() {
        if (this.ctx) {
            this.ctx.clearRect(0, 0, this.options.width, this.options.height);
        }
    }

    /**
     * Destroy the chart
     */
    destroy() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }
        if (this.container && this.canvas) {
            this.container.removeChild(this.canvas);
        }
    }
}

// Export for use in other modules
window.ChartRenderer = ChartRenderer;
