import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ThemeProvider } from "next-themes";
import App from "./App.tsx";
import "./index.css";
import { useGoogleOAuth } from "./hooks/useGoogleOAuth";

const AppWithOAuth = () => {
  useGoogleOAuth();
  return <App />;
};

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
        <AppWithOAuth />
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>,
);
