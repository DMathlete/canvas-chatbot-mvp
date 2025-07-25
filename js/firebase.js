const firebaseConfig = {
  apiKey: "AIzaSyU-UC0qQItahwhqy7q68a9OoNreinYHE",
  authDomain: "canvaschatbot.firebaseapp.com",
  projectId: "canvaschatbot",
  storageBucket: "canvaschatbot.appspot.com",
  messagingSenderId: "93513233362",
  appId: "1:93513233362:web:874453254d707bde224e0b",
  measurementId: "G-25MQFFB2V9"
};

const app = firebase.initializeApp(firebaseConfig);
const db = firebase.firestore();

async function logSessionDataToFirebase(metadata) {
  try {
    await db.collection("chat_sessions").add(metadata);
    console.log("Session metadata logged to Firebase.");
  } catch (error) {
    console.error("Error logging session:", error);
  }
}
