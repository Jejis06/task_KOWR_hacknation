import { ParcelPage } from "./pages/ParcelPage";

export default function App() {
  return (
    <div className="app">
      <a className="skip" href="#main">Przejdź do treści</a>
      <header className="app-header">
        <h1>Zatrzymaj wodę</h1>
        <span className="subtitle">wszystkie dane o wodzie na Twojej działce w jednym miejscu</span>
      </header>
      <main id="main">
        <ParcelPage />
      </main>
      <footer className="app-footer">
        Prototyp HackNation 2026 (zadanie KOWR) · dane publiczne: GUGiK, IMGW-PIB, IUNG-PIB, Copernicus, Wody Polskie, PIG-PIB, GUS,
        Open-Meteo (ERA5), NASA POWER · mapa © OpenStreetMap · bez logowania, bez analityki, bez zbierania danych osobowych.
      </footer>
    </div>
  );
}
