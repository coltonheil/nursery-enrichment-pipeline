// Enrichment functionality
console.log('[App.js] Script loaded - initializing');

// Global batch size variables
let aiBatchSize = null;
let scoreBatchSize = null;
let googlePlacesBatchSize = null;
let pipelineBatchSize = 25; // Default to 25 for full pipeline

// Set batch size for Full Pipeline
function setPipelineBatchSize(size) {
    pipelineBatchSize = parseInt(size);
    const pipelineBtn = document.getElementById('full-pipeline-btn');
    if (pipelineBtn) {
        pipelineBtn.innerHTML = `<i class="bi bi-play-circle-fill"></i> Run Full Pipeline (${pipelineBatchSize} leads)`;
    }
    console.log('[App.js] Pipeline batch size set to:', pipelineBatchSize);
}

// Set batch size for Google Places enrichment
function setGooglePlacesBatchSize(size) {
    googlePlacesBatchSize = size ? parseInt(size) : null;
    const googlePlacesBtn = document.getElementById('google-places-btn');
    if (googlePlacesBtn) {
        if (googlePlacesBatchSize) {
            googlePlacesBtn.innerHTML = `<i class="bi bi-geo-alt"></i> Google Places (Next ${googlePlacesBatchSize})`;
        } else {
            googlePlacesBtn.innerHTML = '<i class="bi bi-geo-alt"></i> Google Places';
        }
    }
    console.log('[App.js] Google Places batch size set to:', googlePlacesBatchSize);
}

// Set batch size for AI enrichment
function setBatchSize(size) {
    aiBatchSize = size ? parseInt(size) : null;
    const aiEnrichBtn = document.getElementById('ai-enrich-btn');
    if (aiEnrichBtn) {
        if (aiBatchSize) {
            aiEnrichBtn.innerHTML = `<i class="bi bi-stars"></i> AI Enrich (Next ${aiBatchSize})`;
        } else {
            aiEnrichBtn.innerHTML = '<i class="bi bi-stars"></i> AI Enrich';
        }
    }
    console.log('[App.js] AI batch size set to:', aiBatchSize);
}

