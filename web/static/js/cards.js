import { gameState } from "./state.js";
import { addLog } from "./ui.js";

const SYMBOLS = {
    'INFANTRY': '🪖',
    'CAVALRY': '🐎',
    'ARTILLERY': '💣',
    'JOLLY': '🌟'
};

export const CardStore = {
    hand: [],
    selectedIndices: [],
    preview: {
        valid: false,
        bonus_armies: 0,
        territory_bonuses: {}
    },
    isOpen: false,

    reset() {
        this.selectedIndices = [];
        this.preview = { valid: false, bonus_armies: 0, territory_bonuses: {} };
    }
};

export async function fetchCards() {
    try {
        const pId = gameState.localHumanId || 1;
        const resp = await fetch(`/player/cards?player_id=${pId}`);
        const data = await resp.json();
        CardStore.hand = data.cards || [];
        renderCards();
    } catch (e) {
        console.error("Error fetching cards:", e);
    }
}

export async function validateSelection() {
    if (CardStore.selectedIndices.length !== 3) {
        CardStore.preview = { valid: false, bonus_armies: 0, territory_bonuses: {} };
        renderPreview();
        return;
    }

    try {
        const pId = gameState.localHumanId || 1;
        const resp = await fetch('/cards/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ indices: CardStore.selectedIndices, player_id: pId })
        });
        const data = await resp.json();
        CardStore.preview = data;
        renderPreview();
    } catch (e) {
        console.error("Error validating cards:", e);
    }
}

export async function tradeCards() {
    if (!CardStore.preview.valid) return;

    try {
        const pId = gameState.localHumanId || 1;
        const resp = await fetch('/cards/trade', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ indices: CardStore.selectedIndices, player_id: pId })
        });
        const data = await resp.json();
        
        if (data.success) {
            addLog(`[CARTE] Scambio completato! +${data.bonus_armies} armate`, "log-success");
            CardStore.reset();
            await fetchCards();
            // State update is handled by the server broadcast triggered by /cards/trade
        } else {
            addLog(`[ERRORE] ${data.error}`, "log-error");
        }
    } catch (e) {
        console.error("Error trading cards:", e);
    }
}

export function toggleCardPanel(forceState) {
    const panel = document.getElementById('card-panel');
    if (!panel) return;

    CardStore.isOpen = (forceState !== undefined) ? forceState : !CardStore.isOpen;
    
    if (CardStore.isOpen) {
        panel.classList.remove('hidden');
        fetchCards();
    } else {
        panel.classList.add('hidden');
    }
}

export function renderCards() {
    const container = document.getElementById('cards-container');
    if (!container) return;

    container.innerHTML = '';
    
    CardStore.hand.forEach((card, index) => {
        const isSelected = CardStore.selectedIndices.includes(index);
        
        const cardEl = document.createElement('div');
        cardEl.className = `card-item ${card.is_jolly ? 'jolly' : ''} ${isSelected ? 'selected' : ''}`;
        
        let badges = '';
        if (card.owns_territory) {
            badges = `<div class="card-ownership-badge">+2</div>`;
        }

        cardEl.innerHTML = `
            ${badges}
            <div class="card-symbol">${SYMBOLS[card.symbol] || '❓'}</div>
            <div class="card-territory">${card.territory_name || 'JOLLY'}</div>
        `;

        cardEl.onclick = () => {
            if (isSelected) {
                CardStore.selectedIndices = CardStore.selectedIndices.filter(i => i !== index);
            } else {
                if (CardStore.selectedIndices.length < 3) {
                    CardStore.selectedIndices.push(index);
                }
            }
            renderCards();
            validateSelection();
        };

        container.appendChild(cardEl);
    });
}

function renderPreview() {
    const previewEl = document.getElementById('card-combo-preview');
    const tradeBtn = document.getElementById('btn-trade-cards');
    if (!previewEl || !tradeBtn) return;

    if (CardStore.preview.valid) {
        const tCount = Object.keys(CardStore.preview.territory_bonuses).length;
        previewEl.innerHTML = `
            <div class="preview-info">
                <div class="preview-bonus">BONUS: +${CardStore.preview.bonus_armies} ARMATE</div>
                ${tCount > 0 ? `<div class="preview-territories">+${tCount * 2} Bonus Territori</div>` : ''}
            </div>
        `;
        tradeBtn.disabled = false;
    } else {
        previewEl.innerHTML = `<div style="color: rgba(255,255,255,0.3); font-size: 0.8rem;">Seleziona 3 carte per una combinazione</div>`;
        tradeBtn.disabled = true;
    }
}

// Initial setup
document.addEventListener('DOMContentLoaded', () => {
    const tradeBtn = document.getElementById('btn-trade-cards');
    if (tradeBtn) {
        tradeBtn.onclick = tradeCards;
    }
});
