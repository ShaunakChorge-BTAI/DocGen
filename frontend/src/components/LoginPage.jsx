import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { login as apiLogin, register as apiRegister } from "../services/api";

export default function LoginPage({ addToast }) {
  const { login } = useAuth();
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      if (mode === "login") {
        const data = await apiLogin(email, password);
        login(data.access_token);
        addToast("Logged in successfully", "success");
      } else {
        await apiRegister(name, email, password);
        // After registering, log in automatically
        const data = await apiLogin(email, password);
        login(data.access_token);
        addToast("Account created — welcome!", "success");
      }
    } catch (err) {
      addToast(err.message, "error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <span style={{ fontSize: 36 }}>📄</span>
          <h1>DocGen</h1>
          <p>AI-Powered Document Generator</p>
        </div>

        <div className="login-tabs">
          <button
            className={mode === "login" ? "active" : ""}
            onClick={() => setMode("login")}
          >
            Sign In
          </button>
          <button
            className={mode === "register" ? "active" : ""}
            onClick={() => setMode("register")}
          >
            Register
          </button>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {mode === "register" && (
            <div className="form-group">
              <label>Full Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                required
              />
            </div>
          )}

          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              minLength={6}
            />
          </div>

          <button type="submit" className="btn-primary login-submit" disabled={loading}>
            {loading ? "Please wait…" : mode === "login" ? "Sign In" : "Create Account"}
          </button>
        </form>

        {mode === "register" && (
          <p className="login-note">
            Note: The very first account registered automatically becomes an Admin.
          </p>
        )}
      </div>
    </div>
  );
}
