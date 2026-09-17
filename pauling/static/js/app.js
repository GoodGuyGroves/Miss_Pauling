// Minimal JavaScript for dynamic functionality

// Toggle Steam details visibility
function toggleSteamDetails() {
    const details = document.getElementById('steam-details');
    const toggle = document.getElementById('steam-details-toggle');
    
    if (details && toggle) {
        if (details.style.display === 'none') {
            details.style.display = 'block';
            toggle.textContent = 'Hide details';
        } else {
            details.style.display = 'none';
            toggle.textContent = 'Show details';
        }
    }
}

// Copy text to clipboard
function copyToClipboard(text, field) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            const button = document.getElementById('copy-' + field);
            if (button) {
                const originalText = button.textContent;
                button.textContent = '✓';
                button.style.backgroundColor = '#10b981';
                button.style.color = 'white';
                
                setTimeout(() => {
                    button.textContent = originalText;
                    button.style.backgroundColor = '';
                    button.style.color = '';
                }, 2000);
            }
        }).catch(err => {
            console.error('Could not copy text: ', err);
            showMessage('Failed to copy to clipboard', 'error');
        });
    } else {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            document.execCommand('copy');
            const button = document.getElementById('copy-' + field);
            if (button) {
                const originalText = button.textContent;
                button.textContent = '✓';
                setTimeout(() => {
                    button.textContent = originalText;
                }, 2000);
            }
        } catch (err) {
            console.error('Fallback copy failed: ', err);
            showMessage('Failed to copy to clipboard', 'error');
        }
        
        document.body.removeChild(textArea);
    }
}

// Confirm unlink action
function confirmUnlink(provider) {
    if (provider === 'steam') {
        return confirm('Are you sure you want to unlink your Steam account?');
    }
    return confirm(`Are you sure you want to unlink your ${provider} account?`);
}

// Show temporary messages
function showMessage(text, type = 'info') {
    const container = document.getElementById('message-container');
    if (!container) return;
    
    const messageDiv = document.createElement('div');
    const className = type === 'error' ? 
        'mb-3 rounded border border-red-400 bg-red-100 px-3 py-2 text-sm text-red-700' :
        'mb-3 rounded border border-green-400 bg-green-100 px-3 py-2 text-sm text-green-700';
    
    messageDiv.className = className;
    messageDiv.textContent = text;
    
    container.appendChild(messageDiv);
    
    // Remove after 3 seconds
    setTimeout(() => {
        if (messageDiv.parentNode) {
            messageDiv.parentNode.removeChild(messageDiv);
        }
    }, 3000);
}

// Handle form submissions with loading states
document.addEventListener('DOMContentLoaded', function() {
    // Add loading states to buttons
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitButton = form.querySelector('button[type="submit"]');
            if (submitButton) {
                const originalText = submitButton.textContent;
                submitButton.disabled = true;
                
                if (submitButton.id === 'sync-steam-btn') {
                    submitButton.innerHTML = '<span class="flex items-center"><span class="spinner mr-1"></span>Syncing</span>';
                } else {
                    submitButton.textContent = 'Loading...';
                }
                
                // Re-enable after 5 seconds as fallback
                setTimeout(() => {
                    submitButton.disabled = false;
                    submitButton.textContent = originalText;
                }, 5000);
            }
        });
    });
});