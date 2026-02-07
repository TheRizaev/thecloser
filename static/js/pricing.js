/* === pricing.js === */
document.addEventListener('DOMContentLoaded', () => {

    // 1. BILLING TOGGLE LOGIC
    const btnMonth = document.getElementById('btn-month');
    const btnYear = document.getElementById('btn-year');
    const toggleBg = document.getElementById('toggleBg');
    const pricePro = document.getElementById('price-pro');
    const priceEnt = document.getElementById('price-ent');

    if (btnMonth && btnYear) {
        // Функция переключения
        function setBilling(period) {
            if (period === 'year') {
                toggleBg.style.left = '50%';
                btnMonth.classList.remove('active');
                btnYear.classList.add('active');
                
                // Анимация смены цены (скидка 20%)
                pricePro.innerText = '24';
                priceEnt.innerText = '79';
            } else {
                toggleBg.style.left = '5px';
                btnMonth.classList.add('active');
                btnYear.classList.remove('active');
                
                pricePro.innerText = '29';
                priceEnt.innerText = '99';
            }
        }

        // Слушатели событий на клик
        btnMonth.addEventListener('click', () => setBilling('month'));
        btnYear.addEventListener('click', () => setBilling('year'));
    }

    // 2. FAQ ACCORDION LOGIC
    const faqQuestions = document.querySelectorAll('.faq-question');
    
    faqQuestions.forEach(item => {
        item.addEventListener('click', () => {
            const parent = item.parentElement;
            
            // Если хотим закрывать другие при открытии одного, раскомментируй код ниже:
            /*
            document.querySelectorAll('.faq-item').forEach(other => {
                if (other !== parent) other.classList.remove('active');
            });
            */

            parent.classList.toggle('active');
        });
    });

});