let messageLog = [
  {
    role: "system",
    content: "You are a helpful calculus tutor. Always encourage the student to explain their thinking. Ask guiding questions. Don’t give the full answer immediately. Focus on understanding and strategy."
  }
];

let sessionId = "session_" + Math.random().toString(36).substr(2, 9);
let startTime = new Date();
let userId = prompt("Enter your ID:"); // Single prompt only

console.log("✅ User ID Detected:", userId);

// Handle Send Message
function sendMessage() {
  const inputBox = document.getElementById("userInput");
  const userText = inputBox.value.trim();
  if (!userText) return;

  appendMessage("user", userText);
  inputBox.value = "";
  messageLog.push({ role: "user", content: userText });

  getBotReply();
}

// Allow pressing "Enter" to send
document.getElementById("userInput").addEventListener("keypress", function (event) {
  if (event.key === "Enter") {
    event.preventDefault();
    sendMessage();
  }
});

// Append messages with LaTeX rendering
function appendMessage(role, text) {
  const chatBox = document.getElementById("chat");
  const msgDiv = document.createElement("div");
  msgDiv.className = "msg " + (role === "user" ? "user" : "bot");
  msgDiv.innerHTML = (role === "user" ? "<strong>You:</strong> " : "<strong>Tutor:</strong> ") + text;
  chatBox.appendChild(msgDiv);
  chatBox.scrollTop = chatBox.scrollHeight;

  if (window.MathJax) MathJax.typesetPromise([msgDiv]);
}

// Handle File Upload
document.getElementById("fileUpload").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (file) {
    const fileURL = await uploadFileToFirebase(file);
    appendMessage("user", `📎 Uploaded file: <a href="${fileURL}" target="_blank">${file.name}</a>`);
    messageLog.push({ role: "user", content: `File uploaded: ${fileURL}` });
    getBotReply();
  }
});

// Upload File to Firebase Storage
async function uploadFileToFirebase(file) {
  const storageRef = firebase.storage().ref(`uploads/${sessionId}/${file.name}`);
  await storageRef.put(file);
  return await storageRef.getDownloadURL();
}

// Get Bot Reply & Log Session
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
    const botReply = data.choices[0].message.content;
    messageLog.push({ role: "assistant", content: botReply });
    appendMessage("bot", botReply);

    // Log to Firestore
    const metadata = {
      session_id: sessionId,
      user_id: userId,
      user_message_count: messageLog.filter(m => m.role === "user").length,
      total_message_count: messageLog.length,
      start_time: startTime.toISOString(),
      end_time: new Date().toISOString(),
      topics: extractTopics(messageLog),
      messages: messageLog,
    };

    await db.collection("chat_sessions").doc(sessionId).set(metadata, { merge: true });
    console.log("✅ Session metadata updated:", metadata);

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
