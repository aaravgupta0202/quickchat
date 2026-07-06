
    tailwind.config = {
        theme: {
            extend: {
                fontFamily: { sans: ['Inter', 'sans-serif'] },
                colors: {
                    base: 'var(--color-base, #000000)',
                    surface: 'var(--color-surface, #0a0a0a)',
                    elevated: 'var(--color-elevated, #111111)',
                    border: 'var(--color-border, #262626)',
                    borderhover: 'var(--color-borderhover, #404040)',
                    text: 'var(--color-text, #ededed)',
                    muted: 'var(--color-muted, #a1a1aa)'
                }
            }
        }
    }


        const backend = "https://sample-ii6m.onrender.com";
        const roomCode = new URLSearchParams(window.location.search).get('room');
        let userName = localStorage.getItem('userName');
        let deviceId = localStorage.getItem('deviceId');

        if (!roomCode || !userName) {
            window.location.href = 'index.html';
        }

        // Multi-tab check (BroadcastChannel)
        const bc = new BroadcastChannel('quickchat_room_' + roomCode);
        bc.postMessage('ping');
        bc.onmessage = (event) => {
            if (event.data === 'ping') {
                bc.postMessage('pong'); // Tell new tab we are here
            } else if (event.data === 'pong') {
                // We are the new tab, and an existing tab responded
                document.getElementById('multiTabError').classList.remove('hidden');
            }
        };

        // PWA Setup
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('./sw.js').catch(console.error);
        }

        document.getElementById('roomDisplay').textContent = roomCode;
        document.getElementById('infoRoomCode').textContent = roomCode;

        let onlineUsers = new Set([userName]);
        let typingUsers = new Set();
        let messageCheckInterval;
        let savedChatName = 'New Chat';

        // Escaping HTML
        function escapeHtml(unsafe) {
            return String(unsafe || "")
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        // Modals
        function toggleModal(modalId, contentId, show) {
            const modal = document.getElementById(modalId);
            const content = document.getElementById(contentId);
            if (show) {
                modal.classList.remove('hidden');
                void modal.offsetWidth;
                modal.classList.remove('opacity-0');
                content.classList.remove('scale-95');
            } else {
                modal.classList.add('opacity-0');
                content.classList.add('scale-95');
                setTimeout(() => modal.classList.add('hidden'), 300);
            }
        }

        function openInfoModal() { updateRoomInfo(); toggleModal('infoModal', 'infoModalContent', true); }
        function closeInfoModal() { toggleModal('infoModal', 'infoModalContent', false); }
        function openNameModal() { document.getElementById('newChatNameInput').value = savedChatName; toggleModal('nameModal', 'nameModalContent', true); document.getElementById('newChatNameInput').focus(); }
        function closeNameModal() { toggleModal('nameModal', 'nameModalContent', false); }
        function openThemeModal() { toggleModal('themeModal', 'themeModalContent', true); }
        function closeThemeModal() { toggleModal('themeModal', 'themeModalContent', false); }

        function showToast(message) {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.classList.remove('-translate-y-full', 'opacity-0');
            setTimeout(() => toast.classList.add('-translate-y-full', 'opacity-0'), 2500);
        }

        function copyRoomCode() {
            navigator.clipboard.writeText(roomCode).then(() => showToast('Copied to clipboard'));
        }

        // API Calls
        async function loadChatName() {
            try {
                const res = await fetch(`${backend}/room/${roomCode}/name`);
                const data = await res.json();
                savedChatName = data.chat_name || 'New Chat';
                document.getElementById('chatName').childNodes[0].nodeValue = savedChatName + " ";
            } catch (e) {}
        }
        loadChatName();

        async function saveChatName() {
            const newName = document.getElementById('newChatNameInput').value.trim();
            if (!newName || newName === savedChatName) return closeNameModal();
            try {
                const res = await fetch(`${backend}/room/${roomCode}/name?user=${encodeURIComponent(userName)}&chat_name=${encodeURIComponent(newName)}`, { method: 'POST' });
                if (res.ok) {
                    savedChatName = newName;
                    document.getElementById('chatName').childNodes[0].nodeValue = newName + " ";
                    closeNameModal();
                    showToast('Chat name updated');
                    fetchMessages();
                }
            } catch (e) { alert('Error changing chat name'); }
        }

        async function updateRoomInfo() {
            try {
                const res = await fetch(`${backend}/room/${roomCode}/info`);
                const data = await res.json();
                if (data.time_remaining !== undefined) document.getElementById('timeRemaining').textContent = `${data.time_remaining} min`;
                document.getElementById('userCount').textContent = data.user_count || 1;
                document.getElementById('messageCount').textContent = data.message_count || 0;
                
                const list = document.getElementById('membersList');
                list.innerHTML = '';
                (data.active_users || [userName]).forEach(u => {
                    list.innerHTML += `<div class="flex items-center gap-2 text-sm bg-base p-2 rounded-md border border-border">
                        <div class="w-1.5 h-1.5 rounded-full ${typingUsers.has(u) ? 'bg-white animate-pulse' : 'bg-gray-500'}"></div>
                        <span class="text-text">${escapeHtml(u)}</span>
                        ${typingUsers.has(u) ? '<span class="text-xs text-muted ml-auto font-light">typing...</span>' : ''}
                    </div>`;
                });
            } catch (e) {}
        }

        // Heartbeat
        setInterval(() => {
            fetch(`${backend}/heartbeat/${roomCode}?user=${encodeURIComponent(userName)}`, { method: 'POST' }).catch(() => {});
        }, 10000);

        // Typing
        document.getElementById('messageInput').addEventListener('input', () => {
            fetch(`${backend}/typing/${roomCode}?user=${encodeURIComponent(userName)}&deviceId=${deviceId}`, { method: 'POST' }).catch(() => {});
        });

        setInterval(async () => {
            try {
                const res = await fetch(`${backend}/typing/${roomCode}`);
                const data = await res.json();
                typingUsers = new Set(data.typing || []);
                const indicator = document.getElementById('typingIndicator');
                const others = Array.from(typingUsers).filter(u => u !== userName);
                if (others.length > 0) {
                    indicator.innerHTML = `${escapeHtml(others.join(', '))} ${others.length === 1 ? 'is' : 'are'} typing <span class="loading-dots ml-1"><div></div><div></div><div></div></span>`;
                    indicator.classList.remove('hidden');
                } else {
                    indicator.classList.add('hidden');
                }
            } catch (e) {}
        }, 1500);

        // Messaging
        async function sendMessage(e) {
            e.preventDefault();
            const input = document.getElementById('messageInput');
            const btn = document.getElementById('sendBtn');
            const msg = input.value.trim();
            if (!msg) return;
            
            input.disabled = true;
            btn.disabled = true;
            try {
                await fetch(`${backend}/message/${roomCode}?message=${encodeURIComponent(msg)}&user=${encodeURIComponent(userName)}&deviceId=${deviceId}`, { method: 'POST' });
                input.value = '';
                fetchMessages();
            } catch (err) {}
            input.disabled = false;
            btn.disabled = false;
            input.focus();
        }

        let lastMessageCount = 0;
        async function fetchMessages() {
            try {
                const res = await fetch(`${backend}/messages/${roomCode}?deviceId=${deviceId}`);
                const data = await res.json();
                if (data.error === 'device_limit') {
                    document.getElementById('multiTabError').classList.remove('hidden');
                    channel.postMessage('duplicate');
                    return;
                }
                if (data.messages && data.messages.length !== lastMessageCount) {
                    lastMessageCount = data.messages.length;
                    renderMessages(data.messages);
                }
                if (data.active_users) {
                    document.getElementById('userCount').textContent = `${data.active_users.length} online`;
                    const list = document.getElementById('membersList');
                    if (list && !document.getElementById('infoModal').classList.contains('hidden')) {
                        list.innerHTML = '';
                        data.active_users.forEach(u => {
                            list.innerHTML += `<div class="flex items-center gap-2 text-sm bg-base p-2 rounded-md border border-border">
                                <div class="w-1.5 h-1.5 rounded-full ${typingUsers.has(u) ? 'bg-white animate-pulse' : 'bg-green-500'}"></div>
                                <span class="text-text">${escapeHtml(u)}</span>
                                ${typingUsers.has(u) ? '<span class="text-xs text-muted ml-auto font-light">typing...</span>' : ''}
                            </div>`;
                        });
                    }
                }
            } catch (e) {}
        }

        function renderMessages(msgs) {
            const container = document.getElementById('messagesContainer');
            const wasScrolledToBottom = container.scrollHeight - container.clientHeight <= container.scrollTop + 50;
            
            container.innerHTML = '';
            msgs.forEach(m => {
                const time = new Date(m.time * 1000).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                if (m.user === 'System') {
                    let safeText = m.text;
                    container.innerHTML += `<div class="flex justify-center w-full my-2"><div class="bubble-system">${safeText}</div></div>`;
                } else if (m.user === userName) {
                    container.innerHTML += `<div class="flex justify-end w-full pl-12"><div class="chat-bubble bubble-you">
                        <div>${escapeHtml(m.text)}</div><div class="msg-time text-gray-500">${time}</div>
                    </div></div>`;
                } else {
                    container.innerHTML += `<div class="flex flex-col items-start w-full pr-12">
                        <span class="text-xs text-muted ml-1 mb-1 font-medium">${escapeHtml(m.user)}</span>
                        <div class="chat-bubble bubble-other">
                            <div>${escapeHtml(m.text)}</div><div class="msg-time text-gray-500">${time}</div>
                        </div>
                    </div>`;
                }
            });
            
            if (wasScrolledToBottom || msgs[msgs.length-1]?.user === userName) {
                container.scrollTop = container.scrollHeight;
            }
        }

        // Theme Color Setup
        const defaultTheme = {
            '--color-base': '#000000',
            '--color-surface': '#0a0a0a',
            '--color-elevated': '#111111',
            '--color-border': '#262626',
            '--color-borderhover': '#404040',
            '--color-text': '#ededed',
            '--color-muted': '#a1a1aa',
            '--accent-color': '#ffffff'
        };

        function applyTheme(theme) {
            for (const [key, value] of Object.entries(theme)) {
                document.documentElement.style.setProperty(key, value);
            }
            document.getElementById('themeAccent').value = theme['--accent-color'] || defaultTheme['--accent-color'];
            document.getElementById('themeText').value = theme['--color-text'] || defaultTheme['--color-text'];
            document.getElementById('themeBase').value = theme['--color-base'] || defaultTheme['--color-base'];
            document.getElementById('themeSurface').value = theme['--color-surface'] || defaultTheme['--color-surface'];
        }

        function saveTheme() {
            const theme = {
                '--accent-color': document.getElementById('themeAccent').value,
                '--color-text': document.getElementById('themeText').value,
                '--color-base': document.getElementById('themeBase').value,
                '--color-surface': document.getElementById('themeSurface').value,
                '--color-elevated': adjustColor(document.getElementById('themeSurface').value, 5),
                '--color-border': adjustColor(document.getElementById('themeSurface').value, 15),
                '--color-borderhover': adjustColor(document.getElementById('themeSurface').value, 25),
                '--color-muted': adjustColor(document.getElementById('themeText').value, -40)
            };
            applyTheme(theme);
            localStorage.setItem(`customTheme_${roomCode}`, JSON.stringify(theme));
        }

        function resetTheme() {
            localStorage.removeItem(`customTheme_${roomCode}`);
            applyTheme(defaultTheme);
            closeThemeModal();
        }

        function adjustColor(col, amt) {
            let usePound = false;
            if (col[0] == "#") { col = col.slice(1); usePound = true; }
            let num = parseInt(col,16);
            let r = (num >> 16) + amt;
            if (r > 255) r = 255; else if (r < 0) r = 0;
            let b = ((num >> 8) & 0x00FF) + amt;
            if (b > 255) b = 255; else if (b < 0) b = 0;
            let g = (num & 0x0000FF) + amt;
            if (g > 255) g = 255; else if (g < 0) g = 0;
            return (usePound?"#":"") + String("000000" + (g | (b << 8) | (r << 16)).toString(16)).slice(-6);
        }

        const savedThemeStr = localStorage.getItem(`customTheme_${roomCode}`);
        if (savedThemeStr) {
            try { applyTheme(JSON.parse(savedThemeStr)); } catch (e) { applyTheme(defaultTheme); }
        } else {
            applyTheme(defaultTheme);
        }

        ['themeAccent', 'themeText', 'themeBase', 'themeSurface'].forEach(id => {
            document.getElementById(id).addEventListener('input', saveTheme);
        });

        // Speech to Text
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        let recognition = null;
        let isRecording = false;

        if (SpeechRecognition) {
            recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;
            recognition.lang = 'en-US';

            recognition.onstart = function() {
                isRecording = true;
                const micIcon = document.getElementById('micIcon');
                micIcon.classList.add('text-red-500', 'animate-pulse');
                document.getElementById('messageInput').placeholder = "Listening...";
            };

            recognition.onresult = function(event) {
                const transcript = event.results[0][0].transcript;
                const input = document.getElementById('messageInput');
                input.value = input.value ? input.value + " " + transcript : transcript;
            };

            recognition.onerror = function(event) {
                showToast("Microphone error: " + event.error);
                stopRecordingUI();
            };

            recognition.onend = function() {
                stopRecordingUI();
            };
        } else {
            document.getElementById('micBtn').style.display = 'none';
        }

        function stopRecordingUI() {
            isRecording = false;
            const micIcon = document.getElementById('micIcon');
            micIcon.classList.remove('text-red-500', 'animate-pulse');
            document.getElementById('messageInput').placeholder = "Type a message...";
        }

        function toggleSpeechRecognition() {
            if (!recognition) return showToast("Speech recognition not supported in this browser.");
            
            if (isRecording) {
                recognition.stop();
            } else {
                try {
                    recognition.start();
                } catch (e) {
                    // Already started
                }
            }
        }

        window.addEventListener('load', () => {
            // Register Join
            fetch(`${backend}/join/${roomCode}?user=${encodeURIComponent(userName)}`, { method: 'POST' }).catch(() => {});

            fetchMessages();
            setInterval(fetchMessages, 2000); // Polling every 2s
            setInterval(sendHeartbeat, 10000); // Heartbeat every 10s
            sendHeartbeat();
        });
        
        document.getElementById('sendBtn').addEventListener('click', sendMessage);
        document.getElementById('messageInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage(e);
        });
        
        // Handle window close
        window.addEventListener('beforeunload', () => {
            navigator.sendBeacon(`${backend}/leave/${roomCode}?user=${encodeURIComponent(userName)}`);
        });
    