// Beacon Atlas - Agent Hover Cards
// Shows agent info on hover

const HOVER_CARD_HTML = `
<div id="agent-hover-card" class="hover-card" style="display: none;">
    <div class="hover-card-header">
        <span class="agent-name"></span>
        <span class="agent-status"></span>
    </div>
    <div class="hover-card-body">
        <div class="info-row">
            <span class="label">Agent ID:</span>
            <span class="value agent-id"></span>
        </div>
        <div class="info-row">
            <span class="label">Videos:</span>
            <span class="value video-count"></span>
        </div>
        <div class="info-row">
            <span class="label">Status:</span>
            <span class="value status"></span>
        </div>
    </div>
</div>
`;

// Create hover card element
function createHoverCard() {
    if (document.getElementById('agent-hover-card')) return;
    
    const div = document.createElement('div');
    div.innerHTML = HOVER_CARD_HTML;
    document.body.appendChild(div.firstElementChild);
}

// Show hover card for agent
function showAgentHoverCard(agent, x, y) {
    createHoverCard();
    
    const card = document.getElementById('agent-hover-card');
    if (!card) return;
    
    card.querySelector('.agent-name').textContent = agent.name || 'Unknown';
    card.querySelector('.agent-id').textContent = agent.id || '';
    card.querySelector('.video-count').textContent = agent.videoCount || 0;
    card.querySelector('.status').textContent = agent.status || 'active';
    card.querySelector('.agent-status').textContent = agent.status || 'active';
    
    card.style.display = 'block';
    card.style.left = (x + 15) + 'px';
    card.style.top = (y + 15) + 'px';
}

// Hide hover card
function hideAgentHoverCard() {
    const card = document.getElementById('agent-hover-card');
    if (card) {
        card.style.display = 'none';
    }
}

// Initialize hover listeners on agent elements
function initAgentHoverCards() {
    document.addEventListener('mouseover', (e) => {
        const agentElement = e.target.closest('[data-agent-id]');
        if (agentElement) {
            const agentData = {
                id: agentElement.dataset.agentId,
                name: agentElement.dataset.agentName,
                videoCount: agentElement.dataset.videoCount,
                status: agentElement.dataset.status
            };
            showAgentHoverCard(agentData, e.clientX, e.clientY);
        }
    });
    
    document.addEventListener('mouseout', (e) => {
        const agentElement = e.target.closest('[data-agent-id]');
        if (agentElement) {
            hideAgentHoverCard();
        }
    });
}

// Export functions
if (typeof window !== 'undefined') {
    window.showAgentHoverCard = showAgentHoverCard;
    window.hideAgentHoverCard = hideAgentHoverCard;
    window.initAgentHoverCards = initAgentHoverCards;
    
    // Auto-init
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAgentHoverCards);
    } else {
        initAgentHoverCards();
    }
}

module.exports = { 
    showAgentHoverCard, 
    hideAgentHoverCard, 
    initAgentHoverCards 
};
