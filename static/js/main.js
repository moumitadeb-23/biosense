/**
 * BioSense - Frontend Theme Management & Global Utilities
 */
document.addEventListener('DOMContentLoaded', () => {
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    const themeIcon = document.getElementById('themeIcon');
    const htmlElement = document.documentElement;

    // Check saved theme in localStorage or default to dark
    const savedTheme = localStorage.getItem('biosense_theme') || 'dark';
    setTheme(savedTheme);

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const currentTheme = htmlElement.getAttribute('data-bs-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            setTheme(newTheme);
        });
    }

    function setTheme(theme) {
        htmlElement.setAttribute('data-bs-theme', theme);
        localStorage.setItem('biosense_theme', theme);

        if (themeIcon) {
            if (theme === 'dark') {
                themeIcon.className = 'bi bi-sun-fill text-warning';
                themeToggleBtn.setAttribute('title', 'Switch to Light Mode');
            } else {
                themeIcon.className = 'bi bi-moon-stars-fill text-primary';
                themeToggleBtn.setAttribute('title', 'Switch to Dark Mode');
            }
        }
    }
});
