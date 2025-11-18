import { useEffect, useState } from "react";
import { AuthProvider } from "./AuthContext";
import { ProjectProvider } from "./ProjectContext";
import { ExportProvider } from "./ExportContext";
import { BlobProvider } from "./BlobContext";
import { RateCardProvider } from "./RateCardContext";
import { PromptsProvider } from "./PromptsContext";
import { ETLProvider } from "./ETLContext";
import { ToastContainer } from "react-toastify";
import { ErrorBoundary } from "react-error-boundary";
import "react-toastify/dist/ReactToastify.css";

function useToastTheme() {
  const [theme, setTheme] = useState(() => {
    if (typeof document !== "undefined") {
      if (document.documentElement.classList.contains("dark")) return "dark";
    }
    if (typeof window !== "undefined" && window.matchMedia) {
      return window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
    }
    return "light";
  });

  useEffect(() => {
    const update = () => {
      setTheme(
        document.documentElement.classList.contains("dark") ? "dark" : "light"
      );
    };

    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });

    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setTheme(mq.matches ? "dark" : "light");
    mq.addEventListener?.("change", onChange);

    return () => {
      observer.disconnect();
      mq.removeEventListener?.("change", onChange);
    };
  }, []);

  return theme;
}

function ErrorFallback({ error }) {
  return (
    <div role="alert" className="p-4 bg-red-100 text-red-600">
      <p className="font-semibold">Something went wrong</p>
      <pre className="whitespace-pre-wrap">{error.message}</pre>
    </div>
  );
}

export default function AppProviders({ children }) {
  const toastTheme = useToastTheme();

  return (
    <AuthProvider>
      <ProjectProvider>
        <ExportProvider>
          <BlobProvider>
            <RateCardProvider>
              <PromptsProvider>
                <ETLProvider>
                  <ErrorBoundary FallbackComponent={ErrorFallback}>
                    {children}
                    <ToastContainer
                      containerId="root-toaster"
                      position="top-right"
                      autoClose={3000}
                      newestOnTop
                      closeOnClick
                      pauseOnFocusLoss={false}
                      draggable
                      pauseOnHover
                      limit={3}
                      theme={toastTheme}
                    />
                  </ErrorBoundary>
                </ETLProvider>
              </PromptsProvider>
            </RateCardProvider>
          </BlobProvider>
        </ExportProvider>
      </ProjectProvider>
    </AuthProvider>
  );
}
