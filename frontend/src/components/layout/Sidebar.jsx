import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  FolderKanban,
  FileSpreadsheet,
  Menu,
  History,
  Database,
  Wallet,
  GitBranch,
} from "lucide-react";
import { useAuth } from "../../contexts/AuthContext";
import { useProjects } from "../../contexts/ProjectContext";



export default function Sidebar({ isOpen, setIsOpen, mobileOpen }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { projects } = useProjects();

  const latestProjectId = projects?.length
    ? [...projects]
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0]?.id
    : null;

  // Base nav items (everyone)
  const baseNavItems = [
    { path: "/dashboard", label: "Dashboard", icon: <LayoutDashboard className="w-5 h-5" /> },
    { path: "/ratecards", label: "Pricing", icon: <Wallet className="w-5 h-5" /> },
  ];

  // Add Knowledge Base and ETL Pipeline only for superusers
  const navItems = user?.is_superuser
    ? [
        ...baseNavItems,
        { path: "/blobs", label: "Knowledge Base", icon: <Database className="w-5 h-5" /> },
        { path: "/etl", label: "ETL Pipeline", icon: <GitBranch className="w-5 h-5" /> },
      ]
    : baseNavItems;

  const handleNavClick = () => {
    if (mobileOpen) setIsOpen(false);
  };

  const initials = user?.username?.[0]?.toUpperCase() || "?";

  return (
    <aside
      className={`fixed md:static left-0
        mt-16 md:mt-0
        h-[calc(100vh-64px)] md:h-screen
        flex flex-col justify-between
        ${isOpen ? "w-64" : "w-20"}
        bg-white/80 dark:bg-dark-surface/80 backdrop-blur-xl
        shadow-2xl border-r border-gray-200/50 dark:border-dark-muted/50
        transform transition-all duration-300 z-40
        ${mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}`}
    >
      <div className="flex flex-col flex-1">
        {/* 🔹 Toggle */}
        <div className="flex justify-center items-center h-16
        bg-gradient-to-br from-primary/10 to-accent/10
        dark:from-dark-primary/10 dark:to-dark-accent/10
        border-b border-gray-200/50 dark:border-dark-muted/50">
          <button
            onClick={() => setIsOpen(!isOpen)}
            className="hidden md:flex items-center justify-center w-11 h-11
            text-primary dark:text-dark-primary rounded-xl
            hover:bg-primary/10 dark:hover:bg-dark-primary/10
            transition-all duration-200"
          >
            <Menu className="w-6 h-6" />
          </button>
        </div>

        {/* 🔹 Navigation */}
        <nav className="flex-1 px-3 py-6 space-y-2 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={handleNavClick}
              className={({ isActive }) =>
                `group flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 relative ${
                  isActive
                    ? "bg-gradient-to-r from-primary to-accent text-white font-semibold shadow-lg shadow-primary/30"
                    : "text-gray-700 dark:text-gray-300 hover:bg-gradient-to-r hover:from-primary/10 hover:to-accent/10 dark:hover:from-dark-primary/20 dark:hover:to-dark-accent/20"
                }`
              }
            >
              <div className={`${isOpen ? '' : 'mx-auto'}`}>
                {item.icon}
              </div>
              <span
                className={`font-medium transition-all duration-300 origin-left whitespace-nowrap ${
                  isOpen ? "opacity-100 scale-100" : "opacity-0 scale-0 w-0 hidden"
                }`}
              >
                {item.label}
              </span>
              {/* Active indicator dot */}
              {!isOpen && (
                <div className="absolute -right-1 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-primary opacity-0 group-[.active]:opacity-100 transition-opacity"></div>
              )}
            </NavLink>
          ))}
        </nav>
      </div>

      {/* User Profile */}
      {user && (
        <div
          onClick={() => navigate("/profile")}
          className="flex items-center gap-3 px-4 py-4 cursor-pointer
          border-t border-gray-200/50 dark:border-dark-muted/50
          hover:bg-gradient-to-r hover:from-primary/5 hover:to-accent/5
          dark:hover:from-dark-primary/10 dark:hover:to-dark-accent/10
          transition-all duration-200 group"
        >
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-accent
          text-white font-bold flex items-center justify-center shadow-lg
          group-hover:scale-110 transition-transform duration-200">
            {initials}
          </div>
          {isOpen && (
            <div className="flex flex-col">
              <span className="text-sm font-semibold text-gray-800 dark:text-gray-100">
                {user.username}
              </span>
              <span className="text-xs text-gray-500 dark:text-gray-400 group-hover:text-primary dark:group-hover:text-dark-primary transition-colors">
                View Profile →
              </span>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}
