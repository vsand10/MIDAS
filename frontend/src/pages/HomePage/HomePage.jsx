/* Placeholder until the real Home screen is built */
export default function HomePage({ onLogOut }) {
  return (
    <main style={{ padding: 24, fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ fontSize: 22 }}>Home</h1>
      <p style={{ color: "#6b6b6b" }}>Home screen coming soon.</p>
      <button
        onClick={onLogOut}
        style={{ marginTop: 16, padding: "10px 16px", borderRadius: 8, border: "none",
          background: "#4a71cd", color: "#fff", fontSize: 15 }}
      >
        Back to Login
      </button>
    </main>
  );
}
 