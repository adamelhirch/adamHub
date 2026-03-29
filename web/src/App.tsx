import {
  BrowserRouter as Router,
  Routes,
  Route,
  NavLink,
} from "react-router-dom";
import {
  Calendar,
  CreditCard,
  ShoppingBasket,
  ChefHat,
  Activity,
  CheckSquare,
  ArrowUpRight,
} from "lucide-react";
import CalendarPage from "./pages/CalendarPage";
import FitnessPage from "./pages/FitnessPage";
import TasksPage from "./pages/TasksPage";
import FinancesPage from "./pages/FinancesPage";
import GroceriesPage from "./pages/GroceriesPage";
import RecipesPage from "./pages/RecipesPage";

const navItems = [
  { name: "Calendar", path: "/", icon: Calendar },
  { name: "Tasks", path: "/tasks", icon: CheckSquare },
  { name: "Finances", path: "/finances", icon: CreditCard },
  { name: "Groceries", path: "/groceries", icon: ShoppingBasket },
  { name: "Recipes", path: "/recipes", icon: ChefHat },
  { name: "Fitness", path: "/fitness", icon: Activity },
] as const;

function NavigationBar() {
  return (
    <>
      <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
        <div className="orb-drift absolute -left-20 top-[-7rem] h-72 w-72 rounded-full bg-[#0A84FF]/18 blur-3xl" />
        <div className="orb-drift-reverse absolute right-[-5rem] top-20 h-80 w-80 rounded-full bg-[#6366F1]/12 blur-3xl" />
        <div className="orb-drift absolute bottom-[-7rem] left-1/3 h-80 w-80 rounded-full bg-[#30D158]/8 blur-3xl" />
        <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.64)_0%,rgba(255,255,255,0.32)_38%,rgba(239,242,248,0.86)_100%)]" />
        <div className="absolute inset-0 opacity-[0.35] bg-[radial-gradient(circle_at_1px_1px,rgba(15,23,42,0.12)_1px,transparent_0)] [background-size:20px_20px]" />
      </div>

      <div className="md:hidden fixed bottom-[max(env(safe-area-inset-bottom),0.5rem)] left-3 right-3 z-50 pointer-events-none">
        <div className="pointer-events-auto relative mx-auto max-w-3xl overflow-hidden rounded-[32px] bg-white/60 backdrop-blur-xl border border-white/20 shadow-lg px-2 py-2.5">
          <div className="flex items-center justify-between gap-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.name}
                  to={item.path}
                  className={({ isActive }) =>
                    `flex min-w-0 flex-1 flex-col items-center justify-center gap-1 rounded-[20px] px-2 py-2.5 transition-all ${
                      isActive
                        ? "bg-white/80 text-apple-blue shadow-sm ring-1 ring-black/5"
                        : "text-apple-gray-500 hover:bg-white/40 hover:text-black"
                    }`
                  }
                >
                  <Icon className="h-5 w-5" strokeWidth={2} />
                  <span className="text-[10px] font-semibold tracking-tight leading-none">
                    {item.name}
                  </span>
                </NavLink>
              );
            })}
          </div>
        </div>
      </div>

      <div className="hidden md:flex flex-col w-[18rem] h-full border-r border-white/70 bg-white/72 p-4 shrink-0 backdrop-blur-2xl shadow-[0_0_0_1px_rgba(255,255,255,0.35)]">
        <div className="mt-2 rounded-[28px] border border-white/70 bg-white/80 p-4 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
          <p className="text-[10px] font-bold uppercase tracking-[0.32em] text-apple-gray-500">
            Workspace
          </p>
          <div className="mt-3 flex items-start gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#0A84FF,#6366F1)] text-white shadow-[0_12px_30px_rgba(10,132,255,0.25)]">
              <span className="h-2.5 w-2.5 rounded-full bg-white" />
            </div>
            <div className="min-w-0">
              <h1 className="text-2xl font-semibold tracking-tight text-black">
                AdamHUB
              </h1>
              <p className="mt-1 text-sm leading-6 text-apple-gray-500">
                Tâches, calendrier, recettes, courses et fitness dans une
                interface unique.
              </p>
            </div>
          </div>
          <div className="mt-4 flex items-center justify-between rounded-2xl border border-apple-gray-100 bg-apple-gray-50 px-3 py-2">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.28em] text-apple-gray-500">
                Mode
              </p>
              <p className="text-sm font-medium text-black">
                Mobile first, clean shell
              </p>
            </div>
            <ArrowUpRight className="h-4 w-4 text-apple-gray-400" />
          </div>
        </div>
        <nav className="mt-5 flex flex-col gap-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.name}
                to={item.path}
                className={({ isActive }) =>
                  `group flex items-center gap-3 rounded-[22px] border px-4 py-3 transition-all ${
                    isActive
                      ? "border-apple-blue/15 bg-[linear-gradient(135deg,rgba(10,132,255,0.14),rgba(99,102,241,0.10))] text-apple-blue shadow-[0_12px_30px_rgba(10,132,255,0.10)] font-semibold"
                      : "border-transparent text-apple-gray-600 hover:border-apple-gray-200 hover:bg-white hover:text-black"
                  }`
                }
              >
                <span className="flex h-9 w-9 items-center justify-center rounded-2xl bg-white/75 text-current shadow-sm ring-1 ring-black/5 transition-transform group-hover:scale-[1.03]">
                  <Icon className="h-5 w-5" strokeWidth={2} />
                </span>
                <span className="min-w-0 text-sm font-medium">{item.name}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>
    </>
  );
}

export default function App() {
  return (
    <Router>
      <div className="relative isolate flex h-screen w-full overflow-hidden bg-[#eef2f8] text-black">
        <NavigationBar />
        <main className="relative z-10 min-w-0 flex-1 overflow-hidden pt-0 md:pb-0 md:pt-0">
          <Routes>
            <Route path="/" element={<CalendarPage />} />
            <Route path="/tasks" element={<TasksPage />} />
            <Route path="/finances" element={<FinancesPage />} />
            <Route path="/groceries" element={<GroceriesPage />} />
            <Route path="/recipes" element={<RecipesPage />} />
            <Route path="/fitness" element={<FitnessPage />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}
