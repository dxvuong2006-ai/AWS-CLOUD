import { useEffect, useState } from "react";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { AuthProvider } from "./context/AuthContext";
import logo from "./public/logo.png";

export default function Root() {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setLoading(false);
    }, 1500);

    return () => clearTimeout(timer);
  }, []);

  if (loading) {
    return (
      <div
        style={{
          position: "fixed",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#ffffff",
          zIndex: 9999,
        }}
      >
        <img
          src={logo}
          alt="LearnCloud"
          style={{
            width: "500px",
            height: "500px",
            objectFit: "contain",
            animation: "logoFade 0.8s ease-in-out",
          }}
        />

        <style>
          {`
            @keyframes logoFade {
              from {
                opacity: 0;
                transform: scale(0.85);
              }
              to {
                opacity: 1;
                transform: scale(1);
              }
            }
          `}
        </style>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  );
}
