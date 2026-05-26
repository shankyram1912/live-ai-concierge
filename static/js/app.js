import { startAudioPlayerWorklet } from "./audio-player.js";
import { startAudioRecorderWorklet } from "./audio-recorder.js";

// Connection mapping required by ADK Backend
const userId = "demo-user";
const sessionId = "demo-session-" + Math.random().toString(36).substring(7);
let websocket = null;
let isConnected = false;
let isConnecting = false;

// Hardware Nodes
let audioPlayerNode;
let audioPlayerContext;
let audioRecorderNode;
let audioRecorderContext;
let micStream;

// Premium UI DOM Elements
const orbContainer = document.getElementById('orb-state');
const micText = document.getElementById('mic-text');
const socketStatus = document.getElementById('socket-status');
const orbButton = document.getElementById('orb-button');
const transcriptUser = document.getElementById('transcript-user');
const transcriptAi = document.getElementById('transcript-ai');
// End Button Elements
const endBtnContainer = document.getElementById('end-btn-container');
const endBtn = document.getElementById('end-btn');

const chatContainer = document.getElementById('chat-container');

const chatInput = document.getElementById('chat-input');
const chatSendBtn = document.getElementById('chat-send-btn');

// --- Advanced Multimodal Chat Logic ---
const fileInput = document.getElementById('chat-file-input');
const attachBtn = document.getElementById('chat-attach-btn');
const previewContainer = document.getElementById('chat-preview-container');
const previewList = document.getElementById('chat-preview-list');
const clearAllBtn = document.getElementById('chat-preview-clear-all');

// --- UI HELPERS ---

/**
 * Updates the glowing orb animation and text status.
 */
function setAgentState(state) {
    if (!orbContainer || !micText) return;
    
    // Reset classes
    orbContainer.className = 'orb-container';
    orbContainer.classList.add(`state-${state.toLowerCase()}`);
    
    const textMap = { 
        'IDLE': 'Tap to Connect', 
        'LISTENING': 'Listening...',
        'THINKING': 'Thinking...',
        'SPEAKING': 'Speaking...'
    };
    micText.innerText = textMap[state];
}

/**
 * Updates the connection status badge and resets the UI for a new session.
 */
function updateConnectionStatus(connected) {
    // Re-query these elements here to ensure they aren't null
    const statusBadge = document.getElementById('socket-status');
    const endContainer = document.getElementById('end-btn-container');

    if (connected) {
        if (statusBadge) {
            statusBadge.innerText = 'Online';
            statusBadge.classList.add('active');
        }
        setAgentState('LISTENING');
        
        // FORCING VISIBILITY HERE
        if (endContainer) {
            endContainer.style.opacity = "1";
            endContainer.style.pointerEvents = "auto";
            endContainer.classList.add('visible');
        }

        // Show Chat
        if (chatContainer) chatContainer.classList.add('visible');

        transcriptUser.innerText = "";
        transcriptAi.innerText = "";
    } else {
        if (statusBadge) {
            statusBadge.innerText = 'Offline';
            statusBadge.classList.remove('active');
        }
        setAgentState('IDLE');
        
        // HIDING HERE
        if (endContainer) {
            endContainer.style.opacity = "0";
            endContainer.style.pointerEvents = "none";
            endContainer.classList.remove('visible');
        }

        // Hide Chat
        if (chatContainer) chatContainer.classList.remove('visible');
        
        transcriptUser.innerText = "Press connect, then speak...";
        transcriptAi.innerText = "";
    }
}

/**
 * Decodes Base64 audio strings from the ADK payload into raw binary 
 * buffers that the AudioWorklet processor requires.
 */
