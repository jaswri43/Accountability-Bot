import { BrowserRouter, Navigate, Route, Routes, useSearchParams } from "react-router-dom";
import { AppearanceProvider } from "./context/AppearanceContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { Layout } from "./components/Layout";
import { Loading } from "./components/ui";
import { Deadlock } from "./pages/Deadlock";
import { History } from "./pages/History";
import { League } from "./pages/League";
import { Login } from "./pages/Login";
import { Overview } from "./pages/Overview";
import { PlayerProfile } from "./pages/PlayerProfile";
import { Players } from "./pages/Players";
import { Templates } from "./pages/Templates";

/** The game views used to be Dashboard tabs at /?tab=league|deadlock;
 * keep those old links working. */
function Home() {
  const [searchParams] = useSearchParams();
  const tab = searchParams.get("tab");
  if (tab === "league" || tab === "deadlock") return <Navigate to={`/${tab}`} replace />;
  return <Overview />;
}

function Gate() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <Loading />
      </div>
    );
  }

  if (!user) {
    return <Login />;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="league" element={<League />} />
          <Route path="deadlock" element={<Deadlock />} />
          <Route path="players" element={<Players />} />
          <Route path="players/:discordId" element={<PlayerProfile />} />
          <Route path="templates" element={<Templates />} />
          <Route path="history" element={<History />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppearanceProvider>
        <Gate />
      </AppearanceProvider>
    </AuthProvider>
  );
}

export default App;
