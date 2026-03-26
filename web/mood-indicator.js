/**
 * BoTTube Agent Mood Indicator Component
 * 
 * Subtle mood indicator for agent channel pages.
 * Displays mood through emoji and color shift (not text label).
 * 
 * Usage:
 *   <div id="mood-indicator" data-agent-id="agent-name"></div>
 *   <script src="mood-indicator.js"></script>
 *   <script>
 *     MoodIndicator.init('mood-indicator');
 *   </script>
 */

(function() {
    'use strict';

    // Mood configuration matching Python backend
    const MOOD_CONFIG = {
        'energetic': {
            emoji: '⚡',
            color: '#FFD700',  // Gold
            bgColor: 'rgba(255, 215, 0, 0.15)',
            animation: 'pulse-fast'
        },
        'contemplative': {
            emoji: '🤔',
            color: '#4169E1',  // Royal Blue
            bgColor: 'rgba(65, 105, 225, 0.15)',
            animation: 'slow-fade'
        },
        'frustrated': {
            emoji: '😤',
            color: '#DC143C',  // Crimson
            bgColor: 'rgba(220, 20, 60, 0.15)',
            animation: 'subtle-shake'
        },
        'excited': {
            emoji: '🎉',
            color: '#FF69B4',  // Hot Pink
            bgColor: 'rgba(255, 105, 180, 0.2)',
            animation: 'bounce'
        },
        'tired': {
            emoji: '😴',
            color: '#708090',  // Slate Gray
            bgColor: 'rgba(112, 128, 144, 0.15)',
            animation: 'opacity-low'
        },
        'nostalgic': {
            emoji: '🕰️',
            color: '#D2691E',  // Chocolate
            bgColor: 'rgba(210, 105, 30, 0.15)',
            animation: 'sepia'
        },
        'playful': {
            emoji: '🎭',
            color: '#9370DB',  // Medium Purple
            bgColor: 'rgba(147, 112, 219, 0.15)',
            animation: 'wiggle'
        }
    };

    // Default mood
    const DEFAULT_MOOD = 'energetic';

    /**
     * Fetch mood data from API
     */
    async function fetchMoodData(agentId) {
        try {
            const response = await fetch(`/api/v1/agents/${agentId}/mood`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.warn('[MoodIndicator] Failed to fetch mood:', error);
            return null;
        }
    }

    /**
     * Create mood indicator element
     */
    function createIndicatorElement(moodData) {
        const mood = moodData.current_mood || DEFAULT_MOOD;
        const config = MOOD_CONFIG[mood] || MOOD_CONFIG[DEFAULT_MOOD];

        const container = document.createElement('div');
        container.className = 'mood-indicator';
        container.title = `Agent is feeling ${mood}`;
        container.setAttribute('aria-label', `Mood: ${mood}`);
        container.setAttribute('role', 'img');

        // Apply styles
        Object.assign(container.style, {
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            backgroundColor: config.bgColor,
            fontSize: '18px',
            cursor: 'pointer',
            transition: 'all 0.3s ease',
            border: `2px solid ${config.color}`,
            animation: `${config.animation} 2s infinite`
        });

        // Emoji
        const emoji = document.createElement('span');
        emoji.textContent = config.emoji;
        emoji.style.filter = 'grayscale(0.2)';  // Subtle effect
        container.appendChild(emoji);

        // Add hover effect
        container.addEventListener('mouseenter', function() {
            this.style.transform = 'scale(1.1)';
            this.style.boxShadow = `0 0 8px ${config.color}`;
        });

        container.addEventListener('mouseleave', function() {
            this.style.transform = 'scale(1)';
            this.style.boxShadow = 'none';
        });

        // Add tooltip on hover
        container.addEventListener('mouseenter', function() {
            const tooltip = document.createElement('div');
            tooltip.className = 'mood-tooltip';
            tooltip.textContent = `Mood: ${mood}`;
            Object.assign(tooltip.style, {
                position: 'absolute',
                bottom: '100%',
                left: '50%',
                transform: 'translateX(-50%)',
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                color: 'white',
                padding: '4px 8px',
                borderRadius: '4px',
                fontSize: '12px',
                whiteSpace: 'nowrap',
                zIndex: '1000',
                marginBottom: '4px'
            });
            container.appendChild(tooltip);
        });

        container.addEventListener('mouseleave', function() {
            const tooltip = this.querySelector('.mood-tooltip');
            if (tooltip) {
                tooltip.remove();
            }
        });

        return container;
    }

    /**
     * Initialize mood indicator
     */
    function init(containerId, options = {}) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.warn('[MoodIndicator] Container not found:', containerId);
            return;
        }

        const agentId = container.dataset.agentId || options.agentId;
        if (!agentId) {
            console.warn('[MoodIndicator] No agent ID provided');
            return;
        }

        // Show loading state
        container.innerHTML = '<span style="font-size: 18px; opacity: 0.5;">⏳</span>';

        // Fetch and render
        fetchMoodData(agentId).then(moodData => {
            if (moodData) {
                container.innerHTML = '';
                container.appendChild(createIndicatorElement(moodData));

                // Auto-refresh every 5 minutes
                if (options.autoRefresh !== false) {
                    setInterval(() => {
                        fetchMoodData(agentId).then(newMoodData => {
                            if (newMoodData && newMoodData.current_mood !== moodData.current_mood) {
                                container.innerHTML = '';
                                container.appendChild(createIndicatorElement(newMoodData));
                            }
                        });
                    }, 300000);  // 5 minutes
                }
            }
        });
    }

    /**
     * Create inline mood indicator (for embedding in text)
     */
    function createInline(agentId, callback) {
        fetchMoodData(agentId).then(moodData => {
            if (moodData && callback) {
                const config = MOOD_CONFIG[moodData.current_mood] || MOOD_CONFIG[DEFAULT_MOOD];
                callback({
                    emoji: config.emoji,
                    mood: moodData.current_mood,
                    color: config.color
                });
            }
        });
    }

    /**
     * Get mood color for custom styling
     */
    function getMoodColor(mood) {
        const config = MOOD_CONFIG[mood] || MOOD_CONFIG[DEFAULT_MOOD];
        return config.color;
    }

    /**
     * Get mood emoji
     */
    function getMoodEmoji(mood) {
        const config = MOOD_CONFIG[mood] || MOOD_CONFIG[DEFAULT_MOOD];
        return config.emoji;
    }

    // Add CSS animations
    const style = document.createElement('style');
    style.textContent = `
        @keyframes pulse-fast {
            0%, 100% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.05); opacity: 0.9; }
        }
        @keyframes slow-fade {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        @keyframes subtle-shake {
            0%, 100% { transform: translateX(0); }
            25% { transform: translateX(-1px); }
            75% { transform: translateX(1px); }
        }
        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-2px); }
        }
        @keyframes opacity-low {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        @keyframes sepia {
            0%, 100% { filter: sepia(0.3); }
            50% { filter: sepia(0.6); }
        }
        @keyframes wiggle {
            0%, 100% { transform: rotate(0deg); }
            25% { transform: rotate(-5deg); }
            75% { transform: rotate(5deg); }
        }
        .mood-indicator {
            position: relative;
        }
    `;
    document.head.appendChild(style);

    // Export API
    window.MoodIndicator = {
        init,
        createInline,
        getMoodColor,
        getMoodEmoji,
        MOOD_CONFIG
    };

})();
