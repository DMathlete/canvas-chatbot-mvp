// Import Firebase SDKs (Compat for easier integration with your existing code)
// Use these instead of modular imports to avoid breaking the current openai-bot.js

// Firebase configuration (copied from your Firebase console)
const firebaseConfig = {
  apiKey: "AIzaSyC-UCogQItaHwhqyq7q68a9GOoNreinYHE",
  authDomain: "canvaschatbot.firebaseapp.com",
  projectId: "canvaschatbot",
  storageBucket: "canvaschatbot.appspot.com", // ✅ FIXED
  messagingSenderId: "93513233362",
  appId: "1:93513233362:web:874453254d707bde224e0b",
  measurementId: "G-25MQFFB2V9"
};

// ✅ Initialize Firebase if not already initialized
if (!firebase.apps.length) {
  firebase.initializeApp(firebaseConfig);
}

async function logSessionDataToFirebase(metadata) {
  try {
    const sessionRef = db.collection("chat_sessions").doc(metadata.session_id);

    await sessionRef.set(metadata, { merge: true }); // 🔥 merge updates existing fields
    console.log("✅ Session metadata updated in Firebase:", metadata);

  } catch (err) {
    console.error("❌ Error logging session to Firebase:", err);
  }
}

