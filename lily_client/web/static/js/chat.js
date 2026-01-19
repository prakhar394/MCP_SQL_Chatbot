
// Basic markdown configuration
if (window.marked) {
    marked.setOptions({
        breaks: true,
        gfm: true,
        headerIds: false,
        mangle: false
    });
}

const chatMessagesEl = document.getElementById("chatMessages");
const userInputEl = document.getElementById("userInput");
const chatFormEl = document.getElementById("chatForm");
const resetBtnEl = document.getElementById("resetChatBtn");
const timelineStatusEl = document.getElementById("timelineStatus");

let isStreaming = false;

/**
 * Smoothly scroll chat to bottom
 */
function scrollToBottom() {
    if (!chatMessagesEl) return;
    chatMessagesEl.scrollTo({
        top: chatMessagesEl.scrollHeight,
        behavior: 'smooth'
    });
}

/**
 * Create a message row DOM element
 */
function createMessage(role, htmlContent, meta = "") {
    const row = document.createElement("div");
    row.className = `message-row ${role === "user" ? "user" : "agent"}`;

    const avatar = document.createElement("div");
    avatar.className = `message-avatar ${role}`;
    avatar.textContent = role === "user" ? "You" : "PS";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    const content = document.createElement("div");
    content.className = "markdown-content";
    content.innerHTML = htmlContent;

    const metaRow = document.createElement("div");
    metaRow.className = "message-meta";

    const metaLeft = document.createElement("div");
    metaLeft.textContent = role === "user" ? "User" : "Agent";

    const metaRight = document.createElement("div");
    metaRight.className = "message-tools";
    metaRight.textContent = meta;

    metaRow.appendChild(metaLeft);
    metaRow.appendChild(metaRight);

    bubble.appendChild(content);
    bubble.appendChild(metaRow);

    row.appendChild(role === "user" ? bubble : avatar);
    row.appendChild(role === "user" ? avatar : bubble);

    return { row, content, metaRow, metaRight };
}

/**
 * Create a typing indicator row for the agent
 */
function createTypingIndicator() {
    const { row, metaRow } = createMessage("agent", "<strong>Thinking…</strong>");

    const typing = document.createElement("div");
    typing.className = "typing-indicator";
    typing.innerHTML = `
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
    `;
    metaRow.appendChild(typing);
    return { row, typing };
}

/**
 * Render the system introduction once
 */
function renderIntroMessage() {
    if (!chatMessagesEl) return;
    const introHtml = `
        <h2>👋 Welcome to the PartSelect Agent</h2>
        <p>
            I'm your focused assistant for <strong>refrigerator</strong> and <strong>dishwasher</strong> parts.
            I combine a retrieval system over repair guides and blogs with a structured parts catalog
            to answer your questions safely and accurately.
        </p>
        <p>You can ask me things like:</p>
        <ul>
            <li>"My GE fridge is leaking water inside. What could be wrong?"</li>
            <li>"How hard is it to install this drain pump? Do I need special tools?"</li>
            <li>"Show me compatible replacements for part number <code>PS11752778</code>."</li>
        </ul>
        <p>Ask your first question whenever you're ready.</p>
    `;
    const { row } = createMessage("agent", introHtml);
    chatMessagesEl.appendChild(row);
    scrollToBottom();
    
    // Focus input after intro loads
    setTimeout(() => {
        if (userInputEl) {
            userInputEl.focus();
        }
    }, 300);
}

/**
 * Update the right-hand timeline status text
 */
function updateTimelineStatus(phaseText) {
    if (!timelineStatusEl) return;
    timelineStatusEl.textContent = phaseText;
}

/**
 * Stream a response from the backend as SSE over a POST /api/chat request
 */
