document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chatForm');
    const messageInput = document.getElementById('messageInput');
    const chatMessages = document.getElementById('chatMessages');
    const typingIndicator = document.getElementById('typingIndicator');
    const confidenceIndicator = document.getElementById('confidenceIndicator');
    const confidenceScore = document.getElementById('confidenceScore');

    chatForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const message = messageInput.value.trim();
        if (!message) return;

        // Add user message
        addMessage(message, 'user');
        messageInput.value = '';

        // Show typing indicator
        typingIndicator.classList.remove('d-none');

        try {
            const response = await fetch(`/chat/course/${courseId}/send/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ message: message })
            });

            const data = await response.json();
            
            // Add bot response
            addMessage(data.bot_message, 'bot');
            confidenceScore.textContent = (data.confidence * 100).toFixed(0) + '%';
            confidenceIndicator.classList.remove('d-none');
            
        } catch (error) {
            addMessage('Sorry, I encountered an error. Please try again.', 'bot');
        } finally {
            typingIndicator.classList.add('d-none');
        }
    });

    function addMessage(content, type) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message mb-3`;
        
        messageDiv.innerHTML = `
            <div class="message-content p-3 rounded shadow-sm">
                <div class="message-text">${content}</div>
            </div>
            <small class="text-muted mt-1">${new Date().toLocaleTimeString()}</small>
        `;
        
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Focus input
    messageInput.focus();
});
