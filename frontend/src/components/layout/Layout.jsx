import { Outlet } from "react-router-dom";
import { useState } from "react";
import Header from "./Header";
import Sidebar from "./Sidebar";

export default function Layout() {
  const [isOpen, setIsOpen] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <Sidebar isOpen={isOpen} setIsOpen={setIsOpen} mobileOpen={mobileOpen} />

      {/* Main Content */}
      <div className="flex flex-col flex-1">
        <Header
          onToggleSidebar={() => setMobileOpen(!mobileOpen)}
          isSidebarOpen={mobileOpen}
        />
        <main className="flex-1 p-8 overflow-y-auto relative">
          <div className="max-w-7xl mx-auto relative z-10">
            <Outlet /> {/* renders nested routes */}
          </div>
        </main>
      </div>
    </div>
  );
}

