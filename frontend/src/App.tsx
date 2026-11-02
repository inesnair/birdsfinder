import { ConsentGate } from "./components/ConsentGate";
import { Shell } from "./components/Shell";
import { About } from "./pages/About";
import { Account } from "./pages/Account";
import { Identify } from "./pages/Identify";
import { Ornithotheque } from "./pages/Ornithotheque";
import { Privacy } from "./pages/Privacy";
import { SpeciesPage } from "./pages/Species";
import { AppProvider, useRoute } from "./state/app";

function Router() {
  const route = useRoute();
  let page;
  if (route.startsWith("/ornithotheque")) page = <Ornithotheque />;
  else if (route.startsWith("/especes")) page = <SpeciesPage />;
  else if (route.startsWith("/compte")) page = <Account />;
  else if (route.startsWith("/a-propos")) page = <About />;
  else if (route.startsWith("/confidentialite")) page = <Privacy />;
  else page = <Identify />;
  return (
    <Shell route={route}>
      {page}
      <ConsentGate />
    </Shell>
  );
}

export function App() {
  return (
    <AppProvider>
      <Router />
    </AppProvider>
  );
}
