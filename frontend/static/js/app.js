class TwitterScreenshotApp {
    constructor() {
        this.initializeElements();
        this.bindEvents();
        this.updateWidthDisplay();
    }

    initializeElements() {
        this.urlsTextarea = document.getElementById('urls');
        this.widthInput = document.getElementById('width-input');
        this.widthSlider = document.getElementById('width-slider');
        this.presetBtns = document.querySelectorAll('.preset-btn');
        this.borderRadiusSlider = document.getElementById('border-radius');
        this.borderRadiusValue = document.getElementById('border-radius-value');
        this.captureBtn = document.getElementById('capture-btn');
        this.clearBtn = document.getElementById('clear-btn');
        this.resultsContainer = document.getElementById('results');
        this.resultsStats = document.getElementById('results-stats');
        this.successCount = document.getElementById('success-count');
        this.failedCount = document.getElementById('failed-count');
        this.totalCount = document.getElementById('total-count');
    }

    bindEvents() {
        // Width controls
        this.widthInput.addEventListener('input', (e) => {
            this.widthSlider.value = e.target.value;
            this.updatePresetButtons();
        });

        this.widthSlider.addEventListener('input', (e) => {
            this.widthInput.value = e.target.value;
            this.updatePresetButtons();
        });

        // Preset buttons
        this.presetBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const width = e.target.dataset.width;
                this.widthInput.value = width;
                this.widthSlider.value = width;
                this.updatePresetButtons();
            });
        });

        // Border radius
        this.borderRadiusSlider.addEventListener('input', (e) => {
            this.borderRadiusValue.textContent = e.target.value + 'px';
        });

        // Buttons
        this.captureBtn.addEventListener('click', () => this.captureScreenshots());
        this.clearBtn.addEventListener('click', () => this.clearAll());
    }

    updatePresetButtons() {
        const currentWidth = parseInt(this.widthInput.value);
        this.presetBtns.forEach(btn => {
            btn.classList.toggle('active', parseInt(btn.dataset.width) === currentWidth);
        });
    }

    updateWidthDisplay() {
        this.updatePresetButtons();
        this.borderRadiusValue.textContent = this.borderRadiusSlider.value + 'px';
    }

    async captureScreenshots() {
        const text = this.urlsTextarea.value.trim();
        if (!text) {
            alert('Please enter tweet URLs or embed HTML code.');
            return;
        }

        const urls = text.split('\n').map(url => url.trim()).filter(url => url.length > 0);

        // This matches the exact API format expected
        const requestData = {
            urls: urls,
            options: {
                width: parseInt(this.widthInput.value),
                format: document.querySelector('input[name="format"]:checked').value,
                theme: document.querySelector('input[name="theme"]:checked').value,
                background: document.getElementById('background').value,
                border_radius: parseInt(this.borderRadiusSlider.value),
                include_metadata: document.getElementById('include-metadata').checked
            }
        };

        console.log('Sending request:', requestData);

        this.setLoadingState(true);
        this.clearResults();

        try {
            const response = await fetch('/api/screenshot/bulk', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });

            console.log('Response status:', response.status);

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Error response:', errorText);
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            const data = await response.json();
            console.log('Success response:', data);
            this.displayResults(data.results);

        } catch (error) {
            console.error('Request failed:', error);
            this.showError('Failed to capture screenshots: ' + error.message);
        } finally {
            this.setLoadingState(false);
        }
    }

    setLoadingState(isLoading) {
        const btnText = this.captureBtn.querySelector('.btn-text');
        const spinner = this.captureBtn.querySelector('.spinner');

        if (isLoading) {
            btnText.textContent = 'Processing...';
            spinner.style.display = 'block';
            this.captureBtn.disabled = true;
        } else {
            btnText.textContent = '📸 Capture Screenshots';
            spinner.style.display = 'none';
            this.captureBtn.disabled = false;
        }
    }

    clearResults() {
        this.resultsContainer.innerHTML = '';
        this.resultsStats.style.display = 'none';
    }

    displayResults(results) {
        if (!results || results.length === 0) return;

        const successful = results.filter(r => r.success).length;
        const failed = results.length - successful;

        this.successCount.textContent = successful;
        this.failedCount.textContent = failed;
        this.totalCount.textContent = results.length;
        this.resultsStats.style.display = 'flex';

        results.forEach((result) => {
            const resultElement = this.createResultElement(result);
            this.resultsContainer.appendChild(resultElement);
        });
    }

    createResultElement(result) {
        const div = document.createElement('div');
        div.className = `result-item ${result.success ? 'success' : 'error'}`;

        if (result.success) {
            div.innerHTML = `
                <div class="result-header">
                    <span class="result-status success">✅ Success</span>
                </div>
                <div class="result-image">
                    <img src="data:image/${result.filename.includes('.png') ? 'png' : 'jpeg'};base64,${result.image_base64}" 
                         alt="Screenshot" style="max-width: 100%; border-radius: 8px;">
                </div>
                <div class="result-actions">
                    <a href="data:image/${result.filename.includes('.png') ? 'png' : 'jpeg'};base64,${result.image_base64}" 
                       download="${result.filename}" 
                       class="action-btn">💾 Download</a>
                </div>
            `;
        } else {
            div.innerHTML = `
                <div class="result-header">
                    <span class="result-status error">❌ Failed</span>
                </div>
                <div class="error-message">${result.error || 'Unknown error'}</div>
            `;
        }

        return div;
    }

    showError(message) {
        this.resultsContainer.innerHTML = `<div class="result-item error"><div class="error-message">${message}</div></div>`;
    }

    clearAll() {
        this.urlsTextarea.value = '';
        this.clearResults();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.app = new TwitterScreenshotApp();
});