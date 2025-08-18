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
    content:
      "You are a helpful multivariable calculus and linear algebra tutor. Always encourage the student to explain their thinking by asking guiding questions and focus on understanding and strategy."
  }
];

let sessionId = "session_" + Math.random().toString(36).substr(2, 9);
let startTime = new Date();

let userId = prompt("Enter your C-number:") || "anonymous_user";
let userName = null;

// Prefer Canvas URL params if present, else ask once for an ID
/*const urlParams = new URLSearchParams(window.location.search);
let userId = urlParams.get("user_id");
let userName = urlParams.get("user_name");

if (!userId) {
  userId = prompt("Enter your C-number:") || "anonymous_user";
}
console.log("✅ User Detected:", { userId, userName });

/***********************
 *  MARKDOWN + MATHJAX
 ***********************/
/** Configure marked for nice lists + line breaks */
if (window.marked) {
  marked.setOptions({
    gfm: true,
    breaks: true,
    mangle: false,
    headerIds: false
  });
}

/**
 * Protect math segments ($...$, $$...$$, \(...\), \[...\]) so the Markdown
 * parser doesn’t mangle them. We replace them with tokens, then restore.
 */
function protectMath(text) {
  const tokens = [];
  let idx = 0;

  // Order matters: handle display first, then inline
  const patterns = [
    { re: /\$\$([\s\S]+?)\$\$/g, wrap: (m) => ({ raw: m }) },
    { re: /\\\[((?:.|\n)+?)\\\]/g, wrap: (m) => ({ raw: m }) },
    // inline $...$ (avoid \$, and don't match $$...$$ which is already handled)
    { re: /(?<!\\)\$([^\n][\s\S]*?)(?<!\\)\$/g, wrap: (m) => ({ raw: m }) },
    { re: /\\\(([\s\S]+?)\\\)/g, wrap: (m) => ({ raw: m }) }
  ];

  let protectedText = text;

  for (const { re, wrap } of patterns) {
    protectedText = protectedText.replace(re, (match) => {
      const key = `[[MATH${idx}]]`;
      tokens.push(wrap(match));
      idx++;
      return key;
    });
  }

  return { protectedText, tokens };
}

function restoreMath(html, tokens) {
  let out = html;
  tokens.forEach((tok, i) => {
    const key = `[[MATH${i}]]`;
    out = out.replace(key, tok.raw);
  });
  return out;
}

/** Render Markdown but preserve MathJax delimiters. */
function renderMarkdownWithMath(text) {
  if (!text) return "";
  const { protectedText, tokens } = protectMath(text);
  const mdHtml = window.marked ? marked.parse(protectedText) : protectedText;
  return restoreMath(mdHtml, tokens);
}

/***********************
 *  DOM HELPERS
 ***********************/
function appendMessage(role, text, opts = {}) {
  const chatBox = document.getElementById("chat");
  const msgDiv = document.createElement("div");
  msgDiv.className = "msg " + role;

  // Markdown + MathJax pipeline
  const formatted = renderMarkdownWithMath(text || "");

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

  // Render MathJax (LaTeX) if present
  if (window.MathJax) {
    MathJax.typesetPromise([msgDiv]);
  }
}

/***********************
 *  FILE UPLOAD HELPERS
 ***********************/
async function getSignedUploadUrl(filename, contentType) {
  const u = new URL(`${FUNCTIONS_BASE}/getUploadUrl`);
  u.searchParams.set("filename", filename);
  u.searchParams.set("contentType", contentType || "application/octet-stream");

  const res = await fetch(u.toString());
  if (!res.ok) throw new Error(`getUploadUrl failed: ${await res.text()}`);
  return res.json(); // { uploadUrl, objectName }
}

async function uploadToSignedUrl(uploadUrl, file) {
  const res = await fetch(uploadUrl, {
    method: "PUT",
    headers: { "Content-Type": file.type || "application/octet-stream" },
    body: file
  });
  if (!res.ok) throw new Error(`PUT upload failed: ${await res.text()}`);
}

