// Auto-logout functionality
class AutoLogout {
    constructor(timeoutMinutes = 10) {
        this.timeoutMinutes = timeoutMinutes;
        this.timeoutMs = timeoutMinutes * 60 * 1000; // Convert to milliseconds
        this.warningMinutes = 1; // Show warning 1 minute before logout
        this.warningMs = this.warningMinutes * 60 * 1000;
        this.timer = null;
        this.warningTimer = null;
        this.lastActivity = Date.now();
        this.isLoggedIn = this.checkIfLoggedIn();
        
        if (this.isLoggedIn) {
            this.init();
        }
    }
    
    checkIfLoggedIn() {
        // Check if user is logged in by looking for logout link or user-specific elements
        const logoutLink = document.querySelector('a[href*="logout"], a[href*="logout_view"]');
        const userMenu = document.querySelector('.user-menu, .navbar-nav .dropdown');
        return !!(logoutLink || userMenu);
    }
    
    init() {
        // Set up event listeners for user activity
        this.setupActivityListeners();
        
        // Start the timer
        this.startTimer();
        
        // Check activity every minute
        setInterval(() => this.checkActivity(), 60000);
        
        console.log(`Auto-logout initialized: ${this.timeoutMinutes} minutes of inactivity`);
    }
    
    setupActivityListeners() {
        const events = [
            'mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'
        ];
        
        events.forEach(event => {
            document.addEventListener(event, () => this.resetTimer(), true);
        });
        
        // Also listen for form submissions and AJAX requests
        document.addEventListener('submit', () => this.resetTimer(), true);
        
        // Listen for visibility change (tab switching)
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.resetTimer();
            }
        });
    }
    
    resetTimer() {
        this.lastActivity = Date.now();
        this.startTimer();
        
        // Clear existing timers
        if (this.timer) {
            clearTimeout(this.timer);
        }
        if (this.warningTimer) {
            clearTimeout(this.warningTimer);
        }
        
        // Start new timers
        this.startTimer();
    }
    
    startTimer() {
        // Set warning timer
        this.warningTimer = setTimeout(() => {
            this.showWarning();
        }, this.timeoutMs - this.warningMs);
        
        // Set logout timer
        this.timer = setTimeout(() => {
            this.logout();
        }, this.timeoutMs);
    }
    
    showWarning() {
        // Create warning modal
        const warningModal = document.createElement('div');
        warningModal.className = 'modal fade';
        warningModal.id = 'timeoutWarningModal';
        warningModal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header bg-warning">
                        <h5 class="modal-title">
                            <i class="fas fa-exclamation-triangle me-2"></i>
                            Session Timeout Warning
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p>Your session will expire in <strong>${this.warningMinutes} minute</strong> due to inactivity.</p>
                        <p>Click "Stay Logged In" to continue your session, or you will be automatically logged out.</p>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Stay Logged In</button>
                        <button type="button" class="btn btn-primary" onclick="autoLogout.logout()">Logout Now</button>
                    </div>
                </div>
            </div>
        `;
        
        // Add modal to page
        document.body.appendChild(warningModal);
        
        // Show modal
        const modal = new bootstrap.Modal(warningModal);
        modal.show();
        
        // Auto-hide after 30 seconds if user doesn't interact
        setTimeout(() => {
            if (warningModal.parentNode) {
                modal.hide();
                warningModal.remove();
            }
        }, 30000);
        
        // Reset timer when modal is closed
        warningModal.addEventListener('hidden.bs.modal', () => {
            this.resetTimer();
            warningModal.remove();
        });
    }
    
    logout() {
        console.log('Auto-logout: Session expired due to inactivity');
        
        // Show logout notification
        this.showLogoutNotification();
        
        // Redirect to logout URL after a short delay
        setTimeout(() => {
            const logoutUrl = this.getLogoutUrl();
            if (logoutUrl) {
                window.location.href = logoutUrl;
            } else {
                // Fallback: redirect to home page
                window.location.href = '/';
            }
        }, 2000);
    }
    
    getLogoutUrl() {
        // Try to find logout link
        const logoutLink = document.querySelector('a[href*="logout"], a[href*="logout_view"]');
        if (logoutLink) {
            return logoutLink.href;
        }
        
        // Check if there's a logout URL in the page context
        if (typeof logoutUrl !== 'undefined') {
            return logoutUrl;
        }
        
        return null;
    }
    
    showLogoutNotification() {
        // Create notification
        const notification = document.createElement('div');
        notification.className = 'alert alert-info alert-dismissible fade show position-fixed';
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            <i class="fas fa-info-circle me-2"></i>
            <strong>Session Expired:</strong> You have been automatically logged out due to inactivity.
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }
    
    checkActivity() {
        const now = Date.now();
        const timeSinceLastActivity = now - this.lastActivity;
        
        // If more than 5 minutes have passed without activity, check if user is still active
        if (timeSinceLastActivity > 300000) { // 5 minutes
            // You could add additional checks here, like checking if the page is visible
            // or if there are any active AJAX requests
        }
    }
}

// Initialize auto-logout when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Check if user is logged in before initializing
    if (document.querySelector('a[href*="logout"], a[href*="logout_view"], .user-menu, .navbar-nav .dropdown')) {
        window.autoLogout = new AutoLogout(10); // 10 minutes timeout
    }
});

// Export for potential use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AutoLogout;
}
