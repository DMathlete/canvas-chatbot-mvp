// Firebase config
const firebaseConfig = {
  apiKey: "AIzaSyC-UCogQItaHwhqyq7q68a9GOoNreinYHE",
  authDomain: "canvaschatbot.firebaseapp.com",
  projectId: "canvaschatbot",
  storageBucket: "canvaschatbot.firebasestorage.app",
  messagingSenderId: "93513233362",
  appId: "1:93513233362:web:874453254d707bde224e0b",
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);
const db = firebase.firestore();

async function logSessionDataToFirebase(metadata) {
  try {
    await db.collection("chat_sessions").add(metadata);
    console.log("Session metadata logged to Firebase.");
  } catch (error) {
    console.error("Error logging session:", error);
  }
}