async function getSignedDownloadUrl(objectName) {
  const u = new URL(`${FUNCTIONS_BASE}/getDownloadUrl`);
  u.searchParams.set("object", objectName);

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
  const userText = (inputBox.value || "").trim();
  const file =
    fileInput && fileInput.files && fileInput.files[0] ? fileInput.files[0] : null;

  if (!userText && !file) return;

  try {
    let attachmentMeta = null;
    let textForBot = userText;

    // If a file is selected, upload via signed URL and show it
    if (file) {
      appendMessage("user", userText || "📎 Attaching a file...", {});

      // 1) get signed PUT URL
      const { uploadUrl, objectName } = await getSignedUploadUrl(
        file.name,
        file.type
      );

      // 2) upload file
      await uploadToSignedUrl(uploadUrl, file);

      // 3) get public download URL
      const { downloadUrl } = await getSignedDownloadUrl(objectName);

      // Clear file input
      fileInput.value = "";

      // Show preview/link in chat (as the user's message)
      const isImage = /^image\//i.test(file.type);
      attachmentMeta = {
        url: downloadUrl,
        filename: file.name,
        kind: isImage ? "image" : "file"
      };
      appendMessage("user", userText, { attachment: attachmentMeta });

      // Add a note to send to the bot so it knows there's a file reference
      textForBot =
        (userText ? userText + "\n\n" : "") + `Attached file: ${downloadUrl}`;
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
 *  TOPIC TAGGING (expanded) + HELPERS
 ***********************/
function extractTopics(log) {
  // Join all message content (user + assistant) for tagging
  const text = log.map(m => (m.content || "").toLowerCase()).join(" ");

  // Canonical tag => array of phrases/keywords (all lowercase)
  const TOPIC_MAP = {
    /* ========= LINEAR ALGEBRA ========= */
    "Python": ["python"],
    "Matrices": ["matrix", "matrices"],
    "Vectors": ["vector", "vectors"],
    "Scalars": ["scalar", "scalar multiplication", "multiply scalar"],
    "Transpose": ["transpose", "a^t", "x^t"],
    "Identity Matrix": ["identity matrix", "identity"],
    "Matrix Properties": ["properties", "associative", "commutative", "distributive"],
    "Systems of Equations": ["systems of equations", "system of equations"],
    "Gaussian Elimination": ["gaussian elimination", "elimination"],
    "Gauss–Jordan": ["gauss-jordan", "gauss jordan"],
    "REF": ["ref", "row echelon form"],
    "RREF": ["rref", "reduced row echelon form"],
    "Row Reduction": ["row reduction", "row-reduction"],
    "Pivots": ["pivot", "pivots"],
    "Free Variables": ["free variable", "free variables"],
    "Consistency": ["consistent", "inconsistent", "consistency"],
    "Homogeneous Systems": ["homogeneous", "homogeneous system"],
    "Parametric Form": ["parametric form", "parametric solution"],
    "Determinant": ["determinant", "det"],
    "Cofactor Expansion": ["cofactor expansion", "laplace expansion"],
    "Cramer’s Rule": ["cramer", "cramer’s rule", "cramers rule"],
    "Inverses": ["inverse", "inverse matrix", "invertible"],
    "Singular Matrix": ["singular matrix", "singular"],
    "Inner/Dot Product": ["inner product", "dot product"],
    "Vector Space": ["vector space"],
    "Subspace": ["subspace"],
    "Span": ["span", "spanning set"],
    "Linear Independence": ["independence", "linearly independent", "dependent set"],
    "Basis": ["basis", "standard basis", "orthonormal basis"],
    "Dimension": ["dimension"],
    "Column Space": ["column space", "col a", "colspace"],
    "Row Space": ["row space", "rowspace"],
    "Null Space": ["null space", "nullspace", "kernel"],
    "Rank/Nullity": ["rank", "nullity", "rank-nullity"],
    "Orthogonal": ["orthogonal", "perpendicular"],
    "Orthogonal Complement": ["orthogonal complement"],
    "Orthonormal": ["orthonormal"],
    "Projection": ["projection", "proj"],
    "Least Squares": ["least squares", "normal equations"],
    "Eigenvalues/Eigenvectors": ["eigenvalue", "eigenvalues", "eigenvector", "eigenvectors", "characteristic polynomial"],
    "Diagonalization": ["diagonalization", "diagonalize"],
    "Defective Matrix": ["defective matrix", "defective"],
    "Symmetric Matrices": ["symmetric"],
    "Orthogonal Matrices": ["orthogonal matrix", "orthogonal matrices"],
    "Diagonal Matrices": ["diagonal matrix", "diagonal matrices"],
    "Gram–Schmidt": ["gram-schmidt", "gram schmidt"],

    /* ======== MULTIVARIABLE CALCULUS ======== */
    "Coordinates & Parametric Curves": ["parametric", "polar", "cylindrical", "spherical", "arc length", "parameterization"],
    "Partial Derivatives": ["partial derivative", "partials", "fx", "fy", "fz", "ux", "uy"],
    "Gradient": ["gradient", "grad", "∇f"],
    "Directional Derivatives": ["directional derivative"],
    "Tangent Planes & Linearization": ["tangent plane", "linearization", "differentials"],
    "Chain Rule (Multi)": ["multivariable chain rule", "chain rule (multi)", "total derivative"],
    "Implicit Functions & Jacobian": ["implicit function", "jacobian", "jacobian matrix", "determinant jacobian"],
    "Optimization & LM": ["lagrange multipliers", "constrained optimization", "unconstrained optimization", "critical points", "hessian"],
    "Double Integrals": ["double integral", "iterated integral", "area by integration"],
    "Triple Integrals": ["triple integral", "volume integral"],
    "Change of Variables": ["u-sub in multiple integrals", "change of variables", "jacobian determinant"],
    "Vector Fields": ["vector field", "field lines"],
    "Line Integrals": ["line integral", "work integral", "circulation"],
    "Conservative Fields & Potentials": ["conservative field", "potential function", "exact differential"],
    "Green’s Theorem": ["green's theorem", "greens theorem"],
    "Surface Integrals": ["surface integral", "parametric surface", "surface area integral"],
    "Flux": ["flux", "outward flux"],
    "Curl": ["curl", "rotational"],
    "Divergence": ["divergence", "div"],
    "Stokes’ Theorem": ["stokes theorem", "stokes’ theorem"],
    "Divergence Theorem": ["divergence theorem", "gauss theorem"],
    "Applications (Physics/Geometry)": ["work", "mass density", "center of mass", "moment of inertia"]
  };

  // Count matches per canonical tag using whole-word/phrase regex
  const counts = {};
  for (const [tag, phrases] of Object.entries(TOPIC_MAP)) {
    let c = 0;
    for (const p of phrases) {
      const esc = p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const re = new RegExp(`\\b${esc}\\b`, "g");
      const m = text.match(re);
      if (m) c += m.length;
    }
    if (c > 0) counts[tag] = c;
  }

  // Sort tags by frequency (desc), then alphabetically
  const topics = Object.keys(counts).sort((a, b) =>
    counts[b] - counts[a] || a.localeCompare(b)
  );

  return { topics, topic_counts: counts };
}

/***********************
 *  ANALYTICS HELPERS (tiny, for research)
 ***********************/
function computeAvgUserMessageLength(log) {
  const userMsgs = log.filter(m => m.role === "user").map(m => m.content || "");
  if (userMsgs.length === 0) return { chars: 0, words: 0 };
  const totalChars = userMsgs.reduce((s, t) => s + t.length, 0);
  const totalWords = userMsgs.reduce((s, t) => s + (t.trim() ? t.trim().split(/\s+/).length : 0), 0);
  return {
    chars: Math.round(totalChars / userMsgs.length),
    words: Math.round(totalWords / userMsgs.length)
  };
}

function computeStudentToBotRatio(log) {
  const userCount = log.filter(m => m.role === "user").length;
  const botCount  = log.filter(m => m.role === "assistant").length;
  return botCount === 0 ? (userCount > 0 ? Infinity : 0) : +(userCount / botCount).toFixed(3);
}

function computeSessionDurationSec(start, end) {
  return Math.max(0, Math.round((end.getTime() - start.getTime()) / 1000));
}

/***********************
 *  FIREBASE LOGGING
 ***********************/
async function logSession() {
  try {
    const { topics, topic_counts } = extractTopics(messageLog);
    const avgLens = computeAvgUserMessageLength(messageLog);
    const ratio   = computeStudentToBotRatio(messageLog);
    const durationSec = computeSessionDurationSec(startTime, new Date());

    const metadata = {
      session_id: sessionId,
      user_id: userId,
      user_name: userName || null,
      user_message_count: messageLog.filter((m) => m.role === "user").length,
      total_message_count: messageLog.length,
      start_time: startTime.toISOString(),
      end_time: new Date().toISOString(),
      // Topics
      topics,
      topic_counts,
      // NEW: richer engagement metrics
      avg_user_msg_len_chars: avgLens.chars,
      avg_user_msg_len_words: avgLens.words,
      student_to_bot_ratio: ratio,
      session_duration_sec: durationSec,
      // Full transcript (for qualitative coding, if permitted by IRB)
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
