import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import authApi from "../api/authApi";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      // Login and get tokens
      const res = await authApi.login(email, password);

      localStorage.setItem("access_token", res.data.access_token);
      if (res.data.refresh_token) {
        localStorage.setItem("refresh_token", res.data.refresh_token);
      }

      // Fetch user profile
      navigate("/dashboard");
    } catch (err) {
      console.error(" Login error:", err);
      alert(" Login failed. Check your credentials and try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen relative overflow-hidden">
      {/* Animated background */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-accent/10 to-secondary/10 dark:from-dark-primary/20 dark:via-dark-accent/20 dark:to-dark-secondary/20"></div>
      <div className="absolute inset-0 opacity-30">
        <div className="absolute top-20 left-20 w-72 h-72 bg-primary/20 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute bottom-20 right-20 w-96 h-96 bg-accent/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '2s' }}></div>
      </div>

      <form
        onSubmit={handleSubmit}
        className="relative bg-white/90 dark:bg-dark-surface/90 backdrop-blur-xl p-10 rounded-3xl
        shadow-2xl w-full max-w-md space-y-6 border border-gray-200/50 dark:border-dark-muted/50
        animate-fade-in"
      >
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl
          bg-gradient-to-br from-primary to-accent shadow-lg mb-4">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h1 className="text-3xl font-extrabold gradient-text">
            Welcome Back
          </h1>
          <p className="text-gray-600 dark:text-gray-400 text-sm">
            Sign in to continue to your dashboard
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Email Address
            </label>
            <input
              className="w-full border-2 border-gray-200 dark:border-dark-muted rounded-xl px-4 py-3
              focus:outline-none focus:border-primary dark:focus:border-dark-primary
              bg-gray-50 dark:bg-dark-surface text-gray-800 dark:text-white
              transition-all duration-200 placeholder:text-gray-400"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Password
            </label>
            <input
              className="w-full border-2 border-gray-200 dark:border-dark-muted rounded-xl px-4 py-3
              focus:outline-none focus:border-primary dark:focus:border-dark-primary
              bg-gray-50 dark:bg-dark-surface text-gray-800 dark:text-white
              transition-all duration-200 placeholder:text-gray-400"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-gradient-to-r from-primary to-accent hover:from-primary/90 hover:to-accent/90
          text-white py-3.5 rounded-xl transition-all duration-200 font-semibold shadow-lg
          shadow-primary/30 disabled:opacity-50 disabled:cursor-not-allowed
          hover:shadow-xl hover:shadow-primary/40 hover:-translate-y-0.5
          relative overflow-hidden group"
        >
          <span className="relative z-10">{loading ? "Logging in..." : "Sign In"}</span>
          <div className="absolute inset-0 bg-gradient-to-r from-accent to-primary opacity-0 group-hover:opacity-100 transition-opacity"></div>
        </button>

        <div className="flex justify-between items-center text-sm">
          <Link to="/register" className="text-primary dark:text-dark-primary hover:underline font-medium">
            Create Account
          </Link>
          <Link to="/forgot-password" className="text-gray-600 dark:text-gray-400 hover:text-primary dark:hover:text-dark-primary hover:underline">
            Forgot Password?
          </Link>
        </div>
      </form>
    </div>
  );
}
