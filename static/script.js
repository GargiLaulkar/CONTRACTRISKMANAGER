document.addEventListener('DOMContentLoaded', () => {
    const contractInput = document.getElementById('contract-input');
    const charCount = document.getElementById('char-count');
    const clearBtn = document.getElementById('clear-btn');
    const analyzeBtn = document.getElementById('analyze-btn');
    const btnText = analyzeBtn.querySelector('.btn-text');
    const btnLoader = analyzeBtn.querySelector('.btn-loader');

    const sampleTosBtn = document.getElementById('sample-tos-btn');
    const sampleNdaBtn = document.getElementById('sample-nda-btn');

    const uploadPdfBtn = document.getElementById('upload-pdf-btn');
    const pdfFileInput = document.getElementById('pdf-file-input');
    const pdfFilenameDisplay = document.getElementById('pdf-filename-display');

    const errorBanner = document.getElementById('error-banner');
    const errorMessage = document.getElementById('error-message');
    const closeErrorBtn = document.getElementById('close-error-btn');

    const loadingState = document.getElementById('loading-state');
    const pipelineStep1 = document.getElementById('pipeline-step-1');
    const pipelineStep2 = document.getElementById('pipeline-step-2');
    const pipelineStep3 = document.getElementById('pipeline-step-3');

    const resultsSection = document.getElementById('results-section');
    const pipelineMetricsText = document.getElementById('pipeline-metrics-text');

    const overallScoreNum = document.getElementById('overall-score-num');
    const scoreTierLabel = document.getElementById('score-tier-label');
    const scoreSummaryText = document.getElementById('score-summary-text');
    const gaugeFillCircle = document.getElementById('gauge-fill-circle');

    const countHigh = document.getElementById('count-high');
    const countMedium = document.getElementById('count-medium');
    const countLow = document.getElementById('count-low');
    const tabCardsCount = document.getElementById('tab-cards-count');

    const tabDocView = document.getElementById('tab-doc-view');
    const tabCardsView = document.getElementById('tab-cards-view');
    const docViewContainer = document.getElementById('doc-view-container');
    const cardsViewContainer = document.getElementById('cards-view-container');
    const highlightedDocumentBody = document.getElementById('highlighted-document-body');
    const docClausePopover = document.getElementById('doc-clause-popover');

    const clausesContainer = document.getElementById('clauses-container');
    const filterButtons = document.querySelectorAll('.filter-btn');

    let currentClauses = [];
    let currentOriginalText = '';
    let currentFilter = 'all';
    let stageTimers = [];

    const GAUGE_CIRCUMFERENCE = 314.16; // 2 * pi * 50

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
        pdfFilenameDisplay.textContent = '';
        pdfFileInput.value = '';
        hideError();
        contractInput.focus();
    });

    // Sample loaders
    sampleTosBtn.addEventListener('click', () => {
        contractInput.value = SAMPLE_TOS;
        contractInput.dispatchEvent(new Event('input'));
        pdfFilenameDisplay.textContent = '';
        pdfFileInput.value = '';
        hideError();
    });

    sampleNdaBtn.addEventListener('click', () => {
        contractInput.value = SAMPLE_NDA;
        contractInput.dispatchEvent(new Event('input'));
        pdfFilenameDisplay.textContent = '';
        pdfFileInput.value = '';
        hideError();
    });

    // PDF Upload handling
    uploadPdfBtn.addEventListener('click', () => {
        pdfFileInput.click();
    });

    pdfFileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            pdfFilenameDisplay.textContent = file.name;
            processPdfUpload(file);
        }
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

    // Pipeline Loading Animation
    function startPipelineLoading() {
        stageTimers.forEach(t => clearTimeout(t));
        stageTimers = [];

        analyzeBtn.disabled = true;
        uploadPdfBtn.disabled = true;
        btnText.textContent = 'Analyzing...';
        btnLoader.style.display = 'inline-block';
        loadingState.style.display = 'block';
        resultsSection.style.display = 'none';
        hideError();

        setStageActive(1);

        const t1 = setTimeout(() => {
            setStageCompleted(1);
            setStageActive(2);
        }, 900);
        stageTimers.push(t1);

        const t2 = setTimeout(() => {
            setStageCompleted(2);
            setStageActive(3);
        }, 2200);
        stageTimers.push(t2);
    }

    function setStageActive(stepNum) {
        [pipelineStep1, pipelineStep2, pipelineStep3].forEach((el, idx) => {
            if (idx + 1 === stepNum) {
                el.className = 'pipeline-step-item active';
            } else if (idx + 1 < stepNum) {
                el.className = 'pipeline-step-item completed';
            } else {
                el.className = 'pipeline-step-item';
            }
        });
    }

    function setStageCompleted(stepNum) {
        const el = [pipelineStep1, pipelineStep2, pipelineStep3][stepNum - 1];
        if (el) el.className = 'pipeline-step-item completed';
    }

    function stopPipelineLoading() {
        stageTimers.forEach(t => clearTimeout(t));
        stageTimers = [];

        analyzeBtn.disabled = false;
        uploadPdfBtn.disabled = false;
        btnText.textContent = 'Analyze contract';
        btnLoader.style.display = 'none';
        loadingState.style.display = 'none';
    }

    // View Switching (Document vs Cards)
    tabDocView.addEventListener('click', () => {
        tabDocView.classList.add('active');
        tabCardsView.classList.remove('active');
        docViewContainer.style.display = 'block';
        cardsViewContainer.style.display = 'none';
    });

    tabCardsView.addEventListener('click', () => {
        tabCardsView.classList.add('active');
        tabDocView.classList.remove('active');
        docViewContainer.style.display = 'none';
        cardsViewContainer.style.display = 'block';
    });

    // Filter handling
    filterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            filterButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.getAttribute('data-filter');
            renderClauses();
            renderHighlightedDocument(currentOriginalText, currentClauses);
        });
    });

    // Score Hero & Gauge Rendering
    function renderScoreGauge(score) {
        overallScoreNum.textContent = score;

        const offset = GAUGE_CIRCUMFERENCE * (1 - Math.min(100, Math.max(0, score)) / 100);
        gaugeFillCircle.style.strokeDashoffset = offset;

        if (score >= 65) {
            gaugeFillCircle.style.stroke = '#c96b6b';
            scoreTierLabel.textContent = 'High risk agreement';
            scoreTierLabel.style.color = '#e59999';
            scoreSummaryText.textContent = 'This agreement contains severe provisions, aggressive rights waivers, or heavy one-sided liabilities.';
        } else if (score >= 35) {
            gaugeFillCircle.style.stroke = '#c9a468';
            scoreTierLabel.textContent = 'Moderate risk agreement';
            scoreTierLabel.style.color = '#e2c08b';
            scoreSummaryText.textContent = 'This agreement includes standard commercial terms with a few clauses warranting caution or negotiation.';
        } else {
            gaugeFillCircle.style.stroke = '#6a9675';
            scoreTierLabel.textContent = 'Low risk agreement';
            scoreTierLabel.style.color = '#90c29d';
            scoreSummaryText.textContent = 'Provisions are relatively balanced, standard, and do not introduce severe unilateral consumer risks.';
        }
    }

    // Paper Document View with Redline Markup
    function renderHighlightedDocument(originalText, clauses) {
        if (!originalText) {
            highlightedDocumentBody.textContent = 'No original text available.';
            return;
        }

        const matches = [];
        const normOriginal = originalText;

        clauses.forEach((clause, cIdx) => {
            if (currentFilter !== 'all' && clause.risk_level !== currentFilter) {
                return;
            }

            const clauseSnippet = clause.text ? clause.text.trim() : '';
            if (!clauseSnippet) return;

            // Find substring in original text
            let startIdx = normOriginal.indexOf(clauseSnippet);
            let length = clauseSnippet.length;

            if (startIdx === -1) {
                const words = clauseSnippet.split(/\s+/).filter(w => w.length > 2);
                if (words.length > 0) {
                    const firstWord = words[0];
                    let searchPos = 0;
                    while ((searchPos = normOriginal.indexOf(firstWord, searchPos)) !== -1) {
                        const candidate = normOriginal.substr(searchPos, clauseSnippet.length + 20);
                        if (candidate.includes(words[words.length - 1])) {
                            startIdx = searchPos;
                            length = Math.min(candidate.length, normOriginal.length - searchPos);
                            break;
                        }
                        searchPos += firstWord.length;
                    }
                }
            }

            if (startIdx !== -1) {
                matches.push({
                    start: startIdx,
                    end: startIdx + length,
                    clause: clause,
                    index: cIdx
                });
            }
        });

        // Sort matches by start index to maintain linear document order
        matches.sort((a, b) => a.start - b.start);

        let html = '';
        let lastPos = 0;

        matches.forEach(m => {
            if (m.start >= lastPos) {
                // Normal document text
                html += escapeHtml(normOriginal.substring(lastPos, m.start));
                
                // Highlighted clause span (low risk has clean unmarked styling)
                const spanText = normOriginal.substring(m.start, m.end);
                const titleAttr = m.clause.risk_level === 'low' 
                    ? `Clause #${m.index + 1}: Low risk (click for analysis)` 
                    : `Clause #${m.index + 1}: ${capitalize(m.clause.risk_level)} risk (click for redline analysis)`;
                
                html += `<span class="doc-highlight risk-${m.clause.risk_level}" data-clause-idx="${m.index}" title="${titleAttr}">${escapeHtml(spanText)}</span>`;
                lastPos = m.end;
            }
        });

        if (lastPos < normOriginal.length) {
            html += escapeHtml(normOriginal.substring(lastPos));
        }

        highlightedDocumentBody.innerHTML = html;

        // Attach click handlers to highlighted spans
        const spans = highlightedDocumentBody.querySelectorAll('.doc-highlight');
        spans.forEach(span => {
            span.addEventListener('click', () => {
                spans.forEach(s => s.classList.remove('selected'));
                span.classList.add('selected');
                const idx = parseInt(span.getAttribute('data-clause-idx'), 10);
                showClausePopover(clauses[idx], idx);
            });
        });
    }

    // Popover Detail Drawer with Tracked-Change Diff View
    function showClausePopover(clause, idx) {
        if (!clause) return;

        const explanationIcon = clause.risk_level === 'high' ? '🚨' : (clause.risk_level === 'medium' ? '⚠️' : '✅');
        const badgeClass = `badge-${clause.risk_level}`;
        const escalatedBadgeHtml = clause.escalated 
            ? `<span class="badge-escalated">Verified by advanced model</span>` 
            : '';

        let diffHtml = '';
        if (clause.suggested_revision && clause.suggested_revision.trim()) {
            diffHtml = `
                <div class="redline-diff-box">
                    <div class="redline-diff-label">Suggested rewrite (tracked changes)</div>
                    <div class="redline-diff-content">
                        <span class="redline-del">${escapeHtml(clause.text)}</span>
                        <span class="redline-arrow">➔</span>
                        <span class="redline-ins">${escapeHtml(clause.suggested_revision)}</span>
                    </div>
                </div>
            `;
        }

        docClausePopover.innerHTML = `
            <div class="popover-header">
                <div class="clause-badges-left">
                    <span class="clause-badge ${badgeClass}">${capitalize(clause.risk_level)} risk</span>
                    ${escalatedBadgeHtml}
                    <strong style="color: var(--paper-ink); font-size: 0.95rem; font-family: sans-serif;">Clause #${idx + 1}</strong>
                </div>
                <button type="button" class="popover-close-btn" id="popover-close-btn" aria-label="Close detail">&times;</button>
            </div>

            <div class="popover-explanation">
                <span class="explanation-icon">${explanationIcon}</span>
                <strong>Plain-English risk:</strong> ${escapeHtml(clause.explanation)}
            </div>

            ${diffHtml}
        `;

        docClausePopover.style.display = 'block';
        docClausePopover.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        const closeBtn = document.getElementById('popover-close-btn');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                docClausePopover.style.display = 'none';
                const spans = highlightedDocumentBody.querySelectorAll('.doc-highlight');
                spans.forEach(s => s.classList.remove('selected'));
            });
        }
    }

    // Cards View
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

            const escalatedBadgeHtml = clause.escalated 
                ? `<span class="badge-escalated" title="Clause underwent Stage 3 deep model verification">Verified by advanced model</span>` 
                : '';

            let diffHtml = '';
            if (clause.suggested_revision && clause.suggested_revision.trim()) {
                diffHtml = `
                    <div class="redline-diff-box">
                        <div class="redline-diff-label">Suggested rewrite (tracked changes)</div>
                        <div class="redline-diff-content">
                            <span class="redline-del">${escapeHtml(clause.text)}</span>
                            <span class="redline-arrow">➔</span>
                            <span class="redline-ins">${escapeHtml(clause.suggested_revision)}</span>
                        </div>
                    </div>
                `;
            }

            card.innerHTML = `
                <div class="clause-header-line">
                    <div class="clause-badges-left">
                        <span class="clause-badge ${badgeClass}">${capitalize(clause.risk_level)} risk</span>
                        ${escalatedBadgeHtml}
                    </div>
                    <span class="clause-index">Clause #${idx + 1}</span>
                </div>
                <div class="clause-quote">${escapeHtml(clause.text)}</div>
                <div class="clause-explanation">
                    <span class="explanation-icon">${explanationIcon}</span>
                    <div class="explanation-text">
                        <strong>Plain-English risk:</strong> ${escapeHtml(clause.explanation)}
                    </div>
                </div>
                ${diffHtml}
            `;

            clausesContainer.appendChild(card);
        });
    }

    function capitalize(str) {
        if (!str) return '';
        return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
    }

    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Success Handler
    function handleSuccessData(data, fallbackOriginalText) {
        currentClauses = data.clauses || [];
        currentOriginalText = data.original_text || fallbackOriginalText || '';
        const score = typeof data.overall_risk_score === 'number' ? data.overall_risk_score : 50;

        // Pipeline Metrics as an Understated Subtext Line
        const s1 = data.stage1_scanned || currentClauses.length;
        const s2 = data.stage2_flagged !== undefined ? data.stage2_flagged : currentClauses.filter(c => c.risk_level !== 'low').length;
        const s3 = data.stage3_escalated !== undefined ? data.stage3_escalated : currentClauses.filter(c => c.escalated).length;

        pipelineMetricsText.textContent = `${s1} clauses scanned · ${s2} flagged for deep analysis · ${s3} escalated to advanced model`;

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
        tabCardsCount.textContent = currentClauses.length;

        renderScoreGauge(score);
        renderHighlightedDocument(currentOriginalText, currentClauses);
        renderClauses();

        resultsSection.style.display = 'block';
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    // Textarea Analyze Flow
    analyzeBtn.addEventListener('click', async () => {
        const text = contractInput.value.trim();
        if (!text) {
            showError('Please enter or paste contract text before analyzing.');
            contractInput.focus();
            return;
        }

        startPipelineLoading();

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

            handleSuccessData(data, text);

        } catch (err) {
            showError('Network error or server connection failed. Please check if Flask is running.');
        } finally {
            stopPipelineLoading();
        }
    });

    // PDF Upload Flow
    async function processPdfUpload(file) {
        startPipelineLoading();

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('/analyze-pdf', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                let err = data.error || `PDF Analysis failed with status ${response.status}`;
                if (data.raw_response) {
                    err += `\n\n[Raw Model Output]:\n${data.raw_response}`;
                }
                showError(err);
                return;
            }

            handleSuccessData(data, '');

        } catch (err) {
            showError('Network error during PDF upload. Please verify the Flask server is running.');
        } finally {
            stopPipelineLoading();
        }
    }
});
