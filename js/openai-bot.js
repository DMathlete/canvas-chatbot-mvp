/***********************
 *  CONFIG
 ***********************/
const FUNCTIONS_BASE = 'https://us-central1-canvaschatbot.cloudfunctions.net'; // <- your region+project
const BOT_PROXY_URL   = 'https://chatbot-proxy-jsustaita02.replit.app/chat';   // <- your Replit proxy

/***********************
 *  SESSION + USER
 ***********************/
let messageLog = [
  {
    role: "system",
    content: "You are a helpful multivariable calculus and linear algebra tutor. Always encourage the student to explain their thinking by asking guiding questions and focus on understanding and strategy. Format any lists as proper HTML ordered lists (<ol><li>Item</li></ol>)."
  }
];

let sessionId = "session_" + Math.random().toString(36).substr(2, 9);
let startTime = new Date();

// Prefer Canvas URL params if present, else ask once for an ID
const urlParams = new URLSearchParams(window.location.search);
let userId = urlParams.get("user_id");
let userName = urlParams.get("user_name");

if (!userId) {
  userId = prompt("Enter your student ID (or initials):") || "anonymous_user";
}
console.log("✅ User Detected:", { userId, userName });

// Format plain text / markdown-ish into HTML for chat
function formatForChat(text) {
  if (!text) return "";

  // 1) Escape HTML
  let esc = text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");

  // 2) Code fences ```...```
  esc = esc.replace(/```([\s\S]*?)```/g, (_, code) => {
    const html = code.replace(/\n/g, "<br>");
    return `<pre style="white-space:pre-wrap;"><code>${html}</code></pre>`;
  });

  // 3) Lists (ordered & unordered)
  const lines = esc.split(/\n/);
  const out = [];
  let i = 0;

  const isBullet = (s) => /^\s*[-*+]\s+/.test(s);
  const isNumber = (s) => /^\s*\d+[.)]\s+/.test(s);

  while (i < lines.length) {
    // Unordered list block
    if (isBullet(lines[i])) {
      out.push("<ul>");
      while (i < lines.length && isBullet(lines[i])) {
        out.push(`<li>${lines[i].replace(/^\s*[-*+]\s+/, "")}</li>`);
        i++;
      }
      out.push("</ul>");
      continue;
    }
    // Ordered list block
    if (isNumber(lines[i])) {
      out.push("<ol>");
      while (i < lines.length && isNumber(lines[i])) {
        out.push(`<li>${lines[i].replace(/^\s*\d+[.)]\s+/, "")}</li>`);
        i++;
      }
      out.push("</ol>");
      continue;
    }
    // Paragraph / line
    out.push(lines[i] === "" ? "<br>" : `${lines[i]}<br>`);
    i++;
  }

  return out.join("");
}

function appendMessage(role, text, opts = {}) {
  const chatBox = document.getElementById("chat");
  const msgDiv = document.createElement("div");
  msgDiv.className = "msg " + role;

  // format text for display (lists, line breaks, code)
  const formatted = formatForChat(text || "");

  msgDiv.innerHTML =
    (role === "user" ? "<strong>You:</strong> " : "<strong>Tutor:</strong> ") +
    formatted;

  // Render attachment preview/link if provided
  if (opts.attachment) {
    const att = opts.attachment;
    const wrap = document.createElement("div");
    wrap.style.marginTop = "6px";

    if (att.kind === "image") {
      const img = document.createElement("img");
      img.src = att.url;
      img.alt = att.filename || "uploaded image";
      img.style.maxWidth = "220px";
      img.style.border = "1px solid #ddd";
      img.style.borderRadius = "6px";
      img.style.display = "block";
      wrap.appendChild(img);
    } else {
      const a = document.createElement("a");
      a.href = att.url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = att.filename || "Download attachment";
      wrap.appendChild(a);
    }
    msgDiv.appendChild(wrap);
  }

  chatBox.appendChild(msgDiv);
  chatBox.scrollTop = chatBox.scrollHeight;

  // Re-render MathJax if present
  if (window.MathJax) {
    MathJax.typesetPromise([msgDiv]);
  }
}


/***********************
 *  FILE UPLOAD HELPERS
 ***********************/
async function getSignedUploadUrl(filename, contentType) {
  const u = new URL(`${FUNCTIONS_BASE}/getUploadUrl`);
  u.searchParams.set('filename', filename);
  u.searchParams.set('contentType', contentType || 'application/octet-stream');

  const res = await fetch(u.toString());
  if (!res.ok) throw new Error(`getUploadUrl failed: ${await res.text()}`);
  return res.json(); // { uploadUrl, objectName }
}

