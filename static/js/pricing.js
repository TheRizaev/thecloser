/* === pricing.js === */
document.addEventListener('DOMContentLoaded', () => {

    // 1. BILLING TOGGLE (Свитчер с анимацией)
    const btnMonth = document.getElementById('btn-month');
    const btnYear = document.getElementById('btn-year');
    const toggleBg = document.getElementById('toggleBg');
    const pricePro = document.getElementById('price-pro');
    const priceEnt = document.getElementById('price-ent');

    if (btnMonth && btnYear) {
        
        // Функция для плавной анимации чисел
        function animateValue(obj, start, end, duration) {
            let startTimestamp = null;
            const step = (timestamp) => {
                if (!startTimestamp) startTimestamp = timestamp;
                const progress = Math.min((timestamp - startTimestamp) / duration, 1);
                obj.innerHTML = Math.floor(progress * (end - start) + start);
                if (progress < 1) {
                    window.requestAnimationFrame(step);
                }
            };
            window.requestAnimationFrame(step);
        }

        function setBilling(period) {
            if (period === 'year') {
                // Включаем ГОД
                toggleBg.style.left = '50%'; // двигаем фон вправо (на 50% ширины)
                toggleBg.style.width = 'calc(50% - 5px)'; // корректируем ширину
                
                btnMonth.classList.remove('active');
                btnYear.classList.add('active');
                
                // Анимируем цены вниз (со скидкой)
                animateValue(pricePro, 29, 24, 300);
                animateValue(priceEnt, 99, 79, 300);
            } else {
                // Включаем МЕСЯЦ
                toggleBg.style.left = '5px'; // двигаем фон влево
                
                btnMonth.classList.add('active');
                btnYear.classList.remove('active');
                
                // Анимируем цены вверх
                animateValue(pricePro, 24, 29, 300);
                animateValue(priceEnt, 79, 99, 300);
            }
        }

        btnMonth.addEventListener('click', () => setBilling('month'));
        btnYear.addEventListener('click', () => setBilling('year'));
    }

    // 2. FAQ ACCORDION
    const faqItems = document.querySelectorAll('.faq-item');
    
    faqItems.forEach(item => {
        const head = item.querySelector('.faq-head');
        head.addEventListener('click', () => {
            // Закрываем другие (аккордеон) - опционально
            faqItems.forEach(other => {
                if (other !== item) other.classList.remove('active');
            });

            item.classList.toggle('active');
        });
    });

});