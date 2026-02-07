/* === login.js === */
function toggleAuth() {
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const card = document.querySelector('.auth-card');

    // Сброс и запуск анимации
    card.classList.remove('fade-in');
    void card.offsetWidth; // Трюк для перезапуска CSS анимации (reflow)
    card.classList.add('fade-in');

    if (loginForm.classList.contains('hidden')) {
        // Показать Вход
        loginForm.classList.remove('hidden');
        registerForm.classList.add('hidden');
    } else {
        // Показать Регистрацию
        loginForm.classList.add('hidden');
        registerForm.classList.remove('hidden');
    }
}