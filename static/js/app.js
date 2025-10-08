let allMaps = [];
let currentFilter = 'all';
let mapPrefixes = new Set();

// Common TF2 map prefixes with descriptions
const prefixDescriptions = {
    'cp_': 'Control Point',
    'ctf_': 'Capture the Flag',
    'pl_': 'Payload',
    'plr_': 'Payload Race',
    'koth_': 'King of the Hill',
    'mvm_': 'Mann vs Machine',
    'sd_': 'Special Delivery',
    'rd_': 'Robot Destruction',
    'pd_': 'Player Destruction',
    'arena_': 'Arena',
    'pass_': 'PASS Time',
    'tc_': 'Territorial Control',
    'tr_': 'Training',
    'surf_': 'Surf',
    'jump_': 'Jump',
    'dm_': 'Deathmatch',
    'trade_': 'Trade',
    'achievement_': 'Achievement',
    'mge_': 'MGE Training'
};

// Load maps on page load
document.addEventListener('DOMContentLoaded', function() {
    loadMaps();
    
    // Handle form submission
    document.getElementById('uploadForm').addEventListener('submit', handleUpload);
});

async function handleUpload(e) {
    e.preventDefault();
    
    const fileInput = document.getElementById('fileInput');
    const files = Array.from(fileInput.files);
    
    if (files.length === 0) {
        showMessage('Please select at least one file', 'error');
        return;
    }
    
    // Validate all files first
    const validFiles = [];
    for (const file of files) {
        const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
        if (!['.bsp', '.bz2'].includes(fileExt)) {
            showMessage(`Skipping ${file.name}: Invalid file type`, 'warning');
            continue;
        }
        if (file.size > 200 * 1024 * 1024) {
            showMessage(`Skipping ${file.name}: File too large (max 200MB)`, 'warning');
            continue;
        }
        validFiles.push(file);
    }
    
    if (validFiles.length === 0) {
        showMessage('No valid files to upload', 'error');
        return;
    }
    
    const progressBar = document.getElementById('progressBar');
    const progressFill = document.getElementById('progressFill');
    const uploadProgress = document.getElementById('uploadProgress');
    const uploadResults = document.getElementById('uploadResults');
    
    progressBar.style.display = 'block';
    uploadResults.innerHTML = '';
    uploadResults.style.display = 'block';
    
    let uploaded = 0;
    let skipped = 0;
    let failed = 0;
    
    for (let i = 0; i < validFiles.length; i++) {
        const file = validFiles[i];
        uploadProgress.textContent = `Uploading ${i + 1} of ${validFiles.length}: ${file.name}`;
        
        try {
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (response.ok) {
                if (result.status === 'skipped') {
                    skipped++;
                    addUploadResult(file.name, 'skipped', result.message);
                } else {
                    uploaded++;
                    addUploadResult(file.name, 'success', result.message);
                }
            } else {
                failed++;
                addUploadResult(file.name, 'failed', result.detail || 'Upload failed');
            }
        } catch (error) {
            failed++;
            addUploadResult(file.name, 'failed', error.message);
        }
        
        // Update progress bar
        const percentComplete = ((i + 1) / validFiles.length) * 100;
        progressFill.style.width = percentComplete + '%';
    }
    
    // Show summary
    let summaryMsg = `Completed: ${uploaded} uploaded`;
    if (skipped > 0) summaryMsg += `, ${skipped} skipped (already exist)`;
    if (failed > 0) summaryMsg += `, ${failed} failed`;
    
    showMessage(summaryMsg, uploaded > 0 ? 'success' : 'warning');
    
    // Reset
    fileInput.value = '';
    progressBar.style.display = 'none';
    progressFill.style.width = '0%';
    uploadProgress.textContent = '';
    
    // Reload maps list
    loadMaps();
}

function addUploadResult(filename, status, message) {
    const uploadResults = document.getElementById('uploadResults');
    const resultItem = document.createElement('div');
    resultItem.className = `upload-result-item upload-${status}`;
    resultItem.textContent = `${filename}: ${message}`;
    uploadResults.appendChild(resultItem);
}

async function loadMaps() {
    try {
        const response = await fetch('/maps');
        allMaps = await response.json();
        
        // Extract unique prefixes
        mapPrefixes.clear();
        allMaps.forEach(map => {
            const prefix = extractMapPrefix(map.name);
            if (prefix) {
                mapPrefixes.add(prefix);
            }
        });
        
        // Create filter buttons
        createFilterButtons();
        
        // Display maps
        displayMaps();
        
    } catch (error) {
        showMessage('Failed to load maps: ' + error.message, 'error');
    }
}

function extractMapPrefix(mapName) {
    const match = mapName.match(/^([a-zA-Z]+_)/);
    return match ? match[1] : null;
}

