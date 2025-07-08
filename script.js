// Global variables
let allWheels = [];
let filteredWheels = [];
let currentView = 'cards';
let currentSource = 'all';
let stats = {};

// DOM elements
const loadingEl = document.getElementById('loading');
const errorEl = document.getElementById('error');
const searchInput = document.getElementById('search');
const clearSearchBtn = document.getElementById('clear-search');
const sourceFilter = document.getElementById('source-filter');
const pythonFilter = document.getElementById('python-filter');
const platformFilter = document.getElementById('platform-filter');
const tabButtons = document.querySelectorAll('.tab-button');
const viewToggleCards = document.getElementById('view-cards');
const viewToggleTable = document.getElementById('view-table');
const resultsCount = document.getElementById('results-count');
const resultsCards = document.getElementById('results-cards');
const resultsTable = document.getElementById('results-table');

// Initialize the application
document.addEventListener('DOMContentLoaded', function () {
    loadData();
    setupEventListeners();
});

// Load data from JSON files
async function loadData() {
    try {
        showLoading();

        // Load wheels data
        const wheelsResponse = await fetch('data/wheels.json');
        if (!wheelsResponse.ok) {
            throw new Error(`Failed to load wheels data: ${wheelsResponse.status}`);
        }
        const wheelsData = await wheelsResponse.json();

        // Load stats data
        const statsResponse = await fetch('data/stats.json');
        if (!statsResponse.ok) {
            throw new Error(`Failed to load stats data: ${statsResponse.status}`);
        }
        stats = await statsResponse.json();

        // Process wheels data
        processWheelsData(wheelsData);

        // Update UI
        updateStats();
        populateFilters();
        filterAndDisplay();

        hideLoading();
    } catch (error) {
        showError(`Error loading data: ${error.message}`);
    }
}

// Process wheels data into flat array
function processWheelsData(data) {
    allWheels = [];

    for (const [sourceKey, files] of Object.entries(data.results || {})) {
        for (const file of files) {
            if (file.type !== 'wheel') continue;

            let sourceType = 'commit';
            let sourceInfo = sourceKey;
            let installCommand = `uv pip install vllm --extra-index-url https://wheels.vllm.ai/${sourceKey} --torch-backend auto`;

            if (sourceKey.startsWith('release_')) {
                sourceType = 'github_release';
                sourceInfo = sourceKey.replace('release_', '');
                installCommand = `uv pip install ${file.url} --torch-backend auto`;
            } else if (sourceKey.startsWith('version_')) {
                sourceType = 'release_version';
                sourceInfo = sourceKey.replace('version_', '');
                installCommand = `uv pip install -U vllm==${sourceInfo} --extra-index-url https://wheels.vllm.ai/${sourceInfo} --torch-backend auto`;
            } else if (sourceKey === 'nightly') {
                sourceType = 'nightly';
                sourceInfo = 'nightly';
                installCommand = 'uv pip install vllm --extra-index-url https://wheels.vllm.ai/nightly --torch-backend auto';
            }

            allWheels.push({
                ...file,
                sourceType,
                sourceInfo,
                installCommand
            });
        }
    }
}

// Update statistics display
function updateStats() {
    document.getElementById('total-wheels').textContent = stats.total_wheels || 0;
    document.getElementById('total-sources').textContent = stats.total_sources || 0;

    const lastUpdated = new Date(stats.last_updated || Date.now());
    document.getElementById('last-updated').textContent = formatDate(lastUpdated);
}

// Populate filter dropdowns
function populateFilters() {
    const pythonVersions = new Set();
    const platforms = new Set();

    allWheels.forEach(wheel => {
        if (wheel.python_tag) pythonVersions.add(wheel.python_tag);
        if (wheel.platform_tag) platforms.add(wheel.platform_tag);
    });

    populateSelect(pythonFilter, Array.from(pythonVersions).sort());
    populateSelect(platformFilter, Array.from(platforms).sort());
}

// Helper function to populate select elements
function populateSelect(selectElement, options) {
    // Clear existing options (except the first one)
    while (selectElement.children.length > 1) {
        selectElement.removeChild(selectElement.lastChild);
    }

    options.forEach(option => {
        const optionElement = document.createElement('option');
        optionElement.value = option;
        optionElement.textContent = option;
        selectElement.appendChild(optionElement);
    });
}

// Setup event listeners
function setupEventListeners() {
    // Search
    searchInput.addEventListener('input', debounce(filterAndDisplay, 300));
    clearSearchBtn.addEventListener('click', clearSearch);

    // Filters
    sourceFilter.addEventListener('change', filterAndDisplay);
    pythonFilter.addEventListener('change', filterAndDisplay);
    platformFilter.addEventListener('change', filterAndDisplay);

    // Source tabs
    tabButtons.forEach(button => {
        button.addEventListener('click', function () {
            setActiveTab(this.dataset.source);
        });
    });

    // View toggles
    viewToggleCards.addEventListener('click', () => setView('cards'));
    viewToggleTable.addEventListener('click', () => setView('table'));

    // Copy to clipboard functionality
    document.addEventListener('click', function (e) {
        if (e.target.classList.contains('install-command')) {
            copyToClipboard(e.target.textContent);
        }
    });
}

// Filter and display results
function filterAndDisplay() {
    const searchTerm = searchInput.value.toLowerCase();
    const sourceFilterValue = sourceFilter.value;
    const pythonFilterValue = pythonFilter.value;
    const platformFilterValue = platformFilter.value;

    filteredWheels = allWheels.filter(wheel => {
        // Text search
        if (searchTerm && !searchMatches(wheel, searchTerm)) {
            return false;
        }

        // Source filter
        if (currentSource !== 'all' && wheel.sourceType !== currentSource) {
            return false;
        }

        // Additional filters
        if (sourceFilterValue && wheel.sourceType !== sourceFilterValue) {
            return false;
        }

        if (pythonFilterValue && wheel.python_tag !== pythonFilterValue) {
            return false;
        }

        if (platformFilterValue && wheel.platform_tag !== platformFilterValue) {
            return false;
        }

        return true;
    });

    displayResults();
}

