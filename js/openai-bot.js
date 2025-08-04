let messageLog = [
  {
    role: "system",
    content: "You are a helpful calculus tutor. Always encourage the student to explain their thinking. Ask guiding questions. Don’t give the full answer immediately. Focus on understanding and strategy."
  }
];

let sessionId = "session_" + Math.random().toString(36).substr(2, 9);
let startTime = new Date();
let userId = prompt("Enter your name or ID:");

function sendMessage() {
  const inputBox = document.getElementById("userInput");
  const userText = inputBox.value.trim();
  if (!userText) return;

  appendMessage("user", userText);
  inputBox.value = "";
  messageLog.push({ role: "user", content: userText });

  getBotReply();
}

// ✅ Add Enter-to-Send & Shift+Enter for newline
document.getElementById("userInput").addEventListener("keydown", function (event) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault(); // Send message on Enter
    sendMessage();
  }
});

function appendMessage(role, text) {
  const chatBox = document.getElementById("chat");
  const msgDiv = document.createElement("div");
  msgDiv.className = "msg " + role;

  // ✅ Auto-format math in the message before displaying
  const processedText = autoFormatMath(text);

  msgDiv.innerHTML = (role === "user" ? "<strong>You:</strong> " : "<strong>Tutor:</strong> ") + processedText;
  chatBox.appendChild(msgDiv);
  chatBox.scrollTop = chatBox.scrollHeight;

  // ✅ Render LaTeX using MathJax
  if (window.MathJax) {
    MathJax.typesetPromise([msgDiv]);
  }
}

// ✅ Helper: Auto-wrap math-like content in LaTeX delimiters
function autoFormatMath(text) {
  // Detect LaTeX commands or math-like patterns
  const mathCommands = /\\[a-zA-Z]+/; // e.g., \int, \frac
  const exponentPattern = /\b[a-zA-Z0-9]+\^[a-zA-Z0-9]+\b/; // e.g., x^2
  const fractionPattern = /\b\d+\/\d+\b/; // e.g., 1/2

  // If text already has delimiters, return as is
  if (text.includes("\\(") || text.includes("$$")) return text;

  // If any math pattern detected, wrap it
  if (mathCommands.test(text) || exponentPattern.test(text) || fractionPattern.test(text)) {
    return `\\(${text}\\)`; // Inline math
  }

  return text; // No math detected
}

async function getBotReply() {
  try {
    const response = await fetch("https://chatbot-proxy-jsustaita02.replit.app/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: messageLog })
    });

    if (!response.ok) {
      appendMessage("bot", "⚠️ Error: Failed to reach tutor bot.");
      console.error("API error:", await response.text());
      return;
    }

    const data = await response.json();
    if (!data.choices || !data.choices[0]) {
      appendMessage("bot", "⚠️ Error: Invalid response from tutor bot.");
      console.error("Unexpected API response:", data);
      return;
    }

    const botReply = data.choices[0].message.content;
    messageLog.push({ role: "assistant", content: botReply });
    appendMessage("bot", botReply);

    // 🔥 Build metadata for Firebase
    const metadata = {
      session_id: sessionId,
      user_id: userId,
      user_message_count: messageLog.filter(m => m.role === "user").length, // Only count student messages
      total_message_count: messageLog.length,
      start_time: startTime.toISOString(),
      end_time: new Date().toISOString(),
      topics: extractTopics(messageLog),
      messages: messageLog
    };

    // ✅ Log or update session in Firebase
    await db.collection("chat_sessions").doc(sessionId).set(metadata, { merge: true });
    console.log("✅ Session metadata updated in Firebase:", metadata);

  } catch (error) {
    console.error("Chatbot error:", error);
    appendMessage("bot", "⚠️ Error: Could not process your request.");
  }
}

function extractTopics(log) {
  const text = log.map(m => m.content.toLowerCase()).join(" ");
  const topics = [];
  if (text.includes("derivative")) topics.push("Derivatives");
  if (text.includes("integral")) topics.push("Integrals");
  if (text.includes("limit")) topics.push("Limits");
  if (text.includes("vector")) topics.push("Vectors");
  return topics;
}
