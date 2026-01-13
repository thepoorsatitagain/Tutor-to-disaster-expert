"""
Web UI — Local browser-based interface for Expert-in-a-Box.

Simple Flask-based UI that runs locally.
No cloud dependencies.
"""

import json
import logging
from pathlib import Path
from typing import Optional

try:
    from flask import Flask, render_template_string, request, jsonify, send_from_directory
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

logger = logging.getLogger("expert-in-a-box.ui")

# HTML template (embedded to avoid external dependencies)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Expert-in-a-Box</title>
    <style>
        :root {
            --bg-primary: #0f1419;
            --bg-secondary: #1a1f2e;
            --bg-tertiary: #252b3b;
            --text-primary: #e7e9ea;
            --text-secondary: #8b98a5;
            --accent: #1d9bf0;
            --accent-hover: #1a8cd8;
            --warning: #f4a621;
            --danger: #f4212e;
            --success: #00ba7c;
            --border: #2f3542;
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        /* Header */
        .header {
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            padding: 1rem 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 {
            font-size: 1.25rem;
            font-weight: 600;
        }
        
        .mode-badge {
            background: var(--accent);
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .mode-badge.emergency {
            background: var(--danger);
        }
        
        .mode-badge.hybrid {
            background: var(--warning);
            color: var(--bg-primary);
        }
        
        /* Main container */
        .container {
            flex: 1;
            display: flex;
            flex-direction: column;
            max-width: 900px;
            margin: 0 auto;
            width: 100%;
            padding: 1rem;
        }
        
        /* Chat area */
        .chat-area {
            flex: 1;
            overflow-y: auto;
            padding: 1rem 0;
        }
        
        .message {
            margin-bottom: 1.5rem;
            animation: fadeIn 0.3s ease;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .message-header {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
        }
        
        .message-role {
            font-weight: 600;
            font-size: 0.875rem;
        }
        
        .message-role.user {
            color: var(--accent);
        }
        
        .message-role.assistant {
            color: var(--success);
        }
        
        .message-module {
            font-size: 0.75rem;
            color: var(--text-secondary);
            background: var(--bg-tertiary);
            padding: 0.125rem 0.5rem;
            border-radius: 4px;
        }
        
        .message-content {
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 1rem;
            line-height: 1.6;
        }
        
        .message.user .message-content {
            background: var(--bg-tertiary);
        }
        
        .message-caveats {
            margin-top: 0.75rem;
            padding: 0.75rem;
            background: rgba(244, 166, 33, 0.1);
            border-left: 3px solid var(--warning);
            border-radius: 0 8px 8px 0;
            font-size: 0.875rem;
            color: var(--warning);
        }
        
        /* Input area */
        .input-area {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 0.75rem;
            margin-top: 1rem;
        }
        
        .input-row {
            display: flex;
            gap: 0.75rem;
        }
        
        .input-field {
            flex: 1;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.75rem 1rem;
            color: var(--text-primary);
            font-size: 1rem;
            resize: none;
            min-height: 48px;
            max-height: 200px;
        }
        
        .input-field:focus {
            outline: none;
            border-color: var(--accent);
        }
        
        .send-button {
            background: var(--accent);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 0 1.5rem;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .send-button:hover {
            background: var(--accent-hover);
        }
        
        .send-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        /* Status bar */
        .status-bar {
            display: flex;
            gap: 1rem;
            padding: 0.5rem 0;
            font-size: 0.75rem;
            color: var(--text-secondary);
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 0.25rem;
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success);
        }
        
        .status-dot.offline {
            background: var(--danger);
        }
        
        /* Profile panel */
        .profile-panel {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        
        .profile-panel h3 {
            font-size: 0.875rem;
            margin-bottom: 0.75rem;
            color: var(--text-secondary);
        }
        
        .profile-options {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }
        
        .profile-option {
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.375rem 0.75rem;
            font-size: 0.75rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .profile-option:hover {
            border-color: var(--accent);
        }
        
        .profile-option.active {
            background: var(--accent);
            border-color: var(--accent);
            color: white;
        }
        
        /* Loading indicator */
        .loading {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--text-secondary);
            font-size: 0.875rem;
        }
        
        .loading-dots {
            display: flex;
            gap: 4px;
        }
        
        .loading-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--accent);
            animation: pulse 1.4s infinite ease-in-out;
        }
        
        .loading-dot:nth-child(1) { animation-delay: -0.32s; }
        .loading-dot:nth-child(2) { animation-delay: -0.16s; }
        
        @keyframes pulse {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }
        
        /* Responsive */
        @media (max-width: 600px) {
            .header {
                padding: 0.75rem 1rem;
            }
            
            .container {
                padding: 0.5rem;
            }
            
            .message-content {
                padding: 0.75rem;
            }
        }
    </style>
</head>
<body>
    <header class="header">
        <h1>📦 Expert-in-a-Box</h1>
        <span class="mode-badge" id="mode-badge">Education</span>
    </header>
    
    <main class="container">
        <!-- Profile selection -->
        <div class="profile-panel">
            <h3>Reading Level</h3>
            <div class="profile-options" id="reading-levels">
                <button class="profile-option" data-level="child">Child</button>
                <button class="profile-option" data-level="teen">Teen</button>
                <button class="profile-option active" data-level="general">General</button>
                <button class="profile-option" data-level="technical">Technical</button>
                <button class="profile-option" data-level="expert">Expert</button>
            </div>
        </div>
        
        <!-- Chat area -->
        <div class="chat-area" id="chat-area">
            <div class="message assistant">
                <div class="message-header">
                    <span class="message-role assistant">Assistant</span>
                </div>
                <div class="message-content">
                    Welcome to Expert-in-a-Box! I'm here to help with education and guidance.
                    How can I assist you today?
                </div>
            </div>
        </div>
        
        <!-- Input area -->
        <div class="input-area">
            <div class="status-bar">
                <div class="status-item">
                    <span class="status-dot" id="llm-status"></span>
                    <span id="llm-status-text">LLM Connected</span>
                </div>
                <div class="status-item">
                    <span>Module: </span>
                    <span id="active-module">education</span>
                </div>
            </div>
            <div class="input-row">
                <textarea 
                    class="input-field" 
                    id="message-input" 
                    placeholder="Ask a question..."
                    rows="1"
                ></textarea>
                <button class="send-button" id="send-button">Send</button>
            </div>
        </div>
    </main>
    
    <script>
        // State
        let sessionId = null;
        let readingLevel = 'general';
        let isLoading = false;
        
        // Elements
        const chatArea = document.getElementById('chat-area');
        const messageInput = document.getElementById('message-input');
        const sendButton = document.getElementById('send-button');
        const modeBadge = document.getElementById('mode-badge');
        const llmStatus = document.getElementById('llm-status');
        const llmStatusText = document.getElementById('llm-status-text');
        const activeModule = document.getElementById('active-module');
        const readingLevelButtons = document.querySelectorAll('[data-level]');
        
        // Initialize
        async function init() {
            const status = await fetchStatus();
            if (status) {
                updateStatus(status);
            }
        }
        
        // Fetch status
        async function fetchStatus() {
            try {
                const response = await fetch('/api/status');
                return await response.json();
            } catch (e) {
                console.error('Failed to fetch status:', e);
                return null;
            }
        }
        
        // Update UI with status
        function updateStatus(status) {
            // Mode badge
            modeBadge.textContent = status.mode.charAt(0).toUpperCase() + status.mode.slice(1);
            modeBadge.className = 'mode-badge ' + status.mode;
            
            // LLM status
            if (status.llm_available) {
                llmStatus.classList.remove('offline');
                llmStatusText.textContent = 'LLM Connected';
            } else {
                llmStatus.classList.add('offline');
                llmStatusText.textContent = 'LLM Offline (Mock Mode)';
            }
        }
        
        // Add message to chat
        function addMessage(role, content, module = null, caveats = null) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${role}`;
            
            let html = `
                <div class="message-header">
                    <span class="message-role ${role}">${role === 'user' ? 'You' : 'Assistant'}</span>
                    ${module ? `<span class="message-module">${module}</span>` : ''}
                </div>
                <div class="message-content">${escapeHtml(content)}</div>
            `;
            
            if (caveats && caveats.length > 0) {
                html += `<div class="message-caveats">⚠️ ${caveats.join(' • ')}</div>`;
            }
            
            messageDiv.innerHTML = html;
            chatArea.appendChild(messageDiv);
            chatArea.scrollTop = chatArea.scrollHeight;
        }
        
        // Add loading indicator
        function addLoading() {
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'message assistant';
            loadingDiv.id = 'loading-message';
            loadingDiv.innerHTML = `
                <div class="message-header">
                    <span class="message-role assistant">Assistant</span>
                </div>
                <div class="message-content">
                    <div class="loading">
                        <div class="loading-dots">
                            <div class="loading-dot"></div>
                            <div class="loading-dot"></div>
                            <div class="loading-dot"></div>
                        </div>
                        <span>Thinking...</span>
                    </div>
                </div>
            `;
            chatArea.appendChild(loadingDiv);
            chatArea.scrollTop = chatArea.scrollHeight;
        }
        
        // Remove loading indicator
        function removeLoading() {
            const loading = document.getElementById('loading-message');
            if (loading) loading.remove();
        }
        
        // Send message
        async function sendMessage() {
            const message = messageInput.value.trim();
            if (!message || isLoading) return;
            
            isLoading = true;
            sendButton.disabled = true;
            
            // Add user message
            addMessage('user', message);
            messageInput.value = '';
            messageInput.style.height = 'auto';
            
            // Show loading
            addLoading();
            
            try {
                const response = await fetch('/api/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: message,
                        session_id: sessionId,
                        reading_level: readingLevel
                    })
                });
                
                const data = await response.json();
                
                // Update session
                if (data.session_id) {
                    sessionId = data.session_id;
                }
                
                // Remove loading and add response
                removeLoading();
                addMessage('assistant', data.response, data.module, data.caveats);
                
                // Update module display
                if (data.module) {
                    activeModule.textContent = data.module;
                }
                
            } catch (e) {
                removeLoading();
                addMessage('assistant', 'Sorry, there was an error processing your request. Please try again.');
                console.error('Query failed:', e);
            }
            
            isLoading = false;
            sendButton.disabled = false;
            messageInput.focus();
        }
        
        // Escape HTML
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Event listeners
        sendButton.addEventListener('click', sendMessage);
        
        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        
        // Auto-resize textarea
        messageInput.addEventListener('input', () => {
            messageInput.style.height = 'auto';
            messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + 'px';
        });
        
        // Reading level selection
        readingLevelButtons.forEach(button => {
            button.addEventListener('click', () => {
                readingLevelButtons.forEach(b => b.classList.remove('active'));
                button.classList.add('active');
                readingLevel = button.dataset.level;
            });
        });
        
        // Initialize
        init();
    </script>
</body>
</html>
'''


def create_app(expert_app):
    """Create Flask application."""
    if not FLASK_AVAILABLE:
        raise ImportError("Flask not installed. Run: pip install flask")
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'expert-in-a-box-dev-key'
    
    @app.route('/')
    def index():
        return render_template_string(HTML_TEMPLATE)
    
    @app.route('/api/status')
    def status():
        return jsonify(expert_app.get_status())
    
    @app.route('/api/query', methods=['POST'])
    def query():
        data = request.get_json()
        
        message = data.get('message', '')
        session_id = data.get('session_id')
        reading_level = data.get('reading_level', 'general')
        
        # Update profile if reading level changed
        if reading_level:
            expert_app.profile.load({
                "reading_level": reading_level,
                "format_preference": "conversational"
            })
        
        result = expert_app.query(message, session_id=session_id)
        return jsonify(result)
    
    @app.route('/api/mode', methods=['POST'])
    def switch_mode():
        data = request.get_json()
        target_mode = data.get('mode')
        key = data.get('key')
        
        result = expert_app.switch_mode(target_mode, key)
        return jsonify(result)
    
    @app.route('/api/profile', methods=['POST'])
    def load_profile():
        data = request.get_json()
        
        result = expert_app.profile.load(data)
        return jsonify({
            "success": result.valid,
            "error": result.error,
            "warnings": result.warnings
        })
    
    @app.route('/api/audit')
    def get_audit():
        event_types = request.args.get('types', '').split(',') if request.args.get('types') else None
        limit = int(request.args.get('limit', 100))
        
        events = expert_app.audit.query(event_types=event_types, limit=limit)
        return jsonify({
            "events": [e.to_dict() for e in events]
        })
    
    return app


def start_server(expert_app, host: str = "0.0.0.0", port: int = 8080):
    """Start the web server."""
    if not FLASK_AVAILABLE:
        logger.error("Flask not installed. Run: pip install flask")
        print("\n❌ Flask not installed.")
        print("Install with: pip install flask")
        return
    
    app = create_app(expert_app)
    
    print(f"\n🚀 Expert-in-a-Box Web UI")
    print(f"   Open http://localhost:{port} in your browser")
    print(f"   Press Ctrl+C to stop\n")
    
    app.run(host=host, port=port, debug=False)
