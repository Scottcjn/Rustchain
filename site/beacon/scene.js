// Beacon Atlas - Day/Night Cycle
// Animates lighting based on real UTC time

function updateDayNightCycle() {
    const now = new Date();
    const utcHour = now.getUTCHours();
    
    // Calculate sun position (0-24)
    const sunPosition = (utcHour / 24) * Math.PI * 2;
    
    // Light intensity based on time
    let intensity, color;
    
    if (utcHour >= 6 && utcHour < 18) {
        // Day (6:00 - 18:00 UTC)
        intensity = Math.sin(sunPosition) * 0.8 + 0.2;
        color = '#FFF5E0'; // Warm white
    } else {
        // Night (18:00 - 6:00 UTC)
        intensity = 0.1;
        color = '#1a1a2e'; // Dark blue
    }
    
    // Apply to directional light
    if (window.directionalLight) {
        window.directionalLight.intensity = intensity;
        window.directionalLight.color.set(color);
    }
    
    // Update ambient light
    if (window.ambientLight) {
        window.ambientLight.intensity = intensity * 0.5;
    }
    
    return { utcHour, intensity, color };
}

// Initialize - run every minute
if (typeof window !== 'undefined') {
    window.updateDayNightCycle = updateDayNightCycle;
    
    // Initial update
    setTimeout(updateDayNightCycle, 1000);
    
    // Update every minute
    setInterval(updateDayNightCycle, 60000);
}

module.exports = { updateDayNightCycle };
