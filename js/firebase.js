// Firebase initialization
const firebaseConfig = {
  apiKey: "AIzaSyC-UCogQItaHwhqyq7q68a9GOoNreinYHE",
  authDomain: "canvaschatbot.firebaseapp.com",
  projectId: "canvaschatbot",
  storageBucket: "canvaschatbot.appspot.com", 
  messagingSenderId: "93513233362",
  appId: "1:93513233362:web:874453254d707bde224e0b"
};

if (!firebase.apps.length) {
  firebase.initializeApp(firebaseConfig);
}

const db = firebase.firestore();

// ✅ Update or create session
async function logSessionDataToFirebase(metadata) {
  try {
    const sessionRef = db.collection("chat_sessions").doc(metadata.session_id);
    await sessionRef.set(metadata, { merge: true });
    console.log("✅ Session metadata updated in Firebase:", metadata);
  } catch (err) {
    console.error("❌ Error logging session to Firebase:", err);
  }
}
