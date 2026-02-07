/* === templates.js === */
document.addEventListener('DOMContentLoaded', () => {
    
    const filterBtns = document.querySelectorAll('.filter-btn');
    const cards = document.querySelectorAll('.template-card');
    const searchInput = document.getElementById('searchInput');
    const noResults = document.querySelector('.no-results');

    // 1. FILTER BY CATEGORY
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Style active button
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
            const title = card.querySelector('.card-title').innerText.toLowerCase();
            const desc = card.querySelector('.card-desc').innerText.toLowerCase();

            // Check Category
            const categoryMatch = (category === 'all') || (cardCategory === category);
            
            // Check Search Text
            const textMatch = title.includes(searchText) || desc.includes(searchText);

            if (categoryMatch && textMatch) {
                card.style.display = 'flex';
                visibleCount++;
            } else {
                card.style.display = 'none';
            }
        });

        // Show/Hide "No Results"
        if (visibleCount === 0) {
            noResults.style.display = 'block';
        } else {
            noResults.style.display = 'none';
        }
    }
});