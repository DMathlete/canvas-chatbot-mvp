// Firebase Initialization (Compat SDK)
const firebaseConfig = {
  apiKey: "YOUR_FIREBASE_API_KEY",
  authDomain: "YOUR_FIREBASE_PROJECT.firebaseapp.com",
  projectId: "YOUR_FIREBASE_PROJECT",
  storageBucket: "YOUR_FIREBASE_PROJECT.appspot.com",
  messagingSenderId: "YOUR_SENDER_ID",
  appId: "YOUR_APP_ID",
};

// Ensure we don't re-initialize Firebase
if (!firebase.apps.length) {
  firebase.initializeApp(firebaseConfig);
}
const db = firebase.firestore();

// ✅ Log metadata function
async function logSessionDataToFirebase(metadata) {
  try {
    await db.collection("chat_sessions").add(metadata);
    console.log("✅ Session metadata logged to Firebase:", metadata);
  } catch (err) {
    console.error("❌ Error logging session to Firebase:", err);
  }
}