async function uploadToSignedUrl(uploadUrl, file) {
  const res = await fetch(uploadUrl, {
    method: 'PUT',
    headers: { 'Content-Type': file.type || 'application/octet-stream' },
    body: file
  });
  if (!res.ok) throw new Error(`PUT upload failed: ${await res.text()}`);
}

async function getSignedDownloadUrl(objectName) {
  const u = new URL(`${FUNCTIONS_BASE}/getDownloadUrl`);
  u.searchParams.set('object', objectName);

  const res = await fetch(u.toString());
  if (!res.ok) throw new Error(`getDownloadUrl failed: ${await res.text()}`);
  return res.json(); // { downloadUrl }
}

/***********************
 *  SEND MESSAGE
 ***********************/
async function sendMessage() {
  const inputBox = document.getElementById("userInput");
  const fileInput = document.getElementById("fileInput");
  const userText  = (inputBox.value || "").trim();
  const file      = (fileInput && fileInput.files && fileInput.files[0]) ? fileInput.files[0] : null;

  if (!userText && !file) return;

  try {
    let attachmentMeta = null;
    let textForBot = userText;

    // If a file is selected, upload via signed URL and show it
    if (file) {
      appendMessage("user", userText || "📎 Attaching a file...", {});

      // 1) get signed PUT URL
      const { uploadUrl, objectName } = await getSignedUploadUrl(file.name, file.type);

      // 2) upload file
      await uploadToSignedUrl(uploadUrl, file);

      // 3) get public download URL
      const { downloadUrl } = await getSignedDownloadUrl(objectName);

      // Clear file input
      fileInput.value = "";

      // Show preview/link in chat (as the user's message)
      const isImage = /^image\//i.test(file.type);
      attachmentMeta = { url: downloadUrl, filename: file.name, kind: isImage ? "image" : "file" };
      appendMessage("user", userText, { attachment: attachmentMeta });

      // Add a note to send to the bot so it knows there's a file reference
      textForBot = (userText ? userText + "\n\n" : "") + `Attached file: ${downloadUrl}`;
    } else {
      // No file, just text
      appendMessage("user", userText);
    }

    // Add to message log (the assistant will only see text + link)
    messageLog.push({ role: "user", content: textForBot });

    // Call your proxy for a reply
    const response = await fetch(BOT_PROXY_URL, {
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

    // Log/update session in Firestore
    await logSession();

  } catch (err) {
    console.error("sendMessage error:", err);
    appendMessage("bot", "⚠️ Error: Could not process your request.");
  } finally {
    // Clear text box
    inputBox.value = "";
  }
}

/***********************
 *  ENTER TO SEND
 ***********************/
document.getElementById("userInput").addEventListener("keypress", function (event) {
  if (event.key === "Enter") {
    event.preventDefault();
    sendMessage();
  }
});

/***********************
 *  TOPIC TAGGING
 ***********************/
function extractTopics(log) {
  const text = log.map(m => m.content.toLowerCase()).join(" ");
  const topics = [];
  if (text.includes("derivative")) topics.push("Derivatives");
  if (text.includes("integral")) topics.push("Integrals");
  if (text.includes("limit")) topics.push("Limits");
  if (text.includes("vector")) topics.push("Vectors");
  if (text.includes("theorem")) topics.push("Theorem");
  if (text.includes("dot product")) topics.push("Dot Product");
  if (text.includes("cross product")) topics.push("Cross Product");
  if (text.includes("plane")) topics.push("Planes");
  return topics;
}

/***********************
 *  FIREBASE LOGGING
 ***********************/
async function logSession() {
  try {
    const metadata = {
      session_id: sessionId,
      user_id: userId,
      user_name: userName || null,
      user_message_count: messageLog.filter(m => m.role === "user").length,
      total_message_count: messageLog.length,
      start_time: startTime.toISOString(),
      end_time: new Date().toISOString(),
      topics: extractTopics(messageLog),
      messages: messageLog
    };
    await db.collection("chat_sessions").doc(sessionId).set(metadata, { merge: true });
    console.log("✅ Session metadata updated in Firebase:", metadata);
  } catch (err) {
    console.error("❌ Error logging session to Firebase:", err);
  }
}

// Expose sendMessage for the Send button
window.sendMessage = sendMessage;
