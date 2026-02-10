/* === docs.js === */

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('docsOverlay'); // Можно добавить оверлей для затемнения
    sidebar.classList.toggle('active');
}

// Закрыть сайдбар при клике вне его (для мобильных)
document.addEventListener('click', (e) => {
    const sidebar = document.getElementById('sidebar');
    const btn = document.querySelector('.mobile-menu-btn');
    
    if (window.innerWidth <= 768 && 
        sidebar.classList.contains('active') && 
        !sidebar.contains(e.target) && 
        !btn.contains(e.target)) {
        sidebar.classList.remove('active');
    }
});

function copyCode(btn) {
    // Находим блок кода внутри .code-window -> pre -> code
    // Структура: .window-bar (btn is here) -> sibling is pre -> inside is code
    
    const windowDiv = btn.closest('.code-window');
    const codeBlock = windowDiv.querySelector('code').innerText;
    
    navigator.clipboard.writeText(codeBlock).then(() => {
        const originalIcon = btn.innerHTML;
        
        // Меняем иконку на галочку
        btn.innerHTML = '<i class="fa-solid fa-check"></i>';
        btn.style.color = '#22c55e';
        
        setTimeout(() => {
            btn.innerHTML = originalIcon;
            btn.style.color = '';
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy!', err);
    });
}