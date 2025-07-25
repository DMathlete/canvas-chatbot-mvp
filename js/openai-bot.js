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

  getBotReply(userText);
}

function appendMessage(role, text) {
  const chatBox = document.getElementById("chat");
  const msgDiv = document.createElement("div");
  msgDiv.className = "msg " + role;
  msgDiv.textContent = (role === "user" ? "You: " : "Tutor: ") + text;
  chatBox.appendChild(msgDiv);
  chatBox.scrollTop = chatBox.scrollHeight;
}

async function getBotReply(userMessage) {
  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + OPENAI_API_KEY
    },
    body: JSON.stringify({
      model: "gpt-3.5-turbo",
      messages: messageLog,
      temperature: 0.7
    })
  });

  const data = await response.json();
  const botReply = data.choices[0].message.content;
  messageLog.push({ role: "assistant", content: botReply });
  appendMessage("bot", botReply);

  const metadata = {
    session_id: sessionId,
    user_id: userId,
    message_count: messageLog.length,
    start_time: startTime.toISOString(),
    end_time: new Date().toISOString(),
    topics: extractTopics(messageLog),
    messages: messageLog
  };

  logSessionDataToFirebase(metadata);
}

function extractTopics(log) {
  const text = log.map(m => m.content.toLowerCase()).join(" ");
  const topics = [];
  if (text.includes("derivative")) topics.push("Derivatives");
  if (text.includes("integral")) topics.push("Integrals");
  if (text.includes("limit")) topics.push("Limits");
  return topics;
}