function base64ToArray(base64) {
    let standardBase64 = base64.replace(/-/g, '+').replace(/_/g, '/');
    while (standardBase64.length % 4) standardBase64 += '=';
    
    const binaryString = window.atob(standardBase64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
}

/**
 * Cleans up spacing anomalies that can occur when the model 
 * streams CJK (Chinese, Japanese, Korean) characters.
 */
function cleanCJKSpaces(text) {
    const cjkPattern = /[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf\uff00-\uffef]/;
    return text.replace(/(\S)\s+(?=\S)/g, (match, char1) => {
        const nextCharMatch = text.match(new RegExp(char1 + '\\s+(.)', 'g'));
        if (nextCharMatch && nextCharMatch.length > 0) {
            const char2 = nextCharMatch[0].slice(-1);
            if (cjkPattern.test(char1) && cjkPattern.test(char2)) return char1;
        }
        return match;
    });
}

// --- CORE WEBSOCKET ROUTING ---

/**
 * Callback function passed to the Audio Recorder Worklet. 
 * Fires continuously to send raw mic chunks to the FastAPI backend.
 */
function audioRecorderHandler(pcmData) {
    if (websocket && websocket.readyState === WebSocket.OPEN && isConnected) {
        websocket.send(pcmData);
    }
}

/**
 * Primary connection function bound to the UI's Connect Button.
 */
async function connectWebsocket() {
    if (isConnected || isConnecting) return; // Prevent double-taps
    // 1. Validate Agent Selection
    const agentSelect = document.getElementById('agent-select');
    const agentName = agentSelect ? agentSelect.value : "";

    if (!agentName) {
        alert("Please select a valid Agent from the settings panel before connecting.");
        return;
    }

    // 2. Set the lock
    isConnecting = true;
    updateConnectionStatus(false);

    // 3. Initialize ADK Hardware AudioWorklets (Handles Mic & Speakers)
    try {
        const [pNode, pCtx] = await startAudioPlayerWorklet();
        audioPlayerNode = pNode;
        audioPlayerContext = pCtx;

        // Listner to update Orb state after full audio playback from HW
        audioPlayerNode.port.onmessage = (event) => {
            console.log("4. MAIN THREAD: Caught flare from Worklet!", event.data);
            if (event.data.command === 'playbackComplete') {
                setAgentState('LISTENING');
            }
        };      

        const [rNode, rCtx, stream] = await startAudioRecorderWorklet(audioRecorderHandler);
        audioRecorderNode = rNode;
        audioRecorderContext = rCtx;
        micStream = stream;
    } catch (err) {
        // --- Path C: Hardware/Permission Error ---
        alert("Connection failed: " + err.message);
        console.error(err);
        
        // CRITICAL: Clean up any half-started hardware
        if (micStream) micStream.getTracks().forEach(t => t.stop());
        
        isConnecting = false; // Reset lock so user can try again
        return;
    }

    // 4. Connect to ADK FastAPI WebSocket Route

    // Get settings from the UI
    const voice = document.getElementById('voice-select').value;
    const affectiveDialog = document.getElementById('affective-toggle').classList.contains('active');
    const proactiveAudio = document.getElementById('proactive-toggle').classList.contains('active');

    // Build query parameters safely
    const params = new URLSearchParams({
        voice: voice,
        affective_dialog: affectiveDialog,
        proactive_audio: proactiveAudio
    });

    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    
    // UPDATED RESTful URL Path mapping back to main.py dynamically
    const wsUrl = `${wsProtocol}//${window.location.host}/live-ai-concierge/ws/${agentName}/${userId}/${sessionId}?${params.toString()}`;
    
    websocket = new WebSocket(wsUrl);

    // Force binary messages to be ArrayBuffers, not Blobs, to receive audio stream directly. 
    // Does not affect Text Frames, only Binary Frames at the network protocol level.
    websocket.binaryType = "arraybuffer";    

    websocket.onopen = function () {
        isConnected = true;
        isConnecting = false;
        updateConnectionStatus(true);
    };

    let aiTurnActive = false;  

    websocket.onmessage = function (event) {
        // --- 1. INTERCEPT RAW BINARY AUDIO (Synchronous!) ---
        if (event.data instanceof ArrayBuffer) {
            if (audioPlayerNode) {
                // Send raw bytes straight to the worklet!
                audioPlayerNode.port.postMessage(event.data);
                setAgentState('SPEAKING');
            }
            return; // Stop processing this event, it's just audio.
        }

        // --- 2. EXISTING: PARSE JSON FOR EVERYTHING ELSE ---
        let adkEvent;
        try {
            adkEvent = JSON.parse(event.data);
        } catch (error) {
            console.warn("Received non-JSON payload, ignoring:", event.data);
            return; // Fail gracefully
        }

        // ==========================================
        // EXTRACT DATA FIRST
        // ==========================================

        // -- User transcription --
        if (adkEvent.inputTranscription && adkEvent.inputTranscription.text) {
            let text = cleanCJKSpaces(adkEvent.inputTranscription.text);
            if (adkEvent.inputTranscription.finished) {                
                transcriptUser.innerText = `"${text}"`;
            } else {
                setAgentState('THINKING');
                transcriptUser.innerText = `"${text}..."`;
            }
        }

        // -- AI transcription --
        if (adkEvent.outputTranscription && adkEvent.outputTranscription.text) {
            const aiText = cleanCJKSpaces(adkEvent.outputTranscription.text);
            
            // Check if this is the final event (contains full string)
            if (adkEvent.outputTranscription.finished || !adkEvent.partial) {
                transcriptAi.innerText = aiText; // Overwrite to prevent duplication
            } else if (!aiTurnActive) {
                transcriptAi.innerText = aiText;
                aiTurnActive = true;
            } else {
                transcriptAi.innerText += aiText;
            }
        }        

        // 1. Safely check if the event contains 'content' and 'parts'
        if (adkEvent.content?.parts) {
            
            // 2. Loop through the parts (Gemini can sometimes return multiple tool calls in one event)
            adkEvent.content.parts.forEach((part, index) => {
                
                // 3A. Check if this part is a function call
                if (part.functionCall) {
                    // Define tools for logging
                    const logTools = [
                        "finalize_order",
                        "retrieve_orders"                      
                    ];
                    // Log tool call requests
                    if (logTools.includes(part.functionCall.name)) {
                        window.logToolUse(part.functionCall.name, true, part.functionCall.args || {});
                    }
                                        
                }

                // 3B. Check if this part is a function response
                if (part.functionResponse) {
                    
                    // Define tools for logging
                    const logTools = [
                        "finalize_order",
                        "retrieve_orders"                         
                    ];
                    // Log tool call requests
                    if (logTools.includes(part.functionResponse.name)) {
                        window.logToolUse(part.functionResponse.name, false, part.functionResponse.response || {});
                    }

                    // Refresh table when an order is finalized ---
                    if (part.functionResponse.name === "finalize_order") {
                        if (typeof window.refreshOrdersTable === 'function') {
                            window.refreshOrdersTable();
                        }
                    }                    
                }
            });
        }

        // -- Audio playback --
        if (adkEvent.content && adkEvent.content.parts) {
            const audioParts = adkEvent.content.parts.filter(
                p => p.inlineData && p.inlineData.mimeType.startsWith("audio/pcm")
            );
            if (audioParts.length > 0 && audioPlayerNode) {
                for (const part of audioParts) {
                    audioPlayerNode.port.postMessage(base64ToArray(part.inlineData.data));
                }
                setAgentState('SPEAKING');
            }
        }

        // ==========================================
        // MANAGE STATE LAST
        // ==========================================

        // -- Turn complete --
        if (adkEvent.turnComplete) {
            // TRACER 1: Did the backend tell us the AI finished?
            console.log("1. MAIN THREAD: turnComplete received. Sending endOfTurn to Worklet.");            
            aiTurnActive = false;  // next AI chunk will start fresh
            if (audioPlayerNode) {
                // Tell the worklet to flush its buffer and report back
                audioPlayerNode.port.postMessage({ command: 'endOfTurn' });
            } else {
                // Fallback just in case hardware is missing
                setAgentState('LISTENING');
            }            
        }

        // -- Interruption --
        if (adkEvent.interrupted) {
            if (audioPlayerNode) {
                audioPlayerNode.port.postMessage({ command: "endOfAudio" });
            }
            aiTurnActive = false; // Reset so the next AI response starts fresh
            setAgentState('LISTENING');
        }
    };

    websocket.onclose = function () {
        isConnected = false; // FIX: Allows the user to reconnect without refreshing!
        isConnecting = false;
        updateConnectionStatus(false);
        
        // Release hardware resources
        if (micStream) {
            micStream.getTracks().forEach(track => track.stop());
            micStream = null;
        }

        // 🛑 CRITICAL: Release Web Audio API Contexts
        if (audioPlayerContext && audioPlayerContext.state !== 'closed') {
            audioPlayerContext.close();
        }

        if (audioRecorderContext && audioRecorderContext.state !== 'closed') {
            audioRecorderContext.close();
        }        
    };

}

// ==========================================
// Text Chat Logic
// ==========================================

// Local tracking state for stage management
// State tracking array for multi-file upload stages
let pendingImages = [];

// 1. Trigger OS File Selection Dialog Box
if (attachBtn && fileInput) {
    attachBtn.onclick = () => fileInput.click();
}

// 2. Intercept Chosen Files and Compile into Memory Cache Arrays
if (fileInput) {
    fileInput.addEventListener('change', () => {
        const files = Array.from(fileInput.files);
        if (files.length === 0) return;

        let processedCount = 0;

        files.forEach(file => {
            const reader = new FileReader();
            reader.onload = function(event) {
                const dataUrl = event.target.result;
                const base64Data = dataUrl.split(',')[1]; 

                // Push compiled metadata object into local array pipeline
                pendingImages.push({
                    mimeType: file.type,
                    data: base64Data,
                    name: file.name,
                    src: dataUrl
                });

                processedCount++;

                // Trigger DOM render engine only after all selected files are processed
                if (processedCount === files.length) {
                    renderMultiPreview();
                }
            };
            reader.readAsDataURL(file);
        });
    });
}

// 3. Dynamic Multi-Thumbnail DOM Construction Engine
function renderMultiPreview() {
    if (!previewList || !previewContainer) return;
    
    // Reset layout slate completely to prevent duplication compounding
    previewList.innerHTML = '';

    // If queue is completely wiped out, hide container and exit early
    if (pendingImages.length === 0) {
        previewContainer.style.display = 'none';
        if (fileInput) fileInput.value = '';
        return;
    }

    // Build functional thumbnail card grids for each item currently held in state arrays
    pendingImages.forEach((imgObj, index) => {
        const itemWrapper = document.createElement('div');
        itemWrapper.style.cssText = `
            position: relative;
            width: 48px;
            height: 48px;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.15);
            flex-shrink: 0;
            background: rgba(0,0,0,0.4);
        `;

        itemWrapper.innerHTML = `
            <img src="${imgObj.src}" style="width:100%; height:100%; object-fit:cover; border-radius:7px;" title="${imgObj.name}" />
            <button class="remove-single-img" style="
                position: absolute;
                top: -6px;
                right: -6px;
                width: 16px;
                height: 16px;
                border-radius: 50%;
                background: var(--apple-red);
                color: white;
                border: none;
                font-size: 11px;
                font-weight: bold;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 2px 4px rgba(0,0,0,0.5);
            ">&times;</button>
        `;

        // Map individual inline image slicing deletion handler loops
        itemWrapper.querySelector('.remove-single-img').onclick = (e) => {
            e.stopPropagation();
            pendingImages.splice(index, 1);
            renderMultiPreview(); // Refresh interface rows dynamically
        };

        previewList.appendChild(itemWrapper);
    });

    // Animate display open
    previewContainer.style.display = 'flex';
}

// 4. Global Structural Clear-All Functionality Hook
if (clearAllBtn) {
    clearAllBtn.onclick = (e) => {
        if (e) e.stopPropagation();
        pendingImages = [];
        renderMultiPreview();
    };
}

// 5. Coordinated Multi-Payload Message Submitter Transmission Pipeline
function sendChatMessage() {
    const text = chatInput.value.trim();
    
    if (!text && pendingImages.length === 0) return;

    // Check if WebSocket instance connection stream is explicitly live
    if (websocket && websocket.readyState === WebSocket.OPEN && isConnected) {
        
        // Step A: Dispatch the entire multi-image cluster frame array payload first
        if (pendingImages.length > 0) {
            websocket.send(JSON.stringify({
                type: "multi-image",
                images: pendingImages.map(img => ({
                    mimeType: img.mimeType,
                    data: img.data
                }))
            }));
            
            if (transcriptUser) {
                transcriptUser.innerText = `[Sent ${pendingImages.length} Image Attachment(s)]`;
            }
        }

        // Step B: Send text context instruction data frame immediately after
        if (text) {
            websocket.send(JSON.stringify({
                type: "text",
                text: text
            }));
            if (transcriptUser) {
                transcriptUser.innerText = `"${text}"`;
            }
        }

        // Step C: Flush input elements and completely wipe staging variables clean
        chatInput.value = "";
        pendingImages = [];
        renderMultiPreview();
    }
}

// 6. Bind New Unified Logic Framework back onto core event triggers
if (chatSendBtn) {
    chatSendBtn.onclick = sendChatMessage;
}

if (chatInput) {
    // Prevent default enter behavior to prevent broken whitespace line breaks
    chatInput.onkeydown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault(); 
            sendChatMessage();
        }
    };
}

// ==========================================
// Session Termination Logic
// ==========================================
function endSession() {
    if (websocket && isConnected) {
        websocket.close(); // This automatically triggers websocket.onclose!
    }
}

// Bind connection and termination to buttons
if (orbButton) {
    orbButton.addEventListener('click', connectWebsocket);
}
if (endBtn) {
    endBtn.addEventListener('click', endSession);
}