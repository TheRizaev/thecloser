/* === index.js - Скрипты Главной Страницы === */

document.addEventListener('DOMContentLoaded', () => {
    
    // 1. 3D TILT EFFECT (Только на десктопе)
    const card = document.getElementById('tiltCard');
    const container = document.getElementById('tiltContainer');

    if (window.matchMedia("(min-width: 1025px)").matches && container && card) {
        container.addEventListener('mousemove', (e) => {
            const rect = container.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            // Наклон карты
            const xRotation = -((y - rect.height / 2) / 25);
            const yRotation = (x - rect.width / 2) / 25;
            card.style.transform = `perspective(1000px) rotateX(${xRotation}deg) rotateY(${yRotation}deg)`;
        });

        container.addEventListener('mouseleave', () => {
            card.style.transform = 'perspective(1000px) rotateX(0) rotateY(0)';
        });
    }

    // 2. CHAT SIMULATION (Бесконечный диалог)
    const chatArea = document.getElementById('chatArea');
    const typingIndicator = document.getElementById('typingIndicator');
    
    if (chatArea && typingIndicator) {
        const scenarios = [
            { user: "Сколько стоит внедрение?", bot: "У нас есть бесплатный тариф! PRO версия от $19/мес." },
            { user: "Можно загрузить PDF?", bot: "Да, перетащите файл в базу знаний. Я изучу его за 10 секунд." },
            { user: "А интеграция с CRM?", bot: "Конечно! Передаем заявки в AmoCRM и Bitrix24." }
        ];

        let currentScenarioIndex = 0;

        async function typeText(element, text, speed = 30) {
            element.innerHTML = "";
            for (let i = 0; i < text.length; i++) {
                element.innerHTML += text.charAt(i);
                await new Promise(r => setTimeout(r, speed));
            }
        }

        async function runChatSimulation() {
            while (true) {
                const scenario = scenarios[currentScenarioIndex];
                
                // Очистка
                chatArea.innerHTML = '';
                await new Promise(r => setTimeout(r, 500));

                // User
                const userMsg = document.createElement('div');
                userMsg.className = 'message user';
                userMsg.innerText = scenario.user;
                chatArea.appendChild(userMsg);
                await new Promise(r => setTimeout(r, 800));

                // Typing
                typingIndicator.style.display = 'flex';
                await new Promise(r => setTimeout(r, 1500));
                typingIndicator.style.display = 'none';

                // Bot
                const botMsg = document.createElement('div');
                botMsg.className = 'message bot';
                chatArea.appendChild(botMsg);
                await typeText(botMsg, scenario.bot);

                await new Promise(r => setTimeout(r, 4000));
                currentScenarioIndex = (currentScenarioIndex + 1) % scenarios.length;
            }
        }

        runChatSimulation();
    }

    // 3. PROCESS TABS LOGIC
    // Функция должна быть глобальной, чтобы вызываться через onclick в HTML
    window.switchTab = function(index) {
        const buttons = document.querySelectorAll('.tab-btn');
        const contents = document.querySelectorAll('.tab-content');
        
        buttons.forEach(btn => btn.classList.remove('active'));
        contents.forEach(content => content.classList.remove('active'));

        if(buttons[index] && contents[index]) {
            buttons[index].classList.add('active');
            contents[index].classList.add('active');
            
            // Перезапуск анимаций внутри контента
            const activeContent = contents[index];
            const clone = activeContent.cloneNode(true);
            activeContent.parentNode.replaceChild(clone, activeContent);
        }
    };

    // 4. BENTO SPOTLIGHT EFFECT
    const bentoCards = document.querySelectorAll('.bento-card');
    bentoCards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            card.style.background = `radial-gradient(circle at ${x}px ${y}px, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.02))`;
            card.style.borderColor = "rgba(255,255,255,0.2)";
        });

        card.addEventListener('mouseleave', () => {
            card.style.background = "rgba(255, 255, 255, 0.02)";
            card.style.borderColor = "rgba(255, 255, 255, 0.08)";
        });
    });

});