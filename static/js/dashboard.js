/**
 * Common dashboard functionality: theme toggle, auth check, logout.
 */
document.addEventListener('DOMContentLoaded', function () {
    // Update copyright year
    const yearElements = document.querySelectorAll('.footer .current-year');
    yearElements.forEach(function (el) {
        el.textContent = new Date().getFullYear();
    });

    // Check auth token on protected pages
    const token = localStorage.getItem('access_token');
    if (!token && !window.location.pathname.includes('/api/login-page')) {
        window.location.href = '/api/login-page';
        return;
    }

    // Theme toggle
    const themeToggle = document.getElementById('themeToggle');
    const htmlElement = document.documentElement;
    const sunIcon = themeToggle ? themeToggle.querySelector('.sun-icon') : null;
    const moonIcon = themeToggle ? themeToggle.querySelector('.moon-icon') : null;

    function updateThemeIcons(theme) {
        if (!sunIcon || !moonIcon) return;
        if (theme === 'dark') {
            sunIcon.style.display = 'none';
            moonIcon.style.display = 'inline-block';
        } else {
            sunIcon.style.display = 'inline-block';
            moonIcon.style.display = 'none';
        }
    }

    function setTheme(theme) {
        htmlElement.setAttribute('data-bs-theme', theme);
        localStorage.setItem('dashboard-theme', theme);
        updateThemeIcons(theme);
    }

    const savedTheme = localStorage.getItem('dashboard-theme') || 'light';
    setTheme(savedTheme);

    if (themeToggle) {
        themeToggle.addEventListener('click', function (e) {
            e.preventDefault();
            const currentTheme = htmlElement.getAttribute('data-bs-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            setTheme(newTheme);
        });
    }

    // Logout
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function (e) {
            e.preventDefault();
            localStorage.removeItem('access_token');
            window.location.href = '/api/login-page';
        });
    }
});