async function streamResponse(endpoint, payload, messageMetaLabel) {
    isStreaming = true;
    updateTimelineStatus("Agent is analyzing your query and retrieving relevant parts & repair docs…");

    // Disable input while streaming
    if (userInputEl) {
        userInputEl.disabled = true;
        userInputEl.placeholder = "Agent is thinking...";
    }

    const { row: typingRow, typing } = createTypingIndicator();
    chatMessagesEl.appendChild(typingRow);
    scrollToBottom();

    const { row: agentRow, content, metaRight } = createMessage("agent", "");
    chatMessagesEl.appendChild(agentRow);

    const startTime = new Date();
    let fullResponse = "";

    try {
        const response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!response.ok || !response.body) {
            throw new Error("Network error talking to agent backend.");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split("\n");
            buffer = lines.pop() || "";

            for (const raw of lines) {
                const line = raw.trim();
                if (!line.startsWith("data:")) continue;

                try {
                    const data = JSON.parse(line.slice(5).trim());
                    if (data.error) {
                        content.innerHTML = `<p style="color:#fecaca;">Error: ${data.error}</p>`;
                        updateTimelineStatus("Agent hit an error while processing. Try simplifying your question.");
                    } else if (data.response) {
                        fullResponse += data.response;
                        const endTime = new Date();
                        const seconds = ((endTime - startTime) / 1000).toFixed(1);
                        const html = window.marked ? marked.parse(fullResponse) : fullResponse;
                        content.innerHTML = html;
                        metaRight.textContent = `${messageMetaLabel} · ${seconds}s`;
                    }
                    scrollToBottom();
                } catch (err) {
                    console.error("Error parsing SSE data:", err);
                }
            }
        }

        if (fullResponse) {
            updateTimelineStatus("Run complete. Ask another question or refine your query.");
        }
    } catch (err) {
        console.error("Error streaming response:", err);
        content.innerHTML = `<p style="color:#fecaca;">Something went wrong while contacting the agent.</p>`;
        updateTimelineStatus("The agent could not complete this run. Please try again.");
    } finally {
        isStreaming = false;
        typing.remove();
        
        // Re-enable input
        if (userInputEl) {
            userInputEl.disabled = false;
            userInputEl.placeholder = "Describe your appliance problem or ask about a specific part...";
            userInputEl.focus();
        }
        
        scrollToBottom();
    }
}

/**
 * Handle primary send message flow
 */
async function handleSend(event) {
    event.preventDefault();
    if (!userInputEl || !userInputEl.value.trim() || isStreaming) return;

    const query = userInputEl.value.trim();
    userInputEl.value = "";
    userInputEl.style.height = "auto"; // Reset textarea height

    // Disable send button while streaming
    const sendBtn = document.getElementById("sendBtn");
    if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.style.opacity = "0.6";
    }

    const html = window.marked ? marked.parse(query) : query;
    const { row } = createMessage("user", html);
    chatMessagesEl.appendChild(row);
    scrollToBottom();

    try {
        await streamResponse("/api/chat", { query }, "Initial answer");
    } finally {
        // Re-enable send button
        if (sendBtn) {
            sendBtn.disabled = false;
            sendBtn.style.opacity = "1";
        }
    }
}

/**
 * Call backend to regenerate answer for the last user query
 * (simplified: we just reuse the text from the most recent user message)
 */
async function handleRegenerateLast() {
    if (isStreaming) return;

    const userMessages = Array.from(chatMessagesEl.querySelectorAll(".message-row.user"));
    if (!userMessages.length) return;

    const lastUser = userMessages[userMessages.length - 1];
    const textEl = lastUser.querySelector(".markdown-content");
    if (!textEl) return;

    const query = textEl.textContent.trim();
    if (!query) return;

    await streamResponse("/api/regenerate", { query }, "Regenerated answer");
}

/**
 * Reset conversation state server-side and re-render intro
 */
async function handleReset() {
    if (!confirm("Reset the conversation and clear history?")) return;
    if (!resetBtnEl) return;

    resetBtnEl.disabled = true;
    resetBtnEl.textContent = "Resetting…";

    try {
        const res = await fetch("/api/reset", { method: "POST" });
        const data = await res.json().catch(() => ({}));

        chatMessagesEl.innerHTML = "";
        renderIntroMessage();

        if (data && data.introduction) {
            const html = window.marked ? marked.parse(data.introduction) : data.introduction;
            const { row } = createMessage("agent", html);
            chatMessagesEl.appendChild(row);
        }

        updateTimelineStatus("Conversation cleared. Ask a new question to start a fresh agent run.");
    } catch (err) {
        console.error("Error resetting chat:", err);
    } finally {
        resetBtnEl.disabled = false;
        resetBtnEl.textContent = "Reset conversation";
    }
}

// Bootstrap on DOM ready
window.addEventListener("DOMContentLoaded", () => {
    if (chatFormEl) {
        chatFormEl.addEventListener("submit", handleSend);
    }
    if (resetBtnEl) {
        resetBtnEl.addEventListener("click", handleReset);
    }

    // Auto-resize textarea
    if (userInputEl) {
        userInputEl.addEventListener("input", () => {
            userInputEl.style.height = "auto";
            userInputEl.style.height = `${Math.min(userInputEl.scrollHeight, 150)}px`;
        });
    }

    // Keyboard shortcuts: Enter to send, Shift+Enter for new line
    if (userInputEl) {
        userInputEl.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                if (e.metaKey || e.ctrlKey || !isStreaming) {
                    e.preventDefault();
                    chatFormEl?.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
                }
            }
        });
    }

    // Double-click timeline panel to request regeneration of last answer
    const timelinePane = document.querySelector(".timeline-pane");
    if (timelinePane) {
        timelinePane.addEventListener("dblclick", handleRegenerateLast);
    }

    renderIntroMessage();
});
