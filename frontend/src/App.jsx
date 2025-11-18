// App.jsx
import { Routes, Route, Navigate, useLocation, Outlet } from "react-router-dom";
import { Suspense, lazy } from "react";
import Layout from "./components/layout/Layout";
import ProtectedRoute from "./components/ProtectedRoute";

// Lazy-load pages
const Login = lazy(() => import("./pages/Login"));
const Register = lazy(() => import("./pages/Register"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Projects = lazy(() => import("./pages/Projects"));
const ProjectDetails = lazy(() => import("./pages/ProjectDetails"));
const Exports = lazy(() => import("./pages/Exports"));
const ForgotPassword = lazy(() => import("./pages/ForgotPassword"));
const ResetPassword = lazy(() => import("./pages/ResetPassword"));
const VerifyEmail = lazy(() => import("./pages/VerifyEmail"));
const ResendVerification = lazy(() => import("./pages/ResendVerification"));
const ProjectsHistory = lazy(() => import("./pages/ProjectsHistory"));
const Profile = lazy(() => import("./pages/Profile"));
const BlobDashboard = lazy(() => import("./pages/BlobDashboard"));
const RateCards = lazy(() => import("./pages/RateCards"));
const ETLDashboard = lazy(() => import("./pages/ETLDashboard")); 


export default function App() {
  const location = useLocation();

  const hideLayoutRoutes = new Set([
    "/login",
    "/register",
    "/forgot-password",
    "/reset-password",
    "/verify-email",
    "/resend-verification",
  ]);
  const shouldHideLayout = hideLayoutRoutes.has(location.pathname);

  const Wrapper = shouldHideLayout ? Outlet : Layout;

  return (
    <Suspense fallback={<p className="text-center mt-10">Loading...</p>}>
      <Routes>
        {/* Public */}
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/resend-verification" element={<ResendVerification />} />

        {/* Protected block */}
        <Route element={<Wrapper />}>
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/projects"
            element={
              <ProtectedRoute>
                <Projects />
              </ProtectedRoute>
            }
          />
          <Route
            path="/projects/:id"
            element={
              <ProtectedRoute>
                <ProjectDetails />
              </ProtectedRoute>
            }
          />
          <Route
            path="/exports/:id"
            element={
              <ProtectedRoute>
                <Exports />
              </ProtectedRoute>
            }
          />
          <Route
            path="/history"
            element={
              <ProtectedRoute>
                <ProjectsHistory />
              </ProtectedRoute>
            }
          />
          <Route
            path="/ratecards"
            element={
              <ProtectedRoute>
                <RateCards />
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <Profile />
              </ProtectedRoute>
            }
          />

          {/* Blob Admin Page */}
          <Route
            path="/blobs"
            element={
              <ProtectedRoute>
                <BlobDashboard />
              </ProtectedRoute>
            }
          />

          {/* ETL Admin Page */}
          <Route
            path="/etl"
            element={
              <ProtectedRoute>
                <ETLDashboard />
              </ProtectedRoute>
            }
          />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Suspense>
  );
}
