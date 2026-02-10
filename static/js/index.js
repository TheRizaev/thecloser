/* === index.js - Скрипты Главной Страницы === */

document.addEventListener('DOMContentLoaded', () => {

    // 3. CHAT SIMULATION (С АВТОСКРОЛЛОМ)
    const chatArea = document.getElementById('chatArea');
    
    // Создаем индикатор печати программно, если его нет в HTML внутри chatArea
    // (или используем существующий, если вы его верстали отдельно)
    let typingIndicator = document.getElementById('typingIndicator');
    
    if (chatArea) {
        const conversation = [
            { type: 'user', text: "Как это увеличит мои продажи?" },
            { type: 'ai', text: "Я отвечаю клиентам мгновенно, 24/7. Пока конкуренты спят, я закрываю сделку." },
            { type: 'user', text: "А это сложно настроить?" },
            { type: 'ai', text: "Нет. Вы просто загружаете PDF с прайсом, и я готов к работе через 5 минут." },
            { type: 'user', text: "Сколько стоит?" },
            { type: 'ai', text: "От $49/мес. Обычно окупается с первого же удержанного клиента." }
        ];

        const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

        // Функция скролла в самый низ
        const scrollToBottom = () => {
            if (chatArea) {
                chatArea.scrollTo({
                    top: chatArea.scrollHeight,
                    behavior: 'smooth'
                });
            }
        };

        async function runChat() {
            while(true) {
                chatArea.innerHTML = '';
                await wait(1000);

                for (const msg of conversation) {
                    // 1. Сообщение пользователя
                    if (msg.type === 'user') {
                        await wait(1000); // Пауза перед вопросом
                        appendMessage(msg);
                    } 
                    // 2. Ответ AI
                    else {
                        // Показываем индикатор печати
                        showTyping();
                        
                        // Имитируем время на "подумать" (зависит от длины текста)
                        await wait(1000 + msg.text.length * 30);
                        
                        // Удаляем индикатор и показываем сообщение
                        hideTyping();
                        appendMessage(msg);
                    }
                }

                // Пауза перед перезапуском
                await wait(5000);
            }
        }

        function appendMessage(msg) {
            const el = document.createElement('div');
            el.className = `msg-bubble ${msg.type === 'user' ? 'msg-user' : 'msg-ai'}`;
            el.innerText = msg.text;
            chatArea.appendChild(el);
            scrollToBottom(); // <-- ВАЖНО: Скроллим сразу после добавления
        }

        function showTyping() {
            // Если индикатор уже есть в HTML (внизу чата), просто показываем его
            // Если мы его создаем динамически:
            const typingDiv = document.createElement('div');
            typingDiv.id = 'temp-typing';
            typingDiv.className = 'typing-bar'; // Используем ваши стили
            typingDiv.innerHTML = `
                <div class="ai-icon"><i class="fa-solid fa-robot"></i></div>
                <div class="dots"><span></span><span></span><span></span></div>
            `;
            chatArea.appendChild(typingDiv);
            scrollToBottom(); // <-- ВАЖНО: Скроллим, чтобы показать индикатор
        }

        function hideTyping() {
            const tempTyping = document.getElementById('temp-typing');
            if (tempTyping) tempTyping.remove();
        }

        // Запуск
        runChat();
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

    // === AUTO ROTATE PROCESS TABS ===
    let currentStep = 0;
    const totalSteps = 3;
    let autoPlayInterval;

    // Функция переключения
    window.switchTab = function(index) {
        const buttons = document.querySelectorAll('.tab-btn');
        const contents = document.querySelectorAll('.tab-content');
        
        // Убираем активный класс у всех
        buttons.forEach(btn => btn.classList.remove('active'));
        contents.forEach(content => content.classList.remove('active'));

        // Добавляем активный класс нужному
        if(buttons[index] && contents[index]) {
            buttons[index].classList.add('active');
            contents[index].classList.add('active');
            
            // Перезапуск анимации (трюк с клонированием)
            const activeContent = contents[index];
            const clone = activeContent.cloneNode(true);
            activeContent.parentNode.replaceChild(clone, activeContent);
        }
        currentStep = index; // Синхронизируем счетчик
    };

    // Функция для ручного клика (сбрасывает таймер)
    window.manualSwitch = function(index) {
        switchTab(index);
        resetAutoPlay();
    }

    function startAutoPlay() {
        autoPlayInterval = setInterval(() => {
            let nextStep = (currentStep + 1) % totalSteps;
            switchTab(nextStep);
        }, 3000); // 3 секунды
    }

    function resetAutoPlay() {
        clearInterval(autoPlayInterval);
        startAutoPlay(); // Запускаем заново
    }

    // Запуск при загрузке
    startAutoPlay();

});