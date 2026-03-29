import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';
import { Calendar, CreditCard, ShoppingBasket, ChefHat, Activity, CheckSquare } from 'lucide-react';
import CalendarPage from './pages/CalendarPage';
import TasksPage from './pages/TasksPage';
import FinancesPage from './pages/FinancesPage';
import GroceriesPage from './pages/GroceriesPage';
import RecipesPage from './pages/RecipesPage';

function NavigationBar() {
  const navItems = [
    { name: 'Calendar', path: '/', icon: Calendar },
    { name: 'Tasks', path: '/tasks', icon: CheckSquare },
    { name: 'Finances', path: '/finances', icon: CreditCard },
    { name: 'Groceries', path: '/groceries', icon: ShoppingBasket },
    { name: 'Recipes', path: '/recipes', icon: ChefHat },
    { name: 'Fitness', path: '/fitness', icon: Activity },
  ];

  return (
    <>
      {/* Mobile Bottom Navigation */}
      <div className="md:hidden fixed bottom-0 left-0 w-full bg-white/90 backdrop-blur-lg border-t border-apple-gray-200 safe-bottom z-50">
        <div className="flex justify-around items-center h-20 px-2 pb-4">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.name}
                to={item.path}
                className={({ isActive }) =>
                  `flex flex-col items-center justify-center w-16 space-y-1 transition-colors ${
                    isActive ? 'text-apple-blue' : 'text-apple-gray-500 hover:text-black'
                  }`
                }
              >
                <Icon className="w-6 h-6" strokeWidth={2} />
                <span className="text-[10px] font-medium">{item.name}</span>
              </NavLink>
            );
          })}
        </div>
      </div>

      {/* Desktop Sidebar Navigation */}
      <div className="hidden md:flex flex-col w-64 h-full bg-apple-gray-100 border-r border-apple-gray-200 p-4 shrink-0">
        <div className="mb-8 mt-4 px-4">
          <h1 className="text-xl font-bold tracking-tight text-black">AdamHUB</h1>
        </div>
        <nav className="flex flex-col space-y-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.name}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors ${
                    isActive ? 'bg-apple-blue/10 text-apple-blue font-semibold' : 'text-apple-gray-600 hover:bg-apple-gray-200 hover:text-black'
                  }`
                }
              >
                <Icon className="w-5 h-5" strokeWidth={2} />
                <span className="text-sm font-medium">{item.name}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>
    </>
  );
}

function PlaceholderScreen({ title }: { title: string }) {
  return (
    <div className="flex-1 flex flex-col pt-12 px-8 pb-24 h-full overflow-y-auto">
      <h1 className="text-3xl font-bold mb-6 tracking-tight text-black">{title}</h1>
      <div className="flex-1 flex items-center justify-center text-apple-gray-500">
        <p>Wireframing in progress...</p>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <div className="flex flex-col md:flex-row h-screen bg-white w-full overflow-hidden">
        <NavigationBar />
        <main className="flex-1 overflow-hidden relative pb-20 md:pb-0 bg-white">
          <Routes>
            <Route path="/" element={<CalendarPage />} />
            <Route path="/tasks" element={<TasksPage />} />
            <Route path="/finances" element={<FinancesPage />} />
            <Route path="/groceries" element={<GroceriesPage />} />
            <Route path="/recipes" element={<RecipesPage />} />
            <Route path="/fitness" element={<PlaceholderScreen title="Fitness Tracker" />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}
