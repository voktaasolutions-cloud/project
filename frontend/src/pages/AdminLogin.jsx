import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Lock } from "lucide-react";
import { loginAdmin, getCurrentUser } from "../lib/api";
import Logo from "../components/Logo";
import SEO from "../components/SEO";

const AdminLogin = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    getCurrentUser().then((user) => {
      if (user) {
        navigate("/admin");
      }
    });
  }, [navigate]);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await loginAdmin(email, password);
      navigate("/admin");
    } catch (err) {
      setError(err.message || "Login failed. Check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-purple-950 flex items-center justify-center px-6 relative overflow-hidden" data-testid="admin-login">
      <SEO title="Admin Login | VOKTAA" noindex={true} />
      <div className="absolute inset-0 dot-grid dot-grid-fade opacity-40" />
      <div className="relative w-full max-w-md">
        <div className="flex flex-col items-center justify-center text-center mb-8">
          <Logo light />
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-purple-300 mt-4">Analytics Console</p>
        </div>
        <div className="card-purple bg-white p-8 rounded-3xl shadow-xl">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 flex items-center justify-center bg-purple-100 text-purple-600 rounded-xl"><Lock size={18} /></div>
            <h1 className="font-heading font-bold text-xl text-purple-950">Admin Sign In</h1>
          </div>
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="font-mono text-xs uppercase tracking-[0.15em] text-purple-950 font-bold block mb-2">Email</label>
              <input type="email" className="input-brand w-full px-4 py-3" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="admin-email-input" />
            </div>
            <div>
              <label className="font-mono text-xs uppercase tracking-[0.15em] text-purple-950 font-bold block mb-2">Password</label>
              <input type="password" className="input-brand w-full px-4 py-3" value={password} onChange={(e) => setPassword(e.target.value)} data-testid="admin-password-input" />
            </div>
            {error && <p className="text-destructive text-sm" data-testid="admin-login-error">{error}</p>}
            <button type="submit" disabled={loading} className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 text-white font-bold uppercase tracking-wider text-sm px-8 py-4 rounded-full shadow-lg shadow-purple-500/25 hover:shadow-purple-500/40 transition-all disabled:opacity-60" data-testid="admin-login-button">
              {loading ? "Signing in..." : "Sign In"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default AdminLogin;