// Set batch size for scoring
function setScoreBatchSize(size) {
    scoreBatchSize = size ? parseInt(size) : null;
    const scoreBtn = document.getElementById('score-all-btn');
    if (scoreBtn) {
        if (scoreBatchSize) {
            scoreBtn.innerHTML = `<i class="bi bi-calculator"></i> Score (Next ${scoreBatchSize})`;
        } else {
            scoreBtn.innerHTML = '<i class="bi bi-calculator"></i> Score Leads';
        }
    }
    console.log('[App.js] Score batch size set to:', scoreBatchSize);
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('[App.js] DOM Content Loaded - attaching event listeners');

    // Get elements
    const enrichButtons = document.querySelectorAll('.enrich-btn');
    const enrichSelectedBtn = document.getElementById('enrich-selected-btn');
    const selectAllCheckbox = document.getElementById('select-all-checkbox');
    const selectAllBtn = document.getElementById('select-all-btn');
    const leadCheckboxes = document.querySelectorAll('.lead-checkbox');
    const searchInput = document.getElementById('search-input');
    const table = document.getElementById('leads-table');

    // Search functionality
    if (searchInput && table) {
        searchInput.addEventListener('keyup', function() {
            const searchTerm = this.value.toLowerCase();
            const rows = table.getElementsByTagName('tbody')[0].getElementsByTagName('tr');

            for (let i = 0; i < rows.length; i++) {
                const row = rows[i];
                const text = row.textContent.toLowerCase();

                if (text.includes(searchTerm)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            }
        });
    }

    // Select all functionality
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            leadCheckboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
            updateEnrichSelectedButton();
        });
    }

    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', function() {
            const allChecked = Array.from(leadCheckboxes).every(cb => cb.checked);
            leadCheckboxes.forEach(checkbox => {
                checkbox.checked = !allChecked;
            });
            selectAllCheckbox.checked = !allChecked;
            updateEnrichSelectedButton();
        });
    }

    // Update enrich selected button state
    leadCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', updateEnrichSelectedButton);
    });

    function updateEnrichSelectedButton() {
        const checkedCount = Array.from(leadCheckboxes).filter(cb => cb.checked).length;
        if (enrichSelectedBtn) {
            enrichSelectedBtn.disabled = checkedCount === 0;
            enrichSelectedBtn.innerHTML = `<i class="bi bi-stars"></i> Enrich Selected (${checkedCount})`;
        }
    }

    // Individual enrich button
    enrichButtons.forEach(button => {
        button.addEventListener('click', function() {
            const leadId = this.getAttribute('data-lead-id');
            enrichLead(leadId);
        });
    });

    // Batch enrich button
    if (enrichSelectedBtn) {
        enrichSelectedBtn.addEventListener('click', function() {
            const selectedLeadIds = Array.from(leadCheckboxes)
                .filter(cb => cb.checked)
                .map(cb => cb.value);

            if (selectedLeadIds.length > 0) {
                enrichBatch(selectedLeadIds);
            }
        });
    }

    // Enrich single lead
    function enrichLead(leadId) {
        const row = document.getElementById(`lead-row-${leadId}`);
        const button = row.querySelector('.enrich-btn');

        // Show loading state
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Enriching...';

        fetch(`/enrich/${leadId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showAlert('Error enriching lead: ' + data.error, 'danger');
                button.innerHTML = '<i class="bi bi-x-circle"></i> Failed';
                updateRowStatus(row, 'failed');
            } else {
                showAlert('Lead enriched successfully!', 'success');
                updateRowWithData(row, data.data);
                button.innerHTML = '<i class="bi bi-check-circle"></i> Enriched';
                button.disabled = true;
            }
        })
        .catch(error => {
            showAlert('Error: ' + error.message, 'danger');
            button.innerHTML = '<i class="bi bi-stars"></i> Enrich';
            button.disabled = false;
        });
    }

    // Enrich multiple leads
    function enrichBatch(leadIds) {
        enrichSelectedBtn.disabled = true;
        enrichSelectedBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Enriching...';

        fetch('/enrich-batch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ lead_ids: leadIds })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showAlert('Error: ' + data.error, 'danger');
            } else {
                const successCount = data.success.length;
                const failedCount = data.failed.length;

                if (failedCount > 0) {
                    showAlert(`Enriched ${successCount} leads. ${failedCount} failed.`, 'warning');
                    data.errors.forEach(err => showAlert(err, 'danger'));
                } else {
                    showAlert(`Successfully enriched ${successCount} leads!`, 'success');
                }

                // Reload page to show updated data
                setTimeout(() => location.reload(), 2000);
            }

            enrichSelectedBtn.innerHTML = '<i class="bi bi-stars"></i> Enrich Selected';
            enrichSelectedBtn.disabled = false;
        })
        .catch(error => {
            showAlert('Error: ' + error.message, 'danger');
            enrichSelectedBtn.innerHTML = '<i class="bi bi-stars"></i> Enrich Selected';
            enrichSelectedBtn.disabled = false;
        });
    }

    // Update row with enriched data
    function updateRowWithData(row, data) {
        // Update phone
        if (data.phone) {
            const phoneCell = row.querySelector('.phone-cell');
            phoneCell.textContent = data.phone;
        }

        // Update website
        if (data.website) {
            const websiteCell = row.querySelector('.website-cell');
            websiteCell.innerHTML = `<a href="${data.website}" target="_blank" class="text-decoration-none"><i class="bi bi-link-45deg"></i> Link</a>`;
        }

        // Update rating
        if (data.rating) {
            const ratingCell = row.querySelector('.rating-cell');
            ratingCell.innerHTML = `<span class="badge bg-warning text-dark"><i class="bi bi-star-fill"></i> ${data.rating}</span>`;
        }

        // Update review count
        if (data.review_count) {
            const reviewCell = row.querySelector('.review-count-cell');
            reviewCell.textContent = data.review_count;
        }

        // Update enrichment status
        updateRowStatus(row, 'enriched');

        // Update row color
        row.classList.remove('table-warning', 'table-danger');
        row.classList.add('table-success');
    }

    // Update row status badge
    function updateRowStatus(row, status) {
        const statusCell = row.querySelector('.enrichment-status-cell');

        if (status === 'enriched') {
            statusCell.innerHTML = '<span class="badge bg-success"><i class="bi bi-check-circle"></i> Enriched</span>';
        } else if (status === 'failed') {
            statusCell.innerHTML = '<span class="badge bg-danger"><i class="bi bi-x-circle"></i> Failed</span>';
        } else if (status === 'pending') {
            statusCell.innerHTML = '<span class="badge bg-warning"><i class="bi bi-clock"></i> Pending</span>';
        }
    }

    // Show alert message
    function showAlert(message, type) {
        const alertsContainer = document.querySelector('.container.mt-4');
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.role = 'alert';

        let icon = 'info-circle';
        if (type === 'success') icon = 'check-circle-fill';
        if (type === 'danger') icon = 'exclamation-triangle-fill';
        if (type === 'warning') icon = 'exclamation-circle-fill';

        alert.innerHTML = `
            <i class="bi bi-${icon}"></i> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        alertsContainer.appendChild(alert);

        // Auto dismiss after 5 seconds
        setTimeout(() => {
            alert.remove();
        }, 5000);
    }

    // Scraping functionality

    // =================================================================
    // FULL PIPELINE ELEMENTS AND HANDLERS
    // =================================================================
    const pipelineBtn = document.getElementById('full-pipeline-btn');
    const stopPipelineBtn = document.getElementById('stop-pipeline-btn');
    const pipelineProgress = document.getElementById('pipeline-progress');
    const pipelineOverallProgressBar = document.getElementById('pipeline-overall-progress-bar');
    const pipelineOverallPercentage = document.getElementById('pipeline-overall-percentage');
    const pipelineStepPercentage = document.getElementById('pipeline-step-percentage');
    const pipelineStatusMessage = document.getElementById('pipeline-status-message');
    const pipelineStepIndicator = document.getElementById('pipeline-step-indicator');
    const step1Indicator = document.getElementById('step-1-indicator');
    const step2Indicator = document.getElementById('step-2-indicator');
    const step3Indicator = document.getElementById('step-3-indicator');
    const step4Indicator = document.getElementById('step-4-indicator');

    console.log('[App.js] Full Pipeline button found:', !!pipelineBtn);

    if (pipelineBtn) {
        pipelineBtn.addEventListener('click', function() {
            console.log('[App.js] Full Pipeline button clicked');
            console.log('[App.js] Batch size:', pipelineBatchSize);

            if (!confirm(`Run full enrichment pipeline on ${pipelineBatchSize} leads?\n\nThis will:\n1. Enrich with Google Places (costs $)\n2. Scrape websites\n3. AI enrich with Gemini (costs $)\n4. Score leads\n\nEstimated cost: ~$${(pipelineBatchSize * 0.001).toFixed(2)}`)) {
                return;
            }

            // Start full pipeline
            fetch('/pipeline/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ batch_size: pipelineBatchSize })
            })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        showAlert(data.error, 'danger');
                    } else {
                        showAlert(data.message, 'success');
                        pipelineBtn.disabled = true;
                        pipelineProgress.style.display = 'block';

                        // Hide other progress bars
                        if (googlePlacesProgress) googlePlacesProgress.style.display = 'none';
                        if (scrapingProgress) scrapingProgress.style.display = 'none';

                        // Start SSE connection
                        startPipelineUpdates();
                    }
                })
                .catch(error => {
                    showAlert('Error starting pipeline: ' + error, 'danger');
                });
        });
    }

    if (stopPipelineBtn) {
        stopPipelineBtn.addEventListener('click', function() {
            fetch('/pipeline/stop', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    showAlert(data.message || 'Stop requested', 'info');
                    stopPipelineBtn.disabled = true;
                })
                .catch(error => {
                    showAlert('Error stopping pipeline: ' + error, 'danger');
                });
        });
    }

    function startPipelineUpdates() {
        // Close existing connection if any
        if (eventSource) {
            eventSource.close();
        }

        // Create new SSE connection
        eventSource = new EventSource('/pipeline/status');

        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);

            // Update overall progress
            pipelineOverallProgressBar.style.width = data.overall_progress + '%';
            pipelineOverallPercentage.textContent = data.overall_progress + '%';
            pipelineStepPercentage.textContent = data.step_progress + '%';
            pipelineStatusMessage.textContent = data.status_message;
            pipelineStepIndicator.textContent = `Step ${data.completed_steps}/${data.total_steps}`;

            // Update step indicators
            [step1Indicator, step2Indicator, step3Indicator, step4Indicator].forEach((el, idx) => {
                if (el) {
                    el.classList.remove('bg-success', 'bg-warning', 'text-white');
                    if (idx < data.completed_steps) {
                        el.classList.add('bg-success', 'text-white');
                    } else if (data.current_step === ['google_places', 'scraping', 'ai_enrichment', 'scoring'][idx]) {
                        el.classList.add('bg-warning', 'text-white');
                    }
                }
            });

            // Check if done
            if (!data.running && data.overall_progress >= 100) {
                eventSource.close();
                pipelineBtn.disabled = false;
                stopPipelineBtn.disabled = false;
                pipelineOverallProgressBar.classList.remove('progress-bar-animated');

                showAlert(`Pipeline complete! ${data.status_message}`, 'success');

                // Reload page after 2 seconds to show updated data
                setTimeout(() => location.reload(), 2000);
            }
        };

        eventSource.onerror = function(error) {
            console.error('SSE Error:', error);
            eventSource.close();
            showAlert('Lost connection to server', 'danger');
        };
    }

    // =================================================================
    // GOOGLE PLACES ENRICHMENT ELEMENTS AND HANDLERS
    // =================================================================
    // Google Places Enrichment elements
    const googlePlacesBtn = document.getElementById('google-places-btn');
    const stopGooglePlacesBtn = document.getElementById('stop-google-places-btn');
    const googlePlacesProgress = document.getElementById('google-places-progress');
    const googlePlacesProgressBar = document.getElementById('google-places-progress-bar');
    const googlePlacesCompleted = document.getElementById('google-places-completed');
    const googlePlacesFailed = document.getElementById('google-places-failed');
    const googlePlacesTotal = document.getElementById('google-places-total');
    const googlePlacesCurrent = document.getElementById('google-places-current');

    console.log('[App.js] Google Places button found:', !!googlePlacesBtn);

    // Scraping elements
    const scrapeWebsitesBtn = document.getElementById('scrape-websites-btn');
    const stopScrapingBtn = document.getElementById('stop-scraping-btn');
    const scrapingProgress = document.getElementById('scraping-progress');
    const scrapingProgressBar = document.getElementById('scraping-progress-bar');
    const scrapingCompleted = document.getElementById('scraping-completed');
    const scrapingFailed = document.getElementById('scraping-failed');
    const scrapingTotal = document.getElementById('scraping-total');
    const scrapingCurrent = document.getElementById('scraping-current');

    console.log('[App.js] Scrape button found:', !!scrapeWebsitesBtn);

    let eventSource = null;

    // Google Places Enrichment handlers
    if (googlePlacesBtn) {
        googlePlacesBtn.addEventListener('click', function() {
            console.log('[App.js] Google Places button clicked - starting enrichment');
            console.log('[App.js] Batch size:', googlePlacesBatchSize);

            // Prepare request body
            const requestBody = googlePlacesBatchSize ? { batch_size: googlePlacesBatchSize } : {};

            // Start Google Places enrichment
            fetch('/google-places/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody)
            })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        showAlert(data.error, 'danger');
                    } else {
                        showAlert(data.message || 'Google Places enrichment started!', 'success');
                        googlePlacesBtn.disabled = true;
                        googlePlacesProgress.style.display = 'block';

                        // Start SSE connection
                        startGooglePlacesUpdates();
                    }
                })
                .catch(error => {
                    showAlert('Error starting Google Places enrichment: ' + error, 'danger');
                });
        });
    }

    if (stopGooglePlacesBtn) {
        stopGooglePlacesBtn.addEventListener('click', function() {
            fetch('/google-places/stop', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    showAlert(data.message || 'Stop requested', 'info');
                    stopGooglePlacesBtn.disabled = true;
                })
                .catch(error => {
                    showAlert('Error stopping Google Places enrichment: ' + error, 'danger');
                });
        });
    }

    function startGooglePlacesUpdates() {
        // Close existing connection if any
        if (eventSource) {
            eventSource.close();
        }

        // Create new SSE connection
        eventSource = new EventSource('/google-places/status');

        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);

            // Update UI
            googlePlacesCompleted.textContent = data.completed;
            googlePlacesFailed.textContent = data.failed;
            googlePlacesTotal.textContent = data.total;

            // Update progress bar
            if (data.total > 0) {
                const percentage = ((data.completed + data.failed) / data.total * 100).toFixed(0);
                googlePlacesProgressBar.style.width = percentage + '%';
                googlePlacesProgressBar.textContent = percentage + '%';
            }

            // Update current lead
            if (data.current_lead) {
                googlePlacesCurrent.textContent = `Currently enriching: ${data.current_lead}`;
            }

            // Check if done
            if (!data.running && data.completed + data.failed >= data.total) {
                eventSource.close();
                googlePlacesBtn.disabled = false;
                stopGooglePlacesBtn.disabled = false;
                googlePlacesCurrent.textContent = 'Google Places enrichment complete!';
                googlePlacesProgressBar.classList.remove('progress-bar-animated');

                showAlert(`Google Places enrichment complete! Enriched: ${data.completed}, Failed: ${data.failed}`, 'success');

                // Reload page after 2 seconds to show updated data
                setTimeout(() => location.reload(), 2000);
            }
        };

        eventSource.onerror = function(error) {
            console.error('SSE Error:', error);
            eventSource.close();
            showAlert('Lost connection to server', 'danger');
        };
    }

    if (scrapeWebsitesBtn) {
        scrapeWebsitesBtn.addEventListener('click', function() {
            console.log('[App.js] Scrape button clicked - starting scraping');
            // Start scraping
            fetch('/scrape/start', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        showAlert(data.error, 'danger');
                    } else {
                        showAlert('Website scraping started!', 'success');
                        scrapeWebsitesBtn.disabled = true;
                        scrapingProgress.style.display = 'block';

                        // Start SSE connection
                        startScrapingUpdates();
                    }
                })
                .catch(error => {
                    showAlert('Error starting scraping: ' + error, 'danger');
                });
        });
    }

    if (stopScrapingBtn) {
        stopScrapingBtn.addEventListener('click', function() {
            fetch('/scrape/stop', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    showAlert(data.message || 'Stop requested', 'info');
                    stopScrapingBtn.disabled = true;
                })
                .catch(error => {
                    showAlert('Error stopping scraping: ' + error, 'danger');
                });
        });
    }

    function startScrapingUpdates() {
        // Close existing connection if any
        if (eventSource) {
            eventSource.close();
        }

        // Create new SSE connection
        eventSource = new EventSource('/scrape/status');

        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);

            // Update UI
            scrapingCompleted.textContent = data.completed;
            scrapingFailed.textContent = data.failed;
            scrapingTotal.textContent = data.total;

            // Update progress bar
            if (data.total > 0) {
                const percentage = ((data.completed + data.failed) / data.total * 100).toFixed(0);
                scrapingProgressBar.style.width = percentage + '%';
                scrapingProgressBar.textContent = percentage + '%';
            }

            // Update current lead
            if (data.current_lead) {
                scrapingCurrent.textContent = `Currently scraping: ${data.current_lead}`;
            }

            // Check if done
            if (!data.running && data.completed + data.failed >= data.total) {
                eventSource.close();
                scrapeWebsitesBtn.disabled = false;
                stopScrapingBtn.disabled = false;
                scrapingCurrent.textContent = 'Scraping complete!';
                scrapingProgressBar.classList.remove('progress-bar-animated');

                showAlert(`Scraping complete! Scraped: ${data.completed}, Failed: ${data.failed}`, 'success');

                // Reload page after 2 seconds to show updated data
                setTimeout(() => location.reload(), 2000);
            }
        };

        eventSource.onerror = function(error) {
            console.error('SSE Error:', error);
            eventSource.close();
            showAlert('Lost connection to server', 'danger');
        };
    }

    // AI Enrichment functionality
    const aiEnrichBtn = document.getElementById('ai-enrich-btn');
    const stopAiEnrichmentBtn = document.getElementById('stop-ai-enrichment-btn');
    const aiEnrichmentProgress = document.getElementById('ai-enrichment-progress');
    const aiEnrichmentProgressBar = document.getElementById('ai-enrichment-progress-bar');
    const aiEnrichmentCompleted = document.getElementById('ai-enrichment-completed');
    const aiEnrichmentFailed = document.getElementById('ai-enrichment-failed');
    const aiEnrichmentTotal = document.getElementById('ai-enrichment-total');
    const aiEnrichmentCurrent = document.getElementById('ai-enrichment-current');

    console.log('[App.js] AI Enrich button found:', !!aiEnrichBtn);

    let aiEventSource = null;

    if (aiEnrichBtn) {
        aiEnrichBtn.addEventListener('click', function() {
            console.log('[App.js] AI Enrich button clicked - starting AI enrichment');
            console.log('[App.js] Batch size:', aiBatchSize);

            // Prepare request body
            const requestBody = aiBatchSize ? { batch_size: aiBatchSize } : {};

            // Start AI enrichment
            fetch('/enrich-ai/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody)
            })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        showAlert(data.error, 'danger');
                    } else {
                        showAlert(data.message || 'AI enrichment started!', 'success');
                        aiEnrichBtn.disabled = true;
                        aiEnrichmentProgress.style.display = 'block';

                        // Start SSE connection
                        startAiEnrichmentUpdates();
                    }
                })
                .catch(error => {
                    showAlert('Error starting AI enrichment: ' + error, 'danger');
                });
        });
    }

    if (stopAiEnrichmentBtn) {
        stopAiEnrichmentBtn.addEventListener('click', function() {
            fetch('/enrich-ai/stop', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    showAlert(data.message || 'Stop requested', 'info');
                    stopAiEnrichmentBtn.disabled = true;
                })
                .catch(error => {
                    showAlert('Error stopping AI enrichment: ' + error, 'danger');
                });
        });
    }

    function startAiEnrichmentUpdates() {
        // Close existing connection if any
        if (aiEventSource) {
            aiEventSource.close();
        }

        // Create new SSE connection
        aiEventSource = new EventSource('/enrich-ai/status');

        aiEventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);

            // Update UI
            aiEnrichmentCompleted.textContent = data.completed;
            aiEnrichmentFailed.textContent = data.failed;
            aiEnrichmentTotal.textContent = data.total;

            // Update progress bar
            if (data.total > 0) {
                const percentage = ((data.completed + data.failed) / data.total * 100).toFixed(0);
                aiEnrichmentProgressBar.style.width = percentage + '%';
                aiEnrichmentProgressBar.textContent = percentage + '%';
            }

            // Update current lead
            if (data.current_lead) {
                aiEnrichmentCurrent.textContent = `Currently enriching: ${data.current_lead}`;
            }

            // Check if done
            if (!data.running && data.completed + data.failed >= data.total) {
                aiEventSource.close();
                aiEnrichBtn.disabled = false;
                stopAiEnrichmentBtn.disabled = false;
                aiEnrichmentCurrent.textContent = 'AI enrichment complete!';
                aiEnrichmentProgressBar.classList.remove('progress-bar-animated');

                showAlert(`AI enrichment complete! Enriched: ${data.completed}, Failed: ${data.failed}`, 'success');

                // Reload page after 2 seconds to show updated data
                setTimeout(() => location.reload(), 2000);
            }
        };

        aiEventSource.onerror = function(error) {
            console.error('SSE Error:', error);
            aiEventSource.close();
            showAlert('Lost connection to server', 'danger');
        };
    }

    // Scoring functionality
    const scoreAllBtn = document.getElementById('score-all-btn');
    const tierDistribution = document.getElementById('tier-distribution');

    console.log('[App.js] Score All button found:', !!scoreAllBtn);

    if (scoreAllBtn) {
        scoreAllBtn.addEventListener('click', function() {
            console.log('[App.js] Score button clicked');
            console.log('[App.js] Score batch size:', scoreBatchSize);

            // Confirm action
            const confirmMsg = scoreBatchSize
                ? `This will score the next ${scoreBatchSize} leads. Continue?`
                : 'This will score all leads in the database. Continue?';

            if (!confirm(confirmMsg)) {
                console.log('[App.js] Scoring cancelled by user');
                return;
            }
            console.log('[App.js] Scoring confirmed - starting');

            // Disable button and show loading
            scoreAllBtn.disabled = true;
            scoreAllBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Scoring...';

            // Prepare request body
            const requestBody = scoreBatchSize ? { batch_size: scoreBatchSize } : {};

            fetch('/score/all', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody)
            })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        showAlert('Error scoring leads: ' + data.error, 'danger');
                        scoreAllBtn.disabled = false;
                        // Restore button text
                        if (scoreBatchSize) {
                            scoreAllBtn.innerHTML = `<i class="bi bi-calculator"></i> Score (Next ${scoreBatchSize})`;
                        } else {
                            scoreAllBtn.innerHTML = '<i class="bi bi-calculator"></i> Score Leads';
                        }
                    } else {
                        showAlert(data.message, 'success');

                        // Update tier distribution
                        updateTierDistribution(data.tier_distribution);

                        // Re-enable button
                        scoreAllBtn.disabled = false;
                        // Restore button text
                        if (scoreBatchSize) {
                            scoreAllBtn.innerHTML = `<i class="bi bi-calculator"></i> Score (Next ${scoreBatchSize})`;
                        } else {
                            scoreAllBtn.innerHTML = '<i class="bi bi-calculator"></i> Score Leads';
                        }

                        // Reload page after 2 seconds
                        setTimeout(() => location.reload(), 2000);
                    }
                })
                .catch(error => {
                    showAlert('Error: ' + error.message, 'danger');
                    scoreAllBtn.disabled = false;
                    // Restore button text
                    if (scoreBatchSize) {
                        scoreAllBtn.innerHTML = `<i class="bi bi-calculator"></i> Score (Next ${scoreBatchSize})`;
                    } else {
                        scoreAllBtn.innerHTML = '<i class="bi bi-calculator"></i> Score Leads';
                    }
                });
        });
    }

    // Load tier distribution on page load
    function loadTierDistribution() {
        fetch('/api/tier-distribution')
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error('Error loading tier distribution:', data.error);
                } else {
                    updateTierDistribution(data);
                }
            })
            .catch(error => {
                console.error('Error loading tier distribution:', error);
            });
    }

    function updateTierDistribution(data) {
        const total = data.total || 0;

        if (total === 0) {
            // Hide tier distribution if no scores yet
            if (tierDistribution) {
                tierDistribution.style.display = 'none';
            }
            return;
        }

        // Show tier distribution
        if (tierDistribution) {
            tierDistribution.style.display = 'block';
        }

        // Update counts and percentages
        ['A', 'B', 'C', 'U'].forEach(tier => {
            const count = data[tier] || 0;
            const percent = total > 0 ? ((count / total) * 100).toFixed(1) : 0;

            const countEl = document.getElementById(`tier-${tier.toLowerCase()}-count`);
            const percentEl = document.getElementById(`tier-${tier.toLowerCase()}-percent`);

            if (countEl) countEl.textContent = count;
            if (percentEl) percentEl.textContent = percent + '%';
        });
    }

    // Load tier distribution on page load
    if (tierDistribution) {
        loadTierDistribution();
    }

    // Save review button - moved inside DOMContentLoaded
    const saveReviewBtn = document.getElementById('saveReviewBtn');
    if (saveReviewBtn) {
        saveReviewBtn.addEventListener('click', function() {
            if (!currentLeadData) return;

            const tierOverride = document.getElementById('tierOverride').value || null;
            const reviewNotes = document.getElementById('reviewNotes').value;

            fetch(`/api/lead/${currentLeadData.id}/review`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    tier_override: tierOverride,
                    review_notes: reviewNotes,
                    reviewed_by: 'user'
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert('Error: ' + data.error);
                } else {
                    alert('Review saved successfully!');
                    location.reload();
                }
            })
            .catch(error => {
                alert('Error: ' + error.message);
            });
        });
    }

    // Checkbox selection management
    const bulkActionsBar = document.getElementById('bulk-actions-bar');
    const selectedCountSpan = document.getElementById('selected-count');

    function updateSelectionCount() {
        const checkedCount = Array.from(leadCheckboxes).filter(cb => cb.checked).length;
        if (selectedCountSpan) selectedCountSpan.textContent = checkedCount;

        if (bulkActionsBar) {
            bulkActionsBar.style.display = checkedCount > 0 ? 'block' : 'none';
        }
    }

    leadCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', updateSelectionCount);
    });

    // Select all on page
    const selectAllPageBtn = document.getElementById('select-all-page-btn');
    if (selectAllPageBtn) {
        selectAllPageBtn.addEventListener('click', function(e) {
            e.preventDefault();
            const allChecked = Array.from(leadCheckboxes).every(cb => cb.checked);
            leadCheckboxes.forEach(cb => cb.checked = !allChecked);
            updateSelectionCount();
        });
    }

    // Personalization functionality
    const personalizeBtn = document.getElementById('personalize-btn');
    const stopPersonalizationBtn = document.getElementById('stop-personalization-btn');
    const personalizationProgress = document.getElementById('personalization-progress');
    const personalizationProgressBar = document.getElementById('personalization-progress-bar');
    const personalizationCompleted = document.getElementById('personalization-completed');
    const personalizationFailed = document.getElementById('personalization-failed');
    const personalizationTotal = document.getElementById('personalization-total');
    const personalizationCurrent = document.getElementById('personalization-current');

    console.log('[App.js] Personalize button found:', !!personalizeBtn);

    let personalizationEventSource = null;

    if (personalizeBtn) {
        personalizeBtn.addEventListener('click', function() {
            console.log('[App.js] Personalize button clicked - starting personalization');
            // Start personalization
            fetch('/personalize/start', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        showAlert(data.error, 'danger');
                    } else {
                        showAlert('Personalization started for Tier A and B leads!', 'success');
                        personalizeBtn.disabled = true;
                        personalizationProgress.style.display = 'block';

                        // Start SSE connection
                        startPersonalizationUpdates();
                    }
                })
                .catch(error => {
                    showAlert('Error starting personalization: ' + error, 'danger');
                });
        });
    }

    if (stopPersonalizationBtn) {
        stopPersonalizationBtn.addEventListener('click', function() {
            fetch('/personalize/stop', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    showAlert(data.message || 'Stop requested', 'info');
                    stopPersonalizationBtn.disabled = true;
                })
                .catch(error => {
                    showAlert('Error stopping personalization: ' + error, 'danger');
                });
        });
    }

    function startPersonalizationUpdates() {
        // Close existing connection if any
        if (personalizationEventSource) {
            personalizationEventSource.close();
        }

        // Create new SSE connection
        personalizationEventSource = new EventSource('/personalize/status');

        personalizationEventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);

            // Update UI
            personalizationCompleted.textContent = data.completed;
            personalizationFailed.textContent = data.failed;
            personalizationTotal.textContent = data.total;

            // Update progress bar
            if (data.total > 0) {
                const percentage = ((data.completed + data.failed) / data.total * 100).toFixed(0);
                personalizationProgressBar.style.width = percentage + '%';
                personalizationProgressBar.textContent = percentage + '%';
            }

            // Update current lead
            if (data.current_lead) {
                personalizationCurrent.textContent = `Currently generating: ${data.current_lead}`;
            }

            // Check if done
            if (!data.running && data.completed + data.failed >= data.total) {
                personalizationEventSource.close();
                personalizeBtn.disabled = false;
                stopPersonalizationBtn.disabled = false;
                personalizationCurrent.textContent = 'Personalization complete!';
                personalizationProgressBar.classList.remove('progress-bar-animated');

                showAlert(`Personalization complete! Generated: ${data.completed}, Failed: ${data.failed}`, 'success');

                // Reload page after 2 seconds to show updated data
                setTimeout(() => location.reload(), 2000);
            }
        };

        personalizationEventSource.onerror = function(error) {
            console.error('SSE Error:', error);
            personalizationEventSource.close();
            showAlert('Lost connection to server', 'danger');
        };
    }
});

