/* === main.js === */

document.addEventListener('DOMContentLoaded', () => {
    
    // 1. ПОДСВЕТКА АКТИВНЫХ ССЫЛОК (Умная логика)
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link, .mobile-links a');

    navLinks.forEach(link => {
        const href = link.getAttribute('href');
        if (!href || href === '#') return;
        
        if (href === '/' && currentPath === '/') {
            link.classList.add('active');
        } else if (href !== '/' && currentPath.startsWith(href)) {
            link.classList.add('active');
        }
    });

    // 2. МОБИЛЬНОЕ МЕНЮ
    const menuToggle = document.getElementById('menuToggle');
    const mobileMenu = document.getElementById('mobileMenu');
    let isMenuOpen = false;

    if (menuToggle && mobileMenu) {
        menuToggle.addEventListener('click', () => {
            isMenuOpen = !isMenuOpen;
            
            // Анимация кнопки (превращение в крестик)
            const spans = menuToggle.querySelectorAll('span');
            if (isMenuOpen) {
                mobileMenu.classList.add('active');
                spans[0].style.transform = 'rotate(45deg) translate(5px, 6px)';
                spans[1].style.transform = 'rotate(-45deg) translate(5px, -6px)';
                document.body.style.overflow = 'hidden'; // Блок скролла
            } else {
                mobileMenu.classList.remove('active');
                spans[0].style.transform = 'none';
                spans[1].style.transform = 'none';
                document.body.style.overflow = '';
            }
        });
    }

    // 3. СКРОЛЛ ЭФФЕКТ ДЛЯ ПАРЯЩЕГО НАВБАРА
    const navbar = document.getElementById('navbar');
    const navContent = navbar.querySelector('.nav-content');

    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            // При скролле навбар становится чуть шире и прозрачнее/темнее
            navbar.style.width = '95%'; 
            navbar.style.maxWidth = '1400px';
            navContent.style.background = 'rgba(2, 6, 23, 0.8)'; // Более темный фон
            navContent.style.boxShadow = '0 15px 40px -10px rgba(0,0,0,0.8)';
        } else {
            // Вверху страницы - компактный вид
            navbar.style.width = '90%';
            navbar.style.maxWidth = '1200px';
            navContent.style.background = 'rgba(15, 23, 42, 0.6)';
            navContent.style.boxShadow = '0 10px 30px -10px rgba(0,0,0,0.5)';
        }
    });
});