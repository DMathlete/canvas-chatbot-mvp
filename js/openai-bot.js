let messageLog = [
  {
    role: "system",
    content: "You are a helpful calculus tutor. Always encourage the student to explain their thinking. Ask guiding questions. Don’t give the full answer immediately. Focus on understanding and strategy."
  }
];

let sessionId = "session_" + Math.random().toString(36).substr(2, 9);
let startTime = new Date();
let userId = "anonymous";
let userName = "anonymous";

/** ✅ Detect Canvas user automatically **/
async function getCanvasUser() {
  try {
    const response = await fetch("/api/v1/users/self", { credentials: "include" });
    if (!response.ok) throw new Error("Canvas API request failed");
    const userData = await response.json();
    console.log("✅ Canvas user detected:", userData);
    return {
      userId: userData.id,
      userName: userData.name
    };
  } catch (err) {
    console.warn("⚠️ Canvas API request failed, using manual entry.");
    return {
      userId: prompt("Enter your ID:"),
      userName: prompt("Enter your name:")
    };
  }
}

// ✅ Initialize user detection
window.addEventListener("load", async () => {
  if (window.self !== window.top) {
    // Running inside Canvas iframe
    const user = await getCanvasUser();
    userId = user.userId;
    userName = user.userName;
  } else {
    // Not inside Canvas
    userId = prompt("Enter your ID:");
    userName = prompt("Enter your name:");
  }
  console.log("✅ Final User Info:", { userId, userName });
});

/** ✅ Send a message **/
function sendMessage() {
  const inputBox = document.getElementById("userInput");
  const userText = inputBox.value.trim();
  if (!userText) return;

  appendMessage("user", userText);
  inputBox.value = "";
  messageLog.push({ role: "user", content: userText });

  getBotReply();
}

/** ✅ Allow Enter-to-send **/
document.getElementById("userInput").addEventListener("keypress", function (event) {
  if (event.key === "Enter") {
    event.preventDefault();
    sendMessage();
  }
});

/** ✅ Append message and render LaTeX **/
function appendMessage(role, text) {
  const chatBox = document.getElementById("chat");
  const msgDiv = document.createElement("div");
  msgDiv.className = "msg " + role;
  msgDiv.innerHTML = (role === "user" ? "<strong>You:</strong> " : "<strong>Tutor:</strong> ") + text;
  chatBox.appendChild(msgDiv);
  chatBox.scrollTop = chatBox.scrollHeight;

  // Re-render MathJax for LaTeX
  if (window.MathJax) {
    MathJax.typesetPromise([msgDiv]);
  }
}

/** ✅ Fetch GPT reply and log session **/
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

    // ✅ Build metadata for Firebase
    const metadata = {
      session_id: sessionId,
      user_id: userId,
      user_name: userName,
      user_message_count: messageLog.filter(m => m.role === "user").length,
      total_message_count: messageLog.length,
      start_time: startTime.toISOString(),
      end_time: new Date().toISOString(),
      topics: extractTopics(messageLog),
      messages: messageLog
    };

    // ✅ Log to Firestore
    await db.collection("chat_sessions").doc(sessionId).set(metadata, { merge: true });
    console.log("✅ Session metadata updated in Firebase:", metadata);

  } catch (error) {
    console.error("Chatbot error:", error);
    appendMessage("bot", "⚠️ Error: Could not process your request.");
  }
}

/** ✅ Extract topics **/
function extractTopics(log) {
  const text = log.map(m => m.content.toLowerCase()).join(" ");
  const topics = [];
  if (text.includes("derivative")) topics.push("Derivatives");
  if (text.includes("integral")) topics.push("Integrals");
  if (text.includes("limit")) topics.push("Limits");
  if (text.includes("vector")) topics.push("Vectors");
  return topics;
}