// Global functions for modal and bulk actions
let currentLeadData = null;

function openLeadModal(leadId) {
    const modal = new bootstrap.Modal(document.getElementById('leadModal'));
    const modalBody = document.getElementById('leadModalBody');

    // Show loading
    modalBody.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"></div></div>';

    modal.show();

    // Fetch lead details
    fetch(`/api/lead/${leadId}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                modalBody.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
                return;
            }

            currentLeadData = data;
            renderLeadDetails(data);
        })
        .catch(error => {
            modalBody.innerHTML = `<div class="alert alert-danger">Error loading lead: ${error}</div>`;
        });
}

function renderLeadDetails(lead) {
    const modalBody = document.getElementById('leadModalBody');

    let html = `
        <div class="row">
            <div class="col-md-6">
                <h4>${lead.business_name}</h4>
                <p class="text-muted">${lead.city}, ${lead.state || ''}</p>
            </div>
            <div class="col-md-6 text-end">
                ${lead.tier ? `<span class="badge bg-${getTierColor(lead.tier_override || lead.tier)} fs-5">${lead.tier_override ? 'Tier ' + lead.tier_override + ' (Override)' : 'Tier ' + lead.tier}</span>` : ''}
                ${lead.score !== null ? `<div class="mt-2"><strong>Score:</strong> ${lead.score} points</div>` : ''}
            </div>
        </div>
        <hr>

        <ul class="nav nav-tabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" data-bs-toggle="tab" data-bs-target="#overview">Overview</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#scoring">Score Breakdown</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#enrichment">AI Enrichment</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#review">Review</button>
            </li>
        </ul>

        <div class="tab-content mt-3">
            <!-- Overview Tab -->
            <div class="tab-pane fade show active" id="overview">
                <div class="row">
                    <div class="col-md-6">
                        <h6>Contact Information</h6>
                        <table class="table table-sm">
                            <tr><th>Phone:</th><td>${lead.phone || '-'}</td></tr>
                            <tr><th>Website:</th><td>${lead.website ? `<a href="${lead.website}" target="_blank">${lead.website}</a>` : '-'}</td></tr>
                            <tr><th>Email:</th><td>${lead.owner_email || '-'}</td></tr>
                            <tr><th>Owner:</th><td>${lead.owner_name || '-'}</td></tr>
                        </table>
                    </div>
                    <div class="col-md-6">
                        <h6>Google Places Data</h6>
                        <table class="table table-sm">
                            <tr><th>Rating:</th><td>${lead.rating ? `${lead.rating} ⭐` : '-'}</td></tr>
                            <tr><th>Reviews:</th><td>${lead.review_count || '-'}</td></tr>
                            <tr><th>Place ID:</th><td><small>${lead.place_id || '-'}</small></td></tr>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Scoring Tab -->
            <div class="tab-pane fade" id="scoring">
                ${renderScoreBreakdown(lead)}
            </div>

            <!-- AI Enrichment Tab -->
            <div class="tab-pane fade" id="enrichment">
                ${renderAIEnrichment(lead)}
            </div>

            <!-- Review Tab -->
            <div class="tab-pane fade" id="review">
                ${renderReviewForm(lead)}
            </div>
        </div>
    `;

    modalBody.innerHTML = html;
}

function getTierColor(tier) {
    const colors = {'A': 'success', 'B': 'primary', 'C': 'warning', 'U': 'secondary'};
    return colors[tier] || 'light';
}

function renderScoreBreakdown(lead) {
    if (!lead.score_breakdown || !lead.score_breakdown.signals) {
        return '<p class="text-muted">No scoring data available</p>';
    }

    const breakdown = lead.score_breakdown;
    const positive = breakdown.signals.filter(s => s.points > 0);
    const negative = breakdown.signals.filter(s => s.points < 0);

    let html = `<h6>Total Score: ${breakdown.total} points</h6><hr>`;

    if (positive.length > 0) {
        html += '<h6 class="text-success">Positive Signals (+${positive.reduce((sum, s) => sum + s.points, 0)})</h6><ul class="list-group mb-3">';
        positive.forEach(signal => {
            html += `<li class="list-group-item d-flex justify-content-between">
                <span>${signal.description}</span>
                <span class="badge bg-success">+${signal.points}</span>
            </li>`;
        });
        html += '</ul>';
    }

    if (negative.length > 0) {
        html += `<h6 class="text-danger">Negative Signals (${negative.reduce((sum, s) => sum + s.points, 0)})</h6><ul class="list-group">`;
        negative.forEach(signal => {
            html += `<li class="list-group-item d-flex justify-content-between">
                <span>${signal.description}</span>
                <span class="badge bg-danger">${signal.points}</span>
            </li>`;
        });
        html += '</ul>';
    }

    return html;
}

function renderAIEnrichment(lead) {
    if (lead.gemini_status !== 'enriched') {
        return `<p class="text-muted">AI enrichment status: ${lead.gemini_status || 'pending'}</p>`;
    }

    let html = `
        <div class="row">
            <div class="col-md-6">
                <h6>Business Details</h6>
                <table class="table table-sm">
                    <tr><th>Type:</th><td>${lead.business_type || '-'}</td></tr>
                    <tr><th>Wholesale:</th><td>${lead.is_wholesale ? 'Yes' : 'No'}</td></tr>
                    <tr><th>Retail:</th><td>${lead.is_retail ? 'Yes' : 'No'}</td></tr>
                    <tr><th>Container Production:</th><td>${lead.container_production ? 'Yes' : 'No'}</td></tr>
                    <tr><th>Soil Relevance:</th><td>${lead.soil_relevance ? 'Yes' : 'No'}</td></tr>
                    <tr><th>Organic Focus:</th><td>${lead.organic_focus ? 'Yes' : 'No'}</td></tr>
                </table>
            </div>
            <div class="col-md-6">
                <h6>Size Indicators</h6>
                <table class="table table-sm">
                    <tr><th>Greenhouse:</th><td>${lead.greenhouse_sqft ? lead.greenhouse_sqft + ' sq ft' : '-'}</td></tr>
                    <tr><th>Acreage:</th><td>${lead.acreage || '-'}</td></tr>
                    <tr><th>Multiple Locations:</th><td>${lead.multiple_locations ? 'Yes' : 'No'}</td></tr>
                    <tr><th>Appointment Only:</th><td>${lead.appointment_only ? 'Yes' : 'No'}</td></tr>
                </table>
            </div>
        </div>

        ${lead.crops_grown && lead.crops_grown.length > 0 ? `
            <h6 class="mt-3">Crops Grown</h6>
            <p>${lead.crops_grown.join(', ')}</p>
        ` : ''}

        ${lead.website_text ? `
            <h6 class="mt-3">
                <a data-bs-toggle="collapse" href="#websiteText" role="button">
                    Website Text <i class="bi bi-chevron-down"></i>
                </a>
            </h6>
            <div class="collapse" id="websiteText">
                <div class="card card-body" style="max-height: 300px; overflow-y: auto;">
                    <small>${lead.website_text.substring(0, 2000)}${lead.website_text.length > 2000 ? '...' : ''}</small>
                </div>
            </div>
        ` : ''}
    `;

    return html;
}

function renderReviewForm(lead) {
    return `
        <div class="mb-3">
            <label class="form-label"><strong>Tier Override</strong></label>
            <select class="form-select" id="tierOverride">
                <option value="">Use calculated tier (${lead.tier || 'None'})</option>
                <option value="A" ${lead.tier_override === 'A' ? 'selected' : ''}>Tier A</option>
                <option value="B" ${lead.tier_override === 'B' ? 'selected' : ''}>Tier B</option>
                <option value="C" ${lead.tier_override === 'C' ? 'selected' : ''}>Tier C</option>
                <option value="U" ${lead.tier_override === 'U' ? 'selected' : ''}>Tier U</option>
            </select>
        </div>

        <div class="mb-3">
            <label class="form-label"><strong>Review Notes</strong></label>
            <textarea class="form-control" id="reviewNotes" rows="4">${lead.review_notes || ''}</textarea>
        </div>

        ${lead.reviewed_at ? `
            <p class="text-muted small">
                Last reviewed: ${new Date(lead.reviewed_at).toLocaleString()}
                ${lead.reviewed_by ? ` by ${lead.reviewed_by}` : ''}
            </p>
        ` : ''}
    `;
}

// Bulk actions
function bulkChangeTier(tier) {
    const leadCheckboxes = document.querySelectorAll('.lead-checkbox:checked');
    const leadIds = Array.from(leadCheckboxes).map(cb => parseInt(cb.value));

    if (leadIds.length === 0) {
        alert('No leads selected');
        return;
    }

    if (!confirm(`Change ${leadIds.length} leads to Tier ${tier}?`)) {
        return;
    }

    fetch('/api/bulk/update-tier', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({lead_ids: leadIds, tier: tier})
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert('Error: ' + data.error);
        } else {
            alert(data.message);
            location.reload();
        }
    })
    .catch(error => {
        alert('Error: ' + error.message);
    });
}

function bulkMarkReviewed() {
    const leadCheckboxes = document.querySelectorAll('.lead-checkbox:checked');
    const leadIds = Array.from(leadCheckboxes).map(cb => parseInt(cb.value));

    if (leadIds.length === 0) {
        alert('No leads selected');
        return;
    }

    if (!confirm(`Mark ${leadIds.length} leads as reviewed?`)) {
        return;
    }

    fetch('/api/bulk/mark-reviewed', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({lead_ids: leadIds, reviewed_by: 'user'})
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert('Error: ' + data.error);
        } else {
            alert(data.message);
            location.reload();
        }
    })
    .catch(error => {
        alert('Error: ' + error.message);
    });
}
