// Lead Review Keyboard Shortcuts - Phase 7
class LeadReviewer {
    constructor() {
        this.leads = [];
        this.currentIndex = 0;
        this.selectedLeads = new Set();
        this.init();
    }

    init() {
        this.leads = document.querySelectorAll('.lead-card');
        if (this.leads.length === 0) return;

        this.bindKeyboardShortcuts();
        this.bindClickHandlers();
        this.highlightCurrent();
    }

    bindKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Don't trigger if typing in input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

            switch(e.key.toLowerCase()) {
                case 'j':
                    e.preventDefault();
                    this.nextLead();
                    break;
                case 'k':
                    e.preventDefault();
                    this.prevLead();
                    break;
                case 'a':
                    e.preventDefault();
                    this.setTier('A');
                    break;
                case 'b':
                    e.preventDefault();
                    this.setTier('B');
                    break;
                case 'c':
                    e.preventDefault();
                    this.setTier('C');
                    break;
                case 'u':
                    e.preventDefault();
                    this.setTier('U');
                    break;
                case 'r':
                    e.preventDefault();
                    this.markReviewed();
                    break;
                case 'x':
                    e.preventDefault();
                    this.toggleSelect();
                    break;
                case 'o':
                    e.preventDefault();
                    this.openWebsite();
                    break;
                case '?':
                    e.preventDefault();
                    this.showHelp();
                    break;
            }
        });
    }

    bindClickHandlers() {
        // Mark reviewed buttons
        document.querySelectorAll('.mark-reviewed-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const leadId = e.target.closest('.mark-reviewed-btn').dataset.leadId;
                this.saveReviewed(leadId);
            });
        });
    }

    highlightCurrent() {
        this.leads.forEach((lead, i) => {
            lead.classList.toggle('current', i === this.currentIndex);
        });
        this.leads[this.currentIndex]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    nextLead() {
        if (this.currentIndex < this.leads.length - 1) {
            this.currentIndex++;
            this.highlightCurrent();
        }
    }

    prevLead() {
        if (this.currentIndex > 0) {
            this.currentIndex--;
            this.highlightCurrent();
        }
    }

    getCurrentLead() {
        return this.leads[this.currentIndex];
    }

    getCurrentLeadId() {
        return this.getCurrentLead()?.dataset.leadId;
    }

    setTier(tier) {
        const leadId = this.getCurrentLeadId();
        if (!leadId) return;

        this.saveTierOverride(leadId, tier);

        // Update badge
        const badge = this.getCurrentLead().querySelector('.tier-badge');
        if (badge) {
            badge.textContent = `TIER ${tier}`;
            badge.className = `tier-badge tier-${tier.toLowerCase()}`;
        }

        // Update card border color
        const card = this.getCurrentLead();
        card.className = card.className.replace(/tier-[a-z]/g, '');
        card.classList.add(`tier-${tier.toLowerCase()}`);

        // Auto-advance to next lead
        setTimeout(() => this.nextLead(), 200);
    }

    async saveTierOverride(leadId, tier) {
        try {
            const response = await fetch(`/api/leads/${leadId}/tier-override`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tier })
            });

            if (!response.ok) throw new Error('Failed to save');

            this.showToast(`Tier set to ${tier}`);
        } catch (e) {
            this.showToast('Error saving tier', 'error');
        }
    }

    markReviewed() {
        const leadId = this.getCurrentLeadId();
        if (!leadId) return;
        this.saveReviewed(leadId);
    }

    async saveReviewed(leadId) {
        try {
            const response = await fetch(`/api/leads/${leadId}/reviewed`, {
                method: 'POST'
            });

            if (!response.ok) throw new Error('Failed to save');

            // Update button
            const btn = document.querySelector(`.mark-reviewed-btn[data-lead-id="${leadId}"]`);
            if (btn) {
                btn.classList.remove('btn-outline-success');
                btn.classList.add('btn-success');
                btn.innerHTML = '<i class="bi bi-check-circle-fill"></i> Reviewed';
            }

            this.showToast('Marked as reviewed');
        } catch (e) {
            this.showToast('Error saving', 'error');
        }
    }

    toggleSelect() {
        const leadId = this.getCurrentLeadId();
        if (!leadId) return;

        if (this.selectedLeads.has(leadId)) {
            this.selectedLeads.delete(leadId);
            this.getCurrentLead().classList.remove('selected');
        } else {
            this.selectedLeads.add(leadId);
            this.getCurrentLead().classList.add('selected');
        }

        this.updateSelectionCount();
    }

    updateSelectionCount() {
        const counter = document.getElementById('selection-count');
        if (counter) {
            counter.textContent = `${this.selectedLeads.size} selected`;
        }
    }

    openWebsite() {
        const lead = this.getCurrentLead();
        const link = lead?.querySelector('.contact-item a');
        if (link) window.open(link.href, '_blank');
    }

    showHelp() {
        const helpText = `Keyboard Shortcuts:

j/k - Next/Previous lead
a/b/c/u - Set tier A/B/C/U
r - Mark as reviewed
x - Toggle selection
o - Open website
? - Show this help`;

        alert(helpText);
    }

    showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 2000);
    }
}

// Initialize on page load (only if we're on a page with lead cards)
document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('.lead-card')) {
        window.leadReviewer = new LeadReviewer();
    }
});
