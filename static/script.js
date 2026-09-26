document.addEventListener('DOMContentLoaded', () => {
    const contractInput = document.getElementById('contract-input');
    const charCount = document.getElementById('char-count');
    const clearBtn = document.getElementById('clear-btn');
    const analyzeBtn = document.getElementById('analyze-btn');
    const btnText = analyzeBtn.querySelector('.btn-text');
    const btnLoader = analyzeBtn.querySelector('.btn-loader');

    const sampleTosBtn = document.getElementById('sample-tos-btn');
    const sampleNdaBtn = document.getElementById('sample-nda-btn');

    const errorBanner = document.getElementById('error-banner');
    const errorMessage = document.getElementById('error-message');
    const closeErrorBtn = document.getElementById('close-error-btn');

    const loadingState = document.getElementById('loading-state');
    const resultsSection = document.getElementById('results-section');

    const overallScoreNum = document.getElementById('overall-score-num');
    const scoreTierLabel = document.getElementById('score-tier-label');
    const scoreBadgeCircle = document.getElementById('score-badge-circle');
    const scoreSummaryText = document.getElementById('score-summary-text');

    const countHigh = document.getElementById('count-high');
    const countMedium = document.getElementById('count-medium');
    const countLow = document.getElementById('count-low');
    const totalClausesCount = document.getElementById('total-clauses-count');
    const clausesContainer = document.getElementById('clauses-container');
    const filterButtons = document.querySelectorAll('.filter-btn');

    let currentClauses = [];
    let currentFilter = 'all';

    const SAMPLE_TOS = `1. License to User Content: By submitting any material or data to the Service, you grant the Company a perpetual, irrevocable, worldwide, royalty-free, and transferable license to use, reproduce, modify, sell, and sublicense your content for any commercial or non-commercial purpose.
2. Unilateral Changes: The Company reserves the right to modify or terminate these Terms at any time without prior notice. Your continued use of the platform constitutes acceptance of all modifications.
3. Class Action Waiver & Mandatory Arbitration: Any dispute arising out of or related to these Terms shall be resolved exclusively through individual binding arbitration, and you expressly waive your right to initiate or participate in any class action litigation.
4. Limitation of Liability: In no event shall the Company be liable for any indirect, punitive, or consequential damages, and the total liability of Company shall not exceed $10 or the fees paid by you in the preceding one month.
5. Privacy & Data Handling: We may collect device telemetry and aggregate usage logs to improve system stability and diagnose software bugs.`;

    const SAMPLE_NDA = `1. Definition of Confidential Information: 'Confidential Information' includes all non-public technical, business, or proprietary information disclosed by either party, whether oral or written.
2. Non-Compete & Non-Solicitation: For a period of 5 years following termination of discussions, the Receiving Party shall not engage in any competing business venture or solicit any employees, contractors, or customers of the Disclosing Party worldwide.
3. Liquidated Damages: Any breach or suspected disclosure of confidential information shall trigger automatic liquidated damages of $100,000 payable immediately, without prejudice to injunctive relief.
4. Standard of Care: The Receiving Party agrees to protect Confidential Information using the same degree of care it uses to protect its own confidential materials of like nature, but no less than reasonable care.`;

    // Character counter
    contractInput.addEventListener('input', () => {
        const len = contractInput.value.length;
        charCount.textContent = `${len.toLocaleString()} character${len === 1 ? '' : 's'}`;
    });

    // Clear input
    clearBtn.addEventListener('click', () => {
        contractInput.value = '';
        charCount.textContent = '0 characters';
        hideError();
        contractInput.focus();
    });

    // Sample loaders
    sampleTosBtn.addEventListener('click', () => {
        contractInput.value = SAMPLE_TOS;
        contractInput.dispatchEvent(new Event('input'));
        hideError();
    });

    sampleNdaBtn.addEventListener('click', () => {
        contractInput.value = SAMPLE_NDA;
        contractInput.dispatchEvent(new Event('input'));
        hideError();
    });

    // Close error banner
    closeErrorBtn.addEventListener('click', hideError);

    function showError(message) {
        errorMessage.textContent = message;
        errorBanner.style.display = 'flex';
        errorBanner.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function hideError() {
        errorBanner.style.display = 'none';
    }

    function setLoading(isLoading) {
        if (isLoading) {
            analyzeBtn.disabled = true;
            btnText.textContent = 'Analyzing...';
            btnLoader.style.display = 'inline-block';
            loadingState.style.display = 'block';
            resultsSection.style.display = 'none';
            hideError();
        } else {
            analyzeBtn.disabled = false;
            btnText.textContent = 'Analyze Contract';
            btnLoader.style.display = 'none';
            loadingState.style.display = 'none';
        }
    }

    // Filter handling
    filterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            filterButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.getAttribute('data-filter');
            renderClauses();
        });
    });

    function renderScore(score) {
        overallScoreNum.textContent = score;

        if (score >= 65) {
            scoreTierLabel.textContent = 'High Risk Agreement';
            scoreTierLabel.style.color = 'var(--risk-high-text)';
            scoreBadgeCircle.style.borderColor = 'var(--risk-high-border)';
            scoreBadgeCircle.style.color = 'var(--risk-high-text)';
            scoreBadgeCircle.style.backgroundColor = 'var(--risk-high-bg)';
            scoreSummaryText.textContent = 'This agreement contains severe provisions, aggressive rights waivers, or heavy one-sided liabilities.';
        } else if (score >= 35) {
            scoreTierLabel.textContent = 'Moderate Risk Agreement';
            scoreTierLabel.style.color = 'var(--risk-med-text)';
            scoreBadgeCircle.style.borderColor = 'var(--risk-med-border)';
            scoreBadgeCircle.style.color = 'var(--risk-med-text)';
            scoreBadgeCircle.style.backgroundColor = 'var(--risk-med-bg)';
            scoreSummaryText.textContent = 'This agreement includes standard commercial terms with a few clauses warranting caution or negotiation.';
        } else {
            scoreTierLabel.textContent = 'Low Risk Agreement';
            scoreTierLabel.style.color = 'var(--risk-low-text)';
            scoreBadgeCircle.style.borderColor = 'var(--risk-low-border)';
            scoreBadgeCircle.style.color = 'var(--risk-low-text)';
            scoreBadgeCircle.style.backgroundColor = 'var(--risk-low-bg)';
            scoreSummaryText.textContent = 'Provisions are relatively balanced, standard, and do not introduce severe unilateral consumer risks.';
        }
    }

    function renderClauses() {
        clausesContainer.innerHTML = '';

        const filtered = currentClauses.filter(clause => {
            if (currentFilter === 'all') return true;
            return clause.risk_level === currentFilter;
        });

        if (filtered.length === 0) {
            const emptyMsg = document.createElement('div');
            emptyMsg.className = 'card no-clauses-msg';
            emptyMsg.textContent = `No ${currentFilter} risk clauses detected in this agreement.`;
            clausesContainer.appendChild(emptyMsg);
            return;
        }

        filtered.forEach((clause, idx) => {
            const card = document.createElement('div');
            const riskClass = `clause-${clause.risk_level}`;
            const badgeClass = `badge-${clause.risk_level}`;

            card.className = `card clause-card ${riskClass}`;
            
            const explanationIcon = clause.risk_level === 'high' ? '🚨' : (clause.risk_level === 'medium' ? '⚠️' : '✅');

            card.innerHTML = `
                <div class="clause-header-line">
                    <span class="clause-badge ${badgeClass}">${escapeHtml(clause.risk_level)} Risk</span>
                    <span class="clause-index">Clause #${idx + 1}</span>
                </div>
                <div class="clause-quote">${escapeHtml(clause.text)}</div>
                <div class="clause-explanation">
                    <span class="explanation-icon">${explanationIcon}</span>
                    <div class="explanation-text">
                        <strong>Plain-English Risk:</strong> ${escapeHtml(clause.explanation)}
                    </div>
                </div>
            `;

            clausesContainer.appendChild(card);
        });
    }

    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Main Analyze Flow
    analyzeBtn.addEventListener('click', async () => {
        const text = contractInput.value.trim();
        if (!text) {
            showError('Please enter or paste contract text before analyzing.');
            contractInput.focus();
            return;
        }

        setLoading(true);

        try {
            const response = await fetch('/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ text: text })
            });

            const data = await response.json();

            if (!response.ok) {
                let err = data.error || `Server responded with status ${response.status}`;
                if (data.raw_response) {
                    err += `\n\n[Raw Model Output]:\n${data.raw_response}`;
                }
                showError(err);
                return;
            }

            // Populate Results
            currentClauses = data.clauses || [];
            const score = typeof data.overall_risk_score === 'number' ? data.overall_risk_score : 50;

            let highCount = 0;
            let medCount = 0;
            let lowCount = 0;

            currentClauses.forEach(c => {
                if (c.risk_level === 'high') highCount++;
                else if (c.risk_level === 'medium') medCount++;
                else lowCount++;
            });

            countHigh.textContent = highCount;
            countMedium.textContent = medCount;
            countLow.textContent = lowCount;
            totalClausesCount.textContent = currentClauses.length;

            renderScore(score);
            renderClauses();

            resultsSection.style.display = 'block';
            resultsSection.scrollIntoView({ behavior: 'smooth' });

        } catch (err) {
            showError('Network error or server connection failed. Please check if Flask is running.');
        } finally {
            setLoading(false);
        }
    });
});
