// Theme Switching Logic
const getStoredTheme = () => localStorage.getItem('theme');
const setStoredTheme = theme => localStorage.setItem('theme', theme);

const getPreferredTheme = () => {
    const storedTheme = getStoredTheme();
    if (storedTheme) {
        return storedTheme;
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

const setTheme = theme => {
    document.documentElement.setAttribute('data-bs-theme', theme);
    const toggleBtn = document.querySelector('#themeToggle i');
    if (toggleBtn) {
        if (theme === 'dark') {
            toggleBtn.className = 'bi bi-sun-fill fs-5';
        } else {
            toggleBtn.className = 'bi bi-moon-stars-fill fs-5';
        }
    }
}

// Init
setTheme(getPreferredTheme());

document.addEventListener('DOMContentLoaded', () => {
    const toggleBtn = document.getElementById('themeToggle');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-bs-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            setStoredTheme(newTheme);
            setTheme(newTheme);
        });
    }
});
