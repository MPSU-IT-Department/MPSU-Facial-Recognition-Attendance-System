/**
 * Authentication Module
 * Handles login functionality
 */
document.addEventListener('DOMContentLoaded', () => {
    // DOM element references
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const toggleRegisterBtn = document.getElementById('toggle-register');
    const toggleLoginBtn = document.getElementById('toggle-login');
    const loginView = document.getElementById('login-view');
    const registerView = document.getElementById('register-view');
    
    // Add event listeners
    if (toggleRegisterBtn) {
        toggleRegisterBtn.addEventListener('click', (e) => {
            e.preventDefault();
            loginView.classList.add('d-none');
            registerView.classList.remove('d-none');
        });
    }
    
    if (toggleLoginBtn) {
        toggleLoginBtn.addEventListener('click', (e) => {
            e.preventDefault();
            registerView.classList.add('d-none');
            loginView.classList.remove('d-none');
        });
    }
    
    // Mobile sidebar toggle
    const mobileToggle = document.getElementById('mobile-toggle');
    const sidebar = document.querySelector('.sidebar');
    
    if (mobileToggle && sidebar) {
        mobileToggle.addEventListener('click', () => {
            sidebar.classList.toggle('show');
        });
    }
    
    // Logout functionality
    const logoutBtn = document.querySelector('.logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            // Send to logout route
            window.location.href = '/auth/logout';
        });
    }
    
    // Password confirmation validation
    function validatePasswordMatch() {
        const password = document.getElementById('password');
        const confirmPassword = document.getElementById('confirm_password');
        
        if (password && confirmPassword) {
            confirmPassword.addEventListener('input', () => {
                if (password.value !== confirmPassword.value) {
                    confirmPassword.setCustomValidity('Passwords must match');
                } else {
                    confirmPassword.setCustomValidity('');
                }
            });
        }
    }
    
    validatePasswordMatch();
});
