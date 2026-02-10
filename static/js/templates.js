/* === templates.js === */
document.addEventListener('DOMContentLoaded', () => {
    
    const filterBtns = document.querySelectorAll('.filter-btn');
    const cards = document.querySelectorAll('.template-card');
    const searchInput = document.getElementById('searchInput');
    const noResults = document.querySelector('.no-results');

    // 1. FILTER BY CATEGORY
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Active styling
            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const filterValue = btn.getAttribute('data-filter');
            filterCards(filterValue, searchInput.value);
        });
    });

    // 2. SEARCH INPUT
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const activeCategory = document.querySelector('.filter-btn.active').getAttribute('data-filter');
            filterCards(activeCategory, e.target.value);
        });
    }

    function filterCards(category, searchText) {
        searchText = searchText.toLowerCase();
        let visibleCount = 0;

        cards.forEach(card => {
            const cardCategory = card.getAttribute('data-category');
            
            // Получаем текст из заголовка и тегов для поиска
            const title = card.querySelector('h3').innerText.toLowerCase();
            const tags = Array.from(card.querySelectorAll('.tags span')).map(t => t.innerText.toLowerCase()).join(' ');
            
            // Логика фильтрации
            const categoryMatch = (category === 'all') || (cardCategory === category);
            const textMatch = title.includes(searchText) || tags.includes(searchText);

            if (categoryMatch && textMatch) {
                card.style.display = 'flex';
                // Анимация появления
                card.style.animation = 'fadeIn 0.4s ease forwards';
                visibleCount++;
            } else {
                card.style.display = 'none';
            }
        });

        // Toggle "No Results"
        if (visibleCount === 0) {
            noResults.style.display = 'block';
            noResults.style.animation = 'fadeIn 0.4s ease forwards';
        } else {
            noResults.style.display = 'none';
        }
    }
});