let messageLog = [];
let sessionId = "session_" + Math.random().toString(36).substr(2, 9);
let userId = "anon_" + Math.floor(Math.random() * 1000);
let startTime = new Date();

function sendMessage() {
  const inputBox = document.getElementById("userInput");
  const userText = inputBox.value.trim();
  if (!userText) return;

  appendMessage("user", userText);
  inputBox.value = "";

  messageLog.push({ role: "user", content: userText });

  let botResponse = "This is a demo response to: " + userText;

  setTimeout(() => {
    appendMessage("bot", botResponse);
    messageLog.push({ role: "bot", content: botResponse });
    logSessionData();
  }, 500);
}

function appendMessage(role, text) {
  const chatBox = document.getElementById("chat");
  const msgDiv = document.createElement("div");
  msgDiv.className = "msg " + role;
  msgDiv.textContent = (role === "user" ? "You: " : "Bot: ") + text;
  chatBox.appendChild(msgDiv);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function logSessionData() {
  const endTime = new Date();
  const metadata = {
    session_id: sessionId,
    user_id: userId,
    message_count: messageLog.length,
    start_time: startTime.toISOString(),
    end_time: endTime.toISOString(),
    topics: extractTopics(),
  };
  console.log("Session Metadata:", metadata);
  // In production, send metadata to Firebase or your backend
}

function extractTopics() {
  const text = messageLog.map(m => m.content).join(" ").toLowerCase();
  const topics = [];
  if (text.includes("derivative")) topics.push("Derivatives");
  if (text.includes("integral")) topics.push("Integrals");
  if (text.includes("limit")) topics.push("Limits");
  return topics;
}