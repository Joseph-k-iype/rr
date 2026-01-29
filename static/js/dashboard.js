// dashboard.js - Compliance Dashboard JavaScript

const API_BASE = 'http://localhost:5000/api';

let allTransfers = [];
let filteredTransfers = [];
let charts = {};

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    loadDashboardData();
    setupEventListeners();
});

// Setup event listeners
function setupEventListeners() {
    document.getElementById('refreshBtn').addEventListener('click', loadDashboardData);
    document.getElementById('complianceFilter').addEventListener('change', applyFilters);
    document.getElementById('ruleFilter').addEventListener('change', applyFilters);
    document.getElementById('searchBox').addEventListener('input', applyFilters);
    document.getElementById('clearFilters').addEventListener('click', clearFilters);
    document.getElementById('exportBtn').addEventListener('click', exportToCSV);

    // Compliance checker event listeners
    document.getElementById('checkComplianceBtn').addEventListener('click', checkCompliance);
    document.getElementById('findSimilarBtn').addEventListener('click', findSimilarCases);
    document.getElementById('clearFormBtn').addEventListener('click', clearForm);
}

// Load all dashboard data
async function loadDashboardData() {
    showLoading(true);

    try {
        // Fetch data from API
        const [transfersRes, summaryRes, ruleComplianceRes] = await Promise.all([
            fetch(`${API_BASE}/transfers`),
            fetch(`${API_BASE}/summary`),
            fetch(`${API_BASE}/compliance-by-rule`)
        ]);

        const transfersData = await transfersRes.json();
        const summaryData = await summaryRes.json();
        const ruleComplianceData = await ruleComplianceRes.json();

        if (transfersData.success) {
            allTransfers = transfersData.data;
            filteredTransfers = [...allTransfers];

            // Update UI
            updateSummaryCards(summaryData.data);
            renderCharts(summaryData.data, ruleComplianceData.data);
            renderTable(filteredTransfers);
            updateLastUpdated();
        } else {
            showError('Failed to load transfers data');
        }
    } catch (error) {
        console.error('Error loading dashboard data:', error);
        showError('Error connecting to server. Please ensure the backend is running.');
    } finally {
        showLoading(false);
    }
}

// Update summary cards
function updateSummaryCards(summary) {
    document.getElementById('totalTransfers').textContent = summary.total_transfers.toLocaleString();
    document.getElementById('compliantCount').textContent = summary.compliant.toLocaleString();
    document.getElementById('nonCompliantCount').textContent = summary.non_compliant.toLocaleString();
    document.getElementById('complianceRate').textContent = `${summary.compliance_rate}%`;
}

// Render charts
function renderCharts(summary, ruleCompliance) {
    renderComplianceChart(summary);
    renderMissingModulesChart(summary);
    renderRuleComplianceChart(ruleCompliance);
}

// Compliance Overview Chart
function renderComplianceChart(summary) {
    const ctx = document.getElementById('complianceChart').getContext('2d');

    if (charts.compliance) {
        charts.compliance.destroy();
    }

    charts.compliance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Compliant', 'Non-Compliant'],
            datasets: [{
                data: [summary.compliant, summary.non_compliant],
                backgroundColor: ['#10b981', '#ef4444'],
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 15,
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: (context) => {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${label}: ${value.toLocaleString()} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

// Missing Modules Chart
function renderMissingModulesChart(summary) {
    const ctx = document.getElementById('missingModulesChart').getContext('2d');

    if (charts.missingModules) {
        charts.missingModules.destroy();
    }

    charts.missingModules = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['PIA', 'TIA', 'HRPR'],
            datasets: [{
                label: 'Missing CM Assessments',
                data: [
                    summary.missing_modules.PIA,
                    summary.missing_modules.TIA,
                    summary.missing_modules.HRPR
                ],
                backgroundColor: ['#ef4444', '#f59e0b', '#ec4899'],
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (context) => `${context.parsed.y.toLocaleString()} cases missing`
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { precision: 0 }
                }
            }
        }
    });
}

// Rule Compliance Chart
function renderRuleComplianceChart(ruleCompliance) {
    const ctx = document.getElementById('ruleComplianceChart').getContext('2d');

    if (charts.ruleCompliance) {
        charts.ruleCompliance.destroy();
    }

    const rules = Object.keys(ruleCompliance).sort();
    const compliantData = rules.map(rule => ruleCompliance[rule].compliant);
    const nonCompliantData = rules.map(rule => ruleCompliance[rule].non_compliant);

    charts.ruleCompliance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: rules,
            datasets: [
                {
                    label: 'Compliant',
                    data: compliantData,
                    backgroundColor: '#10b981',
                    borderRadius: 6
                },
                {
                    label: 'Non-Compliant',
                    data: nonCompliantData,
                    backgroundColor: '#ef4444',
                    borderRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { padding: 15 }
                },
                tooltip: {
                    callbacks: {
                        title: (context) => {
                            const rule = context[0].label;
                            return ruleCompliance[rule].explanation;
                        },
                        label: (context) => {
                            return `${context.dataset.label}: ${context.parsed.y.toLocaleString()}`;
                        }
                    }
                }
            },
            scales: {
                x: { stacked: true },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    ticks: { precision: 0 }
                }
            }
        }
    });
}

