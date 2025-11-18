import { useEffect } from "react";
import { useProjects } from "../contexts/ProjectContext";
import { useAuth } from "../contexts/AuthContext";
import {
  Trash2,
  PlusCircle,
  Folder,
  Eye,
  History
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export default function Dashboard() {
  const { projects, fetchProjects, deleteProject } = useProjects();
  const { user } = useAuth();

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);


  const handleDelete = async (id) => {
    if (window.confirm("Are you sure you want to delete this project?")) {
      await deleteProject(id);
    }
  };

  // Today's date
  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  // Complexity breakdown
  const complexityData = ["Simple", "Medium", "Large"].map((c) => ({
    complexity: c,
    count: projects.filter((p) => p.complexity === c).length,
  }));

  //  Daily projects created
  const dailyData = projects.reduce((acc, p) => {
    const day = new Date(p.created_at).toLocaleDateString("en-US", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
    const existing = acc.find((d) => d.day === day);
    if (existing) existing.count += 1;
    else acc.push({ day, count: 1 });
    return acc;
  }, []);

  // Sort chronologically
  dailyData.sort((a, b) => new Date(a.day) - new Date(b.day));

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="relative">
        <div className="relative bg-white/60 dark:bg-dark-surface/60 backdrop-blur-xl rounded-3xl p-8 shadow-glow border border-gray-200/50 dark:border-dark-muted/50 overflow-hidden">
          {/* Background decoration */}
          <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-br from-primary/10 to-accent/10 rounded-full blur-3xl -z-10"></div>

          <div className="relative z-10">
            <h1 className="text-4xl font-extrabold bg-gradient-to-r from-primary via-accent to-secondary bg-clip-text text-transparent mb-2">
              Welcome back{user ? `, ${user.username}` : ""}!
            </h1>
            <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400 mb-1">
              <span className="status-dot status-online"></span>
              <p className="text-sm font-medium">{today}</p>
            </div>
            <p className="text-gray-600 dark:text-gray-400">
              Here's a quick overview of your scoping activity.
            </p>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <div className="group relative bg-white/80 dark:bg-dark-surface/80 backdrop-blur-xl rounded-2xl p-6 shadow-lg hover:shadow-glow transition-all duration-300 border border-gray-200/50 dark:border-dark-muted/50 overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-primary/20 to-transparent rounded-full blur-2xl group-hover:scale-150 transition-transform duration-500"></div>
          <div className="relative z-10">
            <p className="text-sm font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider mb-2">Total Projects</p>
            <p className="text-4xl font-extrabold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">{projects.length}</p>
          </div>
        </div>

        <div className="group relative bg-white/80 dark:bg-dark-surface/80 backdrop-blur-xl rounded-2xl p-6 shadow-lg hover:shadow-glow transition-all duration-300 border border-gray-200/50 dark:border-dark-muted/50 overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-accent/20 to-transparent rounded-full blur-2xl group-hover:scale-150 transition-transform duration-500"></div>
          <div className="relative z-10">
            <p className="text-sm font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider mb-2">This Week</p>
            <p className="text-4xl font-extrabold bg-gradient-to-r from-accent to-secondary bg-clip-text text-transparent">
              {projects.filter(p => {
                const created = new Date(p.created_at);
                const weekAgo = new Date();
                weekAgo.setDate(weekAgo.getDate() - 7);
                return created >= weekAgo;
              }).length}
            </p>
          </div>
        </div>

        <div className="group relative bg-white/80 dark:bg-dark-surface/80 backdrop-blur-xl rounded-2xl p-6 shadow-lg hover:shadow-glow transition-all duration-300 border border-gray-200/50 dark:border-dark-muted/50 overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-secondary/20 to-transparent rounded-full blur-2xl group-hover:scale-150 transition-transform duration-500"></div>
          <div className="relative z-10">
            <p className="text-sm font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider mb-2">Active</p>
            <p className="text-4xl font-extrabold bg-gradient-to-r from-secondary to-primary bg-clip-text text-transparent">{projects.length}</p>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Complexity Bar */}
        <div className="bg-white/80 dark:bg-dark-surface/80 backdrop-blur-xl p-8 rounded-2xl shadow-lg border border-gray-200/50 dark:border-dark-muted/50 hover:shadow-glow transition-all duration-300">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-lg">
              <Folder className="w-5 h-5 text-white" />
            </div>
            <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">
              Projects by Complexity
            </h2>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={complexityData}>
              <XAxis dataKey="complexity" stroke="#9CA3AF" fontSize={13} fontWeight={600} />
              <YAxis stroke="#9CA3AF" fontSize={13} allowDecimals={false} />
              <Tooltip
                contentStyle={{
                  fontSize: "13px",
                  backgroundColor: "rgba(255, 255, 255, 0.95)",
                  border: "none",
                  borderRadius: "12px",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.15)"
                }}
              />
              <Bar dataKey="count" fill="url(#colorGradient)" radius={[8, 8, 0, 0]} />
              <defs>
                <linearGradient id="colorGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#14b8a6" />
                  <stop offset="100%" stopColor="#0d9488" />
                </linearGradient>
              </defs>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Daily Line */}
        <div className="bg-white/80 dark:bg-dark-surface/80 backdrop-blur-xl p-8 rounded-2xl shadow-lg border border-gray-200/50 dark:border-dark-muted/50 hover:shadow-glow transition-all duration-300">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent to-secondary flex items-center justify-center shadow-lg">
              <History className="w-5 h-5 text-white" />
            </div>
            <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">
              Projects Timeline
            </h2>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={dailyData}>
              <XAxis dataKey="day" stroke="#9CA3AF" fontSize={13} fontWeight={600} />
              <YAxis stroke="#9CA3AF" fontSize={13} allowDecimals={false} />
              <Tooltip
                contentStyle={{
                  fontSize: "13px",
                  backgroundColor: "rgba(255, 255, 255, 0.95)",
                  border: "none",
                  borderRadius: "12px",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.15)"
                }}
              />
              <Line
                type="monotone"
                dataKey="count"
                stroke="#14b8a6"
                strokeWidth={3}
                dot={{ r: 4, fill: "#14b8a6", strokeWidth: 2, stroke: "#fff" }}
                activeDot={{ r: 6, fill: "#0d9488", strokeWidth: 3, stroke: "#fff" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Link
          to="/projects"
          className="group relative flex items-center justify-center gap-3 bg-gradient-to-r from-primary to-accent text-white py-4 px-6 rounded-2xl shadow-lg hover:shadow-glow-lg transition-all duration-300 overflow-hidden"
        >
          <div className="absolute inset-0 bg-gradient-to-r from-accent to-primary opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
          <PlusCircle className="w-5 h-5 relative z-10 group-hover:rotate-90 transition-transform duration-300" />
          <span className="relative z-10 font-semibold">Create New Project</span>
        </Link>
        <Link
          to="/history"
          className="group relative flex items-center justify-center gap-3 bg-gradient-to-r from-accent to-secondary text-white py-4 px-6 rounded-2xl shadow-lg hover:shadow-glow-lg transition-all duration-300 overflow-hidden"
        >
          <div className="absolute inset-0 bg-gradient-to-r from-secondary to-accent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
          <History className="w-5 h-5 relative z-10 group-hover:scale-110 transition-transform duration-300" />
          <span className="relative z-10 font-semibold">View Project History</span>
        </Link>
      </div>

      {/* Recent Projects */}
      <div className="bg-white dark:bg-dark-surface rounded-xl shadow-md border border-gray-200 dark:border-dark-muted p-6">
        <div className="flex items-center gap-2 mb-4 justify-between">
          <div className="flex items-center gap-2">
            <Folder className="w-6 h-6 text-gray-500 dark:text-gray-400" />
            <h3 className="text-lg font-semibold text-gray-700 dark:text-gray-100">
              Recent Projects
            </h3>
          </div>
        </div>

        {projects.length === 0 ? (
          <p className="text-gray-500 dark:text-gray-400">
            No projects yet. Create one!
          </p>
        ) : (
          <table className="min-w-full text-sm border border-gray-200 dark:border-dark-muted rounded-lg overflow-hidden">
            <thead className="bg-gray-100 dark:bg-dark-muted text-gray-700 dark:text-gray-300">
              <tr>
                <th className="px-4 py-2 text-left">Name</th>
                <th className="px-4 py-2 text-left">Domain</th>
                <th className="px-4 py-2 text-left">Created</th>
                <th className="px-4 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {[...projects]
                .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
                .slice(0, 5)
                .map((p) => (

                <tr
                  key={p.id}
                  className="border-t border-gray-200 dark:border-dark-muted hover:bg-gray-50 dark:hover:bg-dark-background transition"
                >
                  <td className="px-4 py-2 font-semibold">
                    <Link
                      to={`/exports/${p.id}?mode=draft`}
                      className="text-primary hover:underline"
                    >
                      {p.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-gray-500 dark:text-gray-400">
                    {p.domain || "-"}
                  </td>
                  <td className="px-4 py-2 text-gray-500 dark:text-gray-400">
                    {new Date(p.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-2 flex items-center gap-3 justify-end">
                    <Link
                      to={`/exports/${p.id}?mode=draft`}
                      className="flex items-center gap-1 text-primary hover:underline"
                    >
                      <Eye className="w-5 h-5" />
                      View
                    </Link>
                    <button
                      onClick={() => handleDelete(p.id)}
                      className="flex items-center gap-1 text-red-600 hover:text-red-800 transition"
                    >
                      <Trash2 className="w-5 h-5" />
                      Delete
                    </button>
                  </td>
                </tr>
              ))}

            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
