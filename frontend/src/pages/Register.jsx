import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../api/client";

export default function Register() {
  const navigate               = useNavigate();
  const [email, setEmail]      = useState("");
  const [password, setPass]    = useState("");
  const [confirm, setConfirm]  = useState("");
  const [error, setError]      = useState("");
  const [success, setSuccess]  = useState(false);
  const [loading, setLoading]  = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (password !== confirm) { setError("Passwords don't match."); return; }
    if (password.length < 8)  { setError("Password must be at least 8 characters."); return; }
    setLoading(true);
    try {
      await api.post("/auth/register", { email, password });
      setSuccess(true);
    } catch (err) {
      setError(err.response?.data?.detail || "Registration failed.");
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-[#1e1f20] flex items-center justify-center px-4">
        <div className="w-full max-w-sm bg-[#2d2e30] rounded-2xl p-8 shadow-xl text-center">
          <div className="text-4xl mb-4">📬</div>
          <h2 className="text-white text-xl font-medium mb-2">Check your email</h2>
          <p className="text-[#9aa0a6] text-sm mb-6">
            We sent a verification link to <span className="text-white">{email}</span>.
            Click it to activate your account.
          </p>
          <Link
            to="/login"
            className="text-[#8ab4f8] text-sm hover:underline"
          >
            Back to Sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#1e1f20] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">

        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <GeminiLogo />
          <h1 className="text-white text-2xl font-medium mt-4">Create account</h1>
          <p className="text-[#9aa0a6] text-sm mt-1">to continue to Gemini</p>
        </div>

        {/* Card */}
        <div className="bg-[#2d2e30] rounded-2xl p-8 shadow-xl">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">

            <InputField label="Email"            type="email"    value={email}    onChange={setEmail}   autoFocus />
            <InputField label="Password"         type="password" value={password} onChange={setPass} />
            <InputField label="Confirm Password" type="password" value={confirm}  onChange={setConfirm} />

            {error && (
              <p className="text-[#f28b82] text-sm text-center">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="mt-2 w-full py-2.5 rounded-full bg-[#8ab4f8] hover:bg-[#93bbf9]
                         text-[#1e1f20] font-medium text-sm transition disabled:opacity-50"
            >
              {loading ? "Creating account…" : "Create account"}
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-[#9aa0a6]">
            Already have an account?{" "}
            <Link to="/login" className="text-[#8ab4f8] hover:underline">
              Sign in
            </Link>
          </div>
        </div>

      </div>
    </div>
  );
}

function InputField({ label, type, value, onChange, autoFocus }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[#9aa0a6] text-xs">{label}</label>
      <input
        type={type}
        value={value}
        autoFocus={autoFocus}
        onChange={(e) => onChange(e.target.value)}
        required
        className="bg-[#3c4043] text-white text-sm rounded-lg px-4 py-2.5
                   border border-transparent focus:border-[#8ab4f8] focus:outline-none
                   transition"
      />
    </div>
  );
}

function GeminiLogo() {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <path d="M20 4 C20 4 28 14 28 20 C28 26 20 36 20 36 C20 36 12 26 12 20 C12 14 20 4 20 4Z" fill="url(#g1)" />
      <path d="M4 20 C4 20 14 12 20 12 C26 12 36 20 36 20 C36 20 26 28 20 28 C14 28 4 20 4 20Z" fill="url(#g2)" />
      <defs>
        <linearGradient id="g1" x1="20" y1="4" x2="20" y2="36" gradientUnits="userSpaceOnUse">
          <stop stopColor="#8ab4f8" /><stop offset="1" stopColor="#c58af9" />
        </linearGradient>
        <linearGradient id="g2" x1="4" y1="20" x2="36" y2="20" gradientUnits="userSpaceOnUse">
          <stop stopColor="#c58af9" /><stop offset="1" stopColor="#8ab4f8" />
        </linearGradient>
      </defs>
    </svg>
  );
}