// Render data table
function renderTable(transfers) {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '';

    if (transfers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; padding: 30px;">No transfers found</td></tr>';
        document.getElementById('filteredCount').textContent = '0';
        return;
    }

    transfers.forEach(transfer => {
        const row = document.createElement('tr');

        const compliance = transfer.compliance;
        const statusClass = compliance.compliant ? 'status-compliant' : 'status-non-compliant';
        const statusText = compliance.compliant ? '✓ Compliant' : '✗ Non-Compliant';

        const personalDataText = transfer.personal_data.length > 0
            ? transfer.personal_data.slice(0, 3).join(', ') + (transfer.personal_data.length > 3 ? '...' : '')
            : 'None';

        const missingText = compliance.missing_modules.length > 0
            ? compliance.missing_modules.join(', ')
            : '-';

        row.innerHTML = `
            <td><strong>${transfer.case_id}</strong></td>
            <td>${transfer.origin_country}</td>
            <td>${transfer.destination_country}</td>
            <td class="personal-data-list" title="${transfer.personal_data.join(', ')}">${personalDataText}</td>
            <td><span class="module-badge ${transfer.pia_module === 'CM' ? 'module-cm' : 'module-not-cm'}">${transfer.pia_module || 'N/A'}</span></td>
            <td><span class="module-badge ${transfer.tia_module === 'CM' ? 'module-cm' : 'module-not-cm'}">${transfer.tia_module || 'N/A'}</span></td>
            <td><span class="module-badge ${transfer.hrpr_module === 'CM' ? 'module-cm' : 'module-not-cm'}">${transfer.hrpr_module || 'N/A'}</span></td>
            <td><small>${compliance.rule_matched || 'N/A'}</small></td>
            <td><span class="status-badge ${statusClass}">${statusText}</span></td>
            <td><small>${missingText}</small></td>
        `;

        // Highlight non-compliant rows
        if (!compliance.compliant) {
            row.style.backgroundColor = '#fef2f2';
        }

        tbody.appendChild(row);
    });

    document.getElementById('filteredCount').textContent = transfers.length.toLocaleString();
}

// Apply filters
function applyFilters() {
    const complianceFilter = document.getElementById('complianceFilter').value;
    const ruleFilter = document.getElementById('ruleFilter').value;
    const searchText = document.getElementById('searchBox').value.toLowerCase();

    filteredTransfers = allTransfers.filter(transfer => {
        // Compliance filter
        if (complianceFilter === 'compliant' && !transfer.compliance.compliant) return false;
        if (complianceFilter === 'non-compliant' && transfer.compliance.compliant) return false;

        // Rule filter
        if (ruleFilter !== 'all' && transfer.compliance.rule_matched !== ruleFilter) return false;

        // Search filter
        if (searchText) {
            const searchableText = [
                transfer.case_id,
                transfer.origin_country,
                transfer.destination_country,
                transfer.eim_id,
                transfer.business_app_id,
                ...transfer.personal_data
            ].join(' ').toLowerCase();

            if (!searchableText.includes(searchText)) return false;
        }

        return true;
    });

    renderTable(filteredTransfers);
}

// Clear filters
function clearFilters() {
    document.getElementById('complianceFilter').value = 'all';
    document.getElementById('ruleFilter').value = 'all';
    document.getElementById('searchBox').value = '';
    filteredTransfers = [...allTransfers];
    renderTable(filteredTransfers);
}

// Export to CSV
function exportToCSV() {
    const headers = [
        'Case ID', 'Origin Country', 'Destination Country', 'Personal Data',
        'PIA Module', 'TIA Module', 'HRPR Module', 'EIM ID', 'Business App ID',
        'Rule Matched', 'Compliant', 'Missing Modules', 'Explanation'
    ];

    const rows = filteredTransfers.map(t => [
        t.case_id,
        t.origin_country,
        t.destination_country,
        t.personal_data.join('; '),
        t.pia_module || '',
        t.tia_module || '',
        t.hrpr_module || '',
        t.eim_id || '',
        t.business_app_id || '',
        t.compliance.rule_matched || '',
        t.compliance.compliant ? 'Yes' : 'No',
        t.compliance.missing_modules.join('; '),
        t.compliance.explanation
    ]);

    let csvContent = headers.join(',') + '\n';
    rows.forEach(row => {
        csvContent += row.map(cell => `"${cell}"`).join(',') + '\n';
    });

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `compliance_report_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
}

// Show/hide loading indicator
function showLoading(show) {
    const loading = document.getElementById('loadingIndicator');
    if (show) {
        loading.classList.add('active');
    } else {
        loading.classList.remove('active');
    }
}

// Show error message
function showError(message) {
    alert(message);
}

// Update last updated timestamp
function updateLastUpdated() {
    const now = new Date();
    const formatted = now.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    document.getElementById('lastUpdated').textContent = formatted;
}