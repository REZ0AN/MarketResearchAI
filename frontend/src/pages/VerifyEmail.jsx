import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api from "../api/client";

export default function VerifyEmail() {
  const [params]              = useSearchParams();
  const token                 = params.get("token");
  const [status, setStatus]   = useState(token ? "verifying" : "error");
  const [message, setMessage] = useState(token ? "" : "No token found in URL.");

  const called = useRef(false);

  useEffect(() => {
    if (!token || called.current) return;
    called.current = true;

    api.post("/auth/verify-email", { token })
      .then(() => setStatus("success"))
      .catch((err) => {
        setStatus("error");
        setMessage(err.response?.data?.detail || "Verification failed.");
      });
  }, [token]);

  return (
    <div className="min-h-screen bg-[#1e1f20] flex items-center justify-center px-4">
      <div className="w-full max-w-sm bg-[#2d2e30] rounded-2xl p-8 shadow-xl text-center">
        {status === "verifying" && (
          <>
            <div className="w-8 h-8 mx-auto rounded-full border-4 border-[#8ab4f8] border-t-transparent animate-spin mb-4" />
            <p className="text-[#9aa0a6] text-sm">Verifying your email…</p>
          </>
        )}
        {status === "success" && (
          <>
            <div className="text-4xl mb-4">✅</div>
            <h2 className="text-white text-xl font-medium mb-2">Email verified!</h2>
            <p className="text-[#9aa0a6] text-sm mb-6">Your account is now active.</p>
            <Link
              to="/login"
              className="inline-block px-6 py-2.5 rounded-full bg-[#8ab4f8]
                         text-[#1e1f20] font-medium text-sm hover:bg-[#93bbf9] transition"
            >
              Sign in
            </Link>
          </>
        )}
        {status === "error" && (
          <>
            <div className="text-4xl mb-4">❌</div>
            <h2 className="text-white text-xl font-medium mb-2">Verification failed</h2>
            <p className="text-[#f28b82] text-sm mb-6">{message}</p>
            <Link to="/login" className="text-[#8ab4f8] text-sm hover:underline">
              Back to Sign in
            </Link>
          </>
        )}
      </div>
    </div>
  );
}