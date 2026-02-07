/* === docs.js === */
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (sidebar) {
        sidebar.classList.toggle('open');
    }
}

function copyCode(btn) {
    // Находим блок кода (pre code)
    const codeBlock = btn.parentElement.nextElementSibling.innerText;
    
    navigator.clipboard.writeText(codeBlock).then(() => {
        const originalHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
        btn.style.color = '#22c55e';
        
        setTimeout(() => {
            btn.innerHTML = originalHtml;
            btn.style.color = '';
        }, 2000);
    });
}