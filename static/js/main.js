/* === main.js — Global Logic === */

document.addEventListener('DOMContentLoaded', () => {
    
    // --- 1. АВТОМАТИЧЕСКАЯ ПОДСВЕТКА АКТИВНОЙ СТРАНИЦЫ ---
    // Работает с Django URLs (например, /pricing/, /docs/)
    
    const currentPath = window.location.pathname; // Получаем текущий путь (напр. "/pricing/")
    
    // Выбираем все ссылки в десктопном и мобильном меню
    const navLinks = document.querySelectorAll('.nav-links a, .mobile-menu a');

    navLinks.forEach(link => {
        const linkPath = link.getAttribute('href'); // Получаем ссылку (напр. "/pricing/")

        // Пропускаем пустые ссылки или якоря
        if (!linkPath || linkPath === '#' || linkPath.startsWith('http')) return;

        // ЛОГИКА СРАВНЕНИЯ:
        // 1. Если это Главная ('/') -> Активна только если мы точно на главной
        if (linkPath === '/') {
            if (currentPath === '/') {
                link.classList.add('active');
            }
        } 
        // 2. Для остальных страниц -> Активна, если путь начинается с этой ссылки
        // (например, "/docs/api" подсветит "/docs/")
        else {
            if (currentPath.startsWith(linkPath)) {
                link.classList.add('active');
            }
        }
    });

    // --- 2. МОБИЛЬНОЕ МЕНЮ (Гамбургер) ---
    const menuToggle = document.getElementById('menuToggle');
    const mobileMenu = document.getElementById('mobileMenu');
    
    if (menuToggle && mobileMenu) {
        const icon = menuToggle.querySelector('i');
        let isMenuOpen = false;

        function toggleMenu() {
            isMenuOpen = !isMenuOpen;
            if (isMenuOpen) {
                // Открыть
                mobileMenu.classList.add('active');
                icon.classList.remove('fa-bars');
                icon.classList.add('fa-xmark'); // Иконка крестика
                document.body.style.overflow = 'hidden'; // Блокируем скролл сайта
            } else {
                // Закрыть
                mobileMenu.classList.remove('active');
                icon.classList.remove('fa-xmark');
                icon.classList.add('fa-bars'); // Иконка бургер
                document.body.style.overflow = ''; // Возвращаем скролл
            }
        }

        menuToggle.addEventListener('click', toggleMenu);

        // Закрывать меню при клике на любую ссылку внутри
        mobileMenu.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                if (isMenuOpen) toggleMenu();
            });
        });
    }

    // --- 3. ЭФФЕКТ СКРОЛЛА НАВИГАЦИИ ---
    // Делает фон темнее при прокрутке вниз
    const navbar = document.getElementById('mainNav');
    if (navbar) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) {
                navbar.style.background = 'rgba(3, 7, 18, 0.95)';
                navbar.style.boxShadow = '0 4px 30px rgba(0, 0, 0, 0.3)';
                navbar.style.padding = '15px 5%'; // Чуть уменьшаем высоту
            } else {
                navbar.style.background = 'rgba(3, 7, 18, 0.7)';
                navbar.style.boxShadow = 'none';
                navbar.style.padding = '20px 5%'; // Возвращаем высоту
            }
        });
    }
});