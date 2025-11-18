import { useState, useRef, useEffect } from "react";
import { Sun, Moon, LogOut, Menu, X } from "lucide-react";
import { useAuth } from "../../contexts/AuthContext";
import { useNavigate } from "react-router-dom";

export default function Header({ onToggleSidebar, isSidebarOpen }) {
  const [darkMode, setDarkMode] = useState(
    document.documentElement.classList.contains("dark")
  );
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  const handleLogout = () => {
    logout();
    window.location.href = "/login";
  };

  const toggleDarkMode = () => {
    document.documentElement.classList.toggle("dark");
    setDarkMode(!darkMode);
  };

  const openProfile = () => {
    navigate("/profile");
    setDropdownOpen(false);
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const initials = user?.username?.[0]?.toUpperCase() || "?";

  return (
    <header className="flex justify-between items-center h-16
      bg-gradient-to-r from-primary via-accent to-primary
      dark:from-dark-primary dark:via-dark-accent dark:to-dark-primary
      text-white shadow-lg px-4 md:px-6 border-b border-white/10 dark:border-gray-700/50
      backdrop-blur-sm relative overflow-hidden"
    >
      {/* Decorative background pattern */}
      <div className="absolute inset-0 opacity-10">
        <div className="absolute inset-0" style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg width='20' height='20' viewBox='0 0 20 20' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M0 0h20L0 20z'/%3E%3C/g%3E%3C/svg%3E")`,
          backgroundSize: '20px 20px'
        }}></div>
      </div>

      <div className="flex items-center gap-3 relative z-10">
        {/*  Mobile Sidebar Toggle */}
        <button
          onClick={onToggleSidebar}
          className="md:hidden flex items-center justify-center w-10 h-10 rounded-xl
          hover:bg-white/20 active:bg-white/30 transition-all duration-200"
        >
          {isSidebarOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>

        <div className="flex items-center gap-3 px-3 py-2 rounded-xl bg-white/10 backdrop-blur-md">
          <img
            src="/bot.png"
            alt="icon"
            className="w-10 h-10 drop-shadow-lg"
          />

          <h1 className="text-xl font-extrabold font-heading text-white tracking-wide">
            Project Scoping Bot
          </h1>
        </div>
      </div>

      <div className="flex items-center gap-4 relative z-10">
        {/*  Profile Dropdown */}
        {user ? (
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="flex items-center gap-2 px-3 py-2 rounded-xl
              bg-white/10 backdrop-blur-md hover:bg-white/20
              transition-all duration-200 border border-white/20"
            >
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-white to-accent
              text-primary font-bold flex items-center justify-center shadow-lg">
                {initials}
              </div>
              <span className="hidden md:inline font-medium">{user.username}</span>
            </button>

            {dropdownOpen && (
              <div className="absolute right-0 mt-3 w-48 bg-white dark:bg-gray-800
              text-gray-800 dark:text-gray-100 rounded-2xl shadow-2xl
              border border-gray-200 dark:border-gray-700 overflow-hidden z-50
              animate-fade-in">
                <button
                  onClick={openProfile}
                  className="w-full text-left px-4 py-3 text-sm font-medium
                  hover:bg-gradient-to-r hover:from-primary/10 hover:to-accent/10
                  dark:hover:from-dark-primary/20 dark:hover:to-dark-accent/20
                  transition-all duration-200 flex items-center gap-2"
                >
                  <div className="w-2 h-2 rounded-full bg-primary"></div>
                  Profile
                </button>
                <button
                  onClick={handleLogout}
                  className="w-full text-left px-4 py-3 text-sm font-medium text-red-600
                  hover:bg-red-50 dark:hover:bg-red-900/20
                  transition-all duration-200 flex items-center gap-2 border-t border-gray-200 dark:border-gray-700"
                >
                  <LogOut className="w-3 h-3" />
                  Logout
                </button>
              </div>
            )}
          </div>
        ) : (
          <span className="italic opacity-70">Not logged in</span>
        )}

        {/*  Theme toggle */}
        <button
          onClick={toggleDarkMode}
          aria-label="Toggle theme"
          className="flex items-center justify-center w-10 h-10
            bg-white/10 dark:bg-gray-900/50 backdrop-blur-md
            text-white rounded-xl shadow-lg hover:bg-white/20 dark:hover:bg-gray-800/70
            transition-all duration-200 border border-white/20 dark:border-gray-700"
        >
          {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </button>
      </div>
    </header>
  );
}