function createFilterButtons() {
    const filterButtons = document.getElementById('filterButtons');
    filterButtons.innerHTML = '<button class="filter-btn active" data-filter="all">All Maps</button>';
    
    // Sort prefixes and create buttons
    const sortedPrefixes = Array.from(mapPrefixes).sort();
    sortedPrefixes.forEach(prefix => {
        const btn = document.createElement('button');
        btn.className = 'filter-btn';
        btn.dataset.filter = prefix;
        
        const description = prefixDescriptions[prefix] || prefix.replace('_', '').toUpperCase();
        const count = allMaps.filter(m => m.name.startsWith(prefix)).length;
        btn.textContent = `${description} (${count})`;
        
        btn.addEventListener('click', () => {
            // Update active button
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // Apply filter
            currentFilter = prefix;
            displayMaps();
        });
        
        filterButtons.appendChild(btn);
    });
    
    // All maps button handler
    document.querySelector('[data-filter="all"]').addEventListener('click', () => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        document.querySelector('[data-filter="all"]').classList.add('active');
        currentFilter = 'all';
        displayMaps();
    });
}

function displayMaps() {
    const mapsList = document.getElementById('mapsList');
    const mapCount = document.getElementById('mapCount');
    const filteredCount = document.getElementById('filteredCount');
    
    // Filter maps
    let filteredMaps = allMaps;
    if (currentFilter !== 'all') {
        filteredMaps = allMaps.filter(map => map.name.startsWith(currentFilter));
    }
    
    mapCount.textContent = allMaps.length;
    filteredCount.textContent = filteredMaps.length;
    mapsList.innerHTML = '';
    
    if (filteredMaps.length === 0) {
        mapsList.innerHTML = '<p style="text-align: center; color: #666;">No maps found</p>';
        return;
    }
    
    filteredMaps.forEach(map => {
        const mapItem = document.createElement('div');
        mapItem.className = 'map-item';
        
        const prefix = extractMapPrefix(map.name);
        const prefixBadge = prefix ? 
            `<span class="map-type">${prefixDescriptions[prefix] || prefix.replace('_', '')}</span>` : '';
        
        // Generate checkboxes for each mapcycle
        const mapcycleCheckboxes = Object.entries(map.mapcycles)
            .map(([mapcycleName, isEnabled]) => `
                <label class="mapcycle-checkbox">
                    <input type="checkbox" ${isEnabled ? 'checked' : ''} 
                           onchange="toggleMapcycle('${map.name}', '${mapcycleName}', this)">
                    <span class="checkmark"></span>
                    ${mapcycleName}
                </label>
            `).join('');

        mapItem.innerHTML = `
            <div class="map-info">
                <div class="map-main-info">
                    <span class="map-name">${map.name}</span>
                    ${prefixBadge}
                    <span class="map-size">(${formatFileSize(map.size)})</span>
                </div>
            </div>
            <div class="map-controls">
                <div class="mapcycle-checkboxes">
                    ${mapcycleCheckboxes}
                </div>
                <div class="map-actions">
                    <span style="color: #666;">${new Date(map.modified).toLocaleString()}</span>
                    <button class="delete-btn" onclick="deleteMap('${map.name}')" title="Delete map">🗑️</button>
                </div>
            </div>
        `;
        mapsList.appendChild(mapItem);
    });
}

function showMessage(text, type) {
    const messageDiv = document.getElementById('message');
    messageDiv.textContent = text;
    messageDiv.className = 'message ' + type;
    setTimeout(() => {
        messageDiv.textContent = '';
        messageDiv.className = '';
    }, 5000);
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

async function toggleMapcycle(filename, mapcycleName, checkbox) {
    try {
        const response = await fetch(`/maps/${encodeURIComponent(filename)}/mapcycle?name=${encodeURIComponent(mapcycleName)}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (response.ok) {
            // Update the checkbox state to match server response
            checkbox.checked = result.in_mapcycle;
            showMessage(result.message, 'success');
        } else {
            // Revert checkbox on error
            checkbox.checked = !checkbox.checked;
            showMessage(result.detail || 'Failed to toggle mapcycle', 'error');
        }
    } catch (error) {
        // Revert checkbox on error
        checkbox.checked = !checkbox.checked;
        showMessage('Failed to toggle mapcycle: ' + error.message, 'error');
    }
}

async function deleteMap(filename) {
    if (!confirm(`Are you sure you want to delete "${filename}"? This action cannot be undone.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/maps/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showMessage(result.message, 'success');
            // Reload maps list to reflect the deletion
            loadMaps();
        } else {
            showMessage(result.detail || 'Failed to delete map', 'error');
        }
    } catch (error) {
        showMessage('Failed to delete map: ' + error.message, 'error');
    }
}