import { BrowserRouter as Router, NavLink, Route, Routes } from "react-router-dom";
import { Calendar, Home, PieChart, ShoppingCart } from "lucide-react";

import { cn } from "./lib/cn";
import CalendarPage from "./pages/Calendar";
import Dashboard from "./pages/Dashboard";
import Finances from "./pages/Finances";
import PantryPage from "./pages/Pantry";

const navItems = [
  { name: "Dashboard", icon: Home, path: "/" },
  { name: "Finances", icon: PieChart, path: "/finances" },
  { name: "Pantry & Courses", icon: ShoppingCart, path: "/pantry" },
  { name: "Calendrier", icon: Calendar, path: "/calendar" },
];

function Sidebar() {
  return (
    <aside className="w-64 h-screen fixed left-0 top-0 glass border-r z-50 flex flex-col pt-8 pb-4">
      <div className="px-6 mb-8">
        <h1 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-[--color-primary] to-purple-500 bg-clip-text text-transparent">AdamHUB</h1>
      </div>

      <nav className="flex-1 px-4 space-y-2">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-[--color-primary] text-white shadow-md shadow-[--color-primary]/20"
                  : "text-foreground/80 hover:bg-black/5 dark:hover:bg-white/5 hover:text-foreground",
              )
            }
          >
            <item.icon className="w-5 h-5" />
            {item.name}
          </NavLink>
        ))}
      </nav>

      <div className="px-6 mt-auto">
        <div className="text-xs text-foreground/50 text-center font-medium">Life API Client</div>
      </div>
    </aside>
  );
}

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-[--color-background] dark:bg-[--color-dark-background] text-[--color-foreground] dark:text-[--color-dark-foreground] flex">
        <Sidebar />
        <main className="flex-1 ml-64 min-h-screen pb-12 transition-all">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/finances" element={<Finances />} />
            <Route path="/pantry" element={<PantryPage />} />
            <Route path="/calendar" element={<CalendarPage />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
