import { ParcelPage } from "./pages/ParcelPage";

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>Zatrzymaj wodę</h1>
        <span className="subtitle">dane o Twojej działce w jednym miejscu</span>
      </header>
      <main>
        <ParcelPage />
      </main>
      <footer className="app-footer">
        Prototyp HackNation 2026 · dane publiczne (GUGiK, IMGW, IUNG-PIB, Copernicus, Wody Polskie, PIG-PIB, GUS)
      </footer>
    </div>
  );
}