// Check if wheel matches search term
function searchMatches(wheel, searchTerm) {
    const searchFields = [
        wheel.filename,
        wheel.version,
        wheel.sourceInfo,
        wheel.python_tag,
        wheel.platform_tag,
        wheel.commit,
        wheel.release_tag
    ];

    return searchFields.some(field =>
        field && field.toLowerCase().includes(searchTerm)
    );
}

// Display results in current view
function displayResults() {
    resultsCount.textContent = `${filteredWheels.length} wheels found`;

    if (currentView === 'cards') {
        displayCardsView();
    } else {
        displayTableView();
    }
}

// Display cards view
function displayCardsView() {
    resultsCards.innerHTML = '';

    if (filteredWheels.length === 0) {
        resultsCards.innerHTML = '<div style="text-align: center; padding: 40px; color: #7f8c8d;">No wheels found matching your criteria.</div>';
        return;
    }

    filteredWheels.forEach(wheel => {
        const card = createWheelCard(wheel);
        resultsCards.appendChild(card);
    });
}

// Create wheel card element
function createWheelCard(wheel) {
    const card = document.createElement('div');
    card.className = 'wheel-card';

    card.innerHTML = `
        <div class="wheel-header">
            <div class="wheel-filename">${escapeHtml(wheel.filename)}</div>
            <div class="source-badge ${wheel.sourceType}">${getSourceLabel(wheel.sourceType)}</div>
        </div>
        
        <div class="wheel-meta">
            <div class="meta-item">
                <div class="meta-label">Version</div>
                <div class="meta-value">${escapeHtml(wheel.version || 'N/A')}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Python</div>
                <div class="meta-value">${escapeHtml(wheel.python_tag || 'N/A')}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Platform</div>
                <div class="meta-value">${escapeHtml(wheel.platform_tag || 'N/A')}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Source</div>
                <div class="meta-value">${escapeHtml(wheel.sourceInfo || 'N/A')}</div>
            </div>
        </div>
        
        <div class="install-command" title="Click to copy">
            ${escapeHtml(wheel.installCommand)}
        </div>
    `;

    return card;
}

// Display table view
function displayTableView() {
    if (filteredWheels.length === 0) {
        resultsTable.innerHTML = '<div style="text-align: center; padding: 40px; color: #7f8c8d;">No wheels found matching your criteria.</div>';
        return;
    }

    const table = document.createElement('table');
    table.innerHTML = `
        <thead>
            <tr>
                <th>Filename</th>
                <th>Source</th>
                <th>Version</th>
                <th>Python</th>
                <th>Platform</th>
                <th>Install Command</th>
            </tr>
        </thead>
        <tbody>
            ${filteredWheels.map(wheel => `
                <tr>
                    <td class="filename">${escapeHtml(wheel.filename)}</td>
                    <td><span class="source-badge ${wheel.sourceType}">${getSourceLabel(wheel.sourceType)}</span></td>
                    <td>${escapeHtml(wheel.version || 'N/A')}</td>
                    <td>${escapeHtml(wheel.python_tag || 'N/A')}</td>
                    <td>${escapeHtml(wheel.platform_tag || 'N/A')}</td>
                    <td class="install-command" title="Click to copy">${escapeHtml(wheel.installCommand)}</td>
                </tr>
            `).join('')}
        </tbody>
    `;

    resultsTable.innerHTML = '';
    resultsTable.appendChild(table);
}

// Set active tab
function setActiveTab(source) {
    currentSource = source;

    // Update tab buttons
    tabButtons.forEach(button => {
        button.classList.toggle('active', button.dataset.source === source);
    });

    filterAndDisplay();
}

// Set view mode
function setView(view) {
    currentView = view;

    // Update toggle buttons
    viewToggleCards.classList.toggle('active', view === 'cards');
    viewToggleTable.classList.toggle('active', view === 'table');

    // Show/hide views
    resultsCards.style.display = view === 'cards' ? 'grid' : 'none';
    resultsTable.style.display = view === 'table' ? 'block' : 'none';

    displayResults();
}

// Clear search
function clearSearch() {
    searchInput.value = '';
    filterAndDisplay();
}

// Copy to clipboard functionality
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showTooltip('Copied to clipboard!');
    } catch (err) {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        showTooltip('Copied to clipboard!');
    }
}

// Show tooltip
function showTooltip(message) {
    // Create temporary tooltip
    const tooltip = document.createElement('div');
    tooltip.textContent = message;
    tooltip.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: #2c3e50;
        color: white;
        padding: 10px 20px;
        border-radius: 4px;
        z-index: 1000;
        font-size: 14px;
    `;
    document.body.appendChild(tooltip);

    setTimeout(() => {
        document.body.removeChild(tooltip);
    }, 2000);
}

// Utility functions
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getSourceLabel(sourceType) {
    const labels = {
        commit: 'Commit',
        github_release: 'Release',
        release_version: 'Version',
        nightly: 'Nightly'
    };
    return labels[sourceType] || sourceType;
}

function formatDate(date) {
    return new Intl.DateTimeFormat('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    }).format(date);
}

function showLoading() {
    loadingEl.style.display = 'block';
    errorEl.style.display = 'none';
}

function hideLoading() {
    loadingEl.style.display = 'none';
}

function showError(message) {
    errorEl.textContent = message;
    errorEl.style.display = 'block';
    loadingEl.style.display = 'none';
} 