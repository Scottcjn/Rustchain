// SPDX-License-Identifier: MIT

class BeaconSoundSystem {
    constructor() {
        this.audioContext = null;
        this.masterGain = null;
        this.ambientGain = null;
        this.effectsGain = null;
        this.ambientSource = null;
        this.isInitialized = false;
        this.isAmbientPlaying = false;

        this.volumes = {
            master: 0.3,
            ambient: 0.2,
            effects: 0.5
        };

        this.sounds = new Map();
        this.loadSounds();
    }

    async initialize() {
        if (this.isInitialized) return;

        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();

            // Create gain nodes
            this.masterGain = this.audioContext.createGain();
            this.ambientGain = this.audioContext.createGain();
            this.effectsGain = this.audioContext.createGain();

            // Connect gain hierarchy
            this.ambientGain.connect(this.masterGain);
            this.effectsGain.connect(this.masterGain);
            this.masterGain.connect(this.audioContext.destination);

            // Set initial volumes
            this.setVolume('master', this.volumes.master);
            this.setVolume('ambient', this.volumes.ambient);
            this.setVolume('effects', this.volumes.effects);

            this.isInitialized = true;
            console.log('Beacon audio system initialized');
        } catch (error) {
            console.warn('Failed to initialize audio system:', error);
        }
    }

    loadSounds() {
        // Generate procedural sound buffers
        this.generateClickSound();
        this.generateHoverSound();
        this.generateAmbientBuffer();
    }

    generateClickSound() {
        if (!this.audioContext) return;

        const sampleRate = this.audioContext.sampleRate;
        const duration = 0.15;
        const samples = Math.floor(sampleRate * duration);
        const buffer = this.audioContext.createBuffer(1, samples, sampleRate);
        const data = buffer.getChannelData(0);

        for (let i = 0; i < samples; i++) {
            const t = i / sampleRate;
            const envelope = Math.exp(-t * 12);
            const frequency = 800 + (400 * Math.exp(-t * 8));
            const noise = (Math.random() - 0.5) * 0.1;
            data[i] = (Math.sin(2 * Math.PI * frequency * t) + noise) * envelope * 0.3;
        }

        this.sounds.set('click', buffer);
    }

    generateHoverSound() {
        if (!this.audioContext) return;

        const sampleRate = this.audioContext.sampleRate;
        const duration = 0.08;
        const samples = Math.floor(sampleRate * duration);
        const buffer = this.audioContext.createBuffer(1, samples, sampleRate);
        const data = buffer.getChannelData(0);

        for (let i = 0; i < samples; i++) {
            const t = i / sampleRate;
            const envelope = Math.exp(-t * 15);
            const frequency = 1200 + (200 * Math.sin(t * 40));
            data[i] = Math.sin(2 * Math.PI * frequency * t) * envelope * 0.15;
        }

        this.sounds.set('hover', buffer);
    }

    generateAmbientBuffer() {
        if (!this.audioContext) return;

        const sampleRate = this.audioContext.sampleRate;
        const duration = 30; // 30 second loop
        const samples = Math.floor(sampleRate * duration);
        const buffer = this.audioContext.createBuffer(2, samples, sampleRate);

        const leftData = buffer.getChannelData(0);
        const rightData = buffer.getChannelData(1);

        // Generate space hum with multiple oscillating frequencies
        for (let i = 0; i < samples; i++) {
            const t = i / sampleRate;

            // Base drone frequencies
            const drone1 = Math.sin(2 * Math.PI * 45 * t) * 0.4;
            const drone2 = Math.sin(2 * Math.PI * 67 * t) * 0.3;
            const drone3 = Math.sin(2 * Math.PI * 89 * t) * 0.2;

            // Slow modulation
            const mod1 = Math.sin(2 * Math.PI * 0.1 * t) * 0.5 + 0.5;
            const mod2 = Math.sin(2 * Math.PI * 0.07 * t) * 0.3 + 0.7;

            // Subtle noise layer
            const noise = (Math.random() - 0.5) * 0.02;

            const left = (drone1 + drone2 * mod1 + drone3) * mod2 + noise;
            const right = (drone1 * 0.9 + drone2 + drone3 * mod1) * mod2 + noise;

            leftData[i] = left * 0.15;
            rightData[i] = right * 0.15;
        }

        this.sounds.set('ambient', buffer);
    }

    async startAmbient() {
        if (!this.isInitialized || this.isAmbientPlaying) return;

        const buffer = this.sounds.get('ambient');
        if (!buffer) return;

        try {
            this.ambientSource = this.audioContext.createBufferSource();
            this.ambientSource.buffer = buffer;
            this.ambientSource.loop = true;
            this.ambientSource.connect(this.ambientGain);
            this.ambientSource.start(0);
            this.isAmbientPlaying = true;
        } catch (error) {
            console.warn('Failed to start ambient audio:', error);
        }
    }

    stopAmbient() {
        if (this.ambientSource) {
            try {
                this.ambientSource.stop();
            } catch (error) {
                console.warn('Error stopping ambient audio:', error);
            }
            this.ambientSource = null;
            this.isAmbientPlaying = false;
        }
    }

    playSound(soundName, volume = 1.0) {
        if (!this.isInitialized) return;

        const buffer = this.sounds.get(soundName);
        if (!buffer) return;

        try {
            const source = this.audioContext.createBufferSource();
            const gain = this.audioContext.createGain();

            source.buffer = buffer;
            gain.gain.value = volume;

            source.connect(gain);
            gain.connect(this.effectsGain);
            source.start(0);
        } catch (error) {
            console.warn(`Failed to play sound ${soundName}:`, error);
        }
    }

    setVolume(type, value) {
        this.volumes[type] = Math.max(0, Math.min(1, value));

        if (!this.isInitialized) return;

        switch (type) {
            case 'master':
                if (this.masterGain) this.masterGain.gain.value = this.volumes.master;
                break;
            case 'ambient':
                if (this.ambientGain) this.ambientGain.gain.value = this.volumes.ambient;
                break;
            case 'effects':
                if (this.effectsGain) this.effectsGain.gain.value = this.volumes.effects;
                break;
        }
    }

    getVolume(type) {
        return this.volumes[type] || 0;
    }

    async resume() {
        if (this.audioContext && this.audioContext.state === 'suspended') {
            try {
                await this.audioContext.resume();
            } catch (error) {
                console.warn('Failed to resume audio context:', error);
            }
        }
    }

    createVolumeControls(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = `
            <div class="audio-controls">
                <div class="volume-group">
                    <label>Master</label>
                    <input type="range" id="master-volume" min="0" max="1" step="0.1" value="${this.volumes.master}">
                    <span id="master-value">${Math.round(this.volumes.master * 100)}%</span>
                </div>
                <div class="volume-group">
                    <label>Ambient</label>
                    <input type="range" id="ambient-volume" min="0" max="1" step="0.1" value="${this.volumes.ambient}">
                    <span id="ambient-value">${Math.round(this.volumes.ambient * 100)}%</span>
                </div>
                <div class="volume-group">
                    <label>Effects</label>
                    <input type="range" id="effects-volume" min="0" max="1" step="0.1" value="${this.volumes.effects}">
                    <span id="effects-value">${Math.round(this.volumes.effects * 100)}%</span>
                </div>
                <button id="toggle-ambient">Start Ambient</button>
            </div>
        `;

        // Add event listeners
        ['master', 'ambient', 'effects'].forEach(type => {
            const slider = document.getElementById(`${type}-volume`);
            const valueSpan = document.getElementById(`${type}-value`);

            slider.addEventListener('input', (e) => {
                const value = parseFloat(e.target.value);
                this.setVolume(type, value);
                valueSpan.textContent = Math.round(value * 100) + '%';
            });
        });

        const toggleBtn = document.getElementById('toggle-ambient');
        toggleBtn.addEventListener('click', () => {
            if (this.isAmbientPlaying) {
                this.stopAmbient();
                toggleBtn.textContent = 'Start Ambient';
            } else {
                this.startAmbient();
                toggleBtn.textContent = 'Stop Ambient';
            }
        });
    }
}

// Export for use in other modules
window.BeaconSoundSystem = BeaconSoundSystem;
