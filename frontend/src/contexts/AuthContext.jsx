import { createContext, useContext, useState, useCallback } from "react";

const AuthContext = createContext(null);

/**
 * Decode a JWT payload without verifying the signature.
 * Verification is the server's job; we just need the claims for UI decisions.
 */
function decodeJwt(token) {
  try {
    const payload = token.split(".")[1];
    return JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
  } catch {
    return null;
  }
}

function isExpired(claims) {
  if (!claims?.exp) return true;
  return Date.now() / 1000 > claims.exp;
}

function loadFromStorage() {
  const token = localStorage.getItem("docgen_token");
  if (!token) return { token: null, user: null };
  const claims = decodeJwt(token);
  if (!claims || isExpired(claims)) {
    localStorage.removeItem("docgen_token");
    return { token: null, user: null };
  }
  return {
    token,
    user: { id: claims.sub, name: claims.name, email: claims.email, role: claims.role },
  };
}

function loadProject() {
  try {
    return JSON.parse(localStorage.getItem("docgen_project") || "null");
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [{ token, user }, setAuth] = useState(loadFromStorage);
  const [currentProject, setCurrentProjectState] = useState(loadProject);

  const login = useCallback((newToken) => {
    localStorage.setItem("docgen_token", newToken);
    const claims = decodeJwt(newToken);
    setAuth({
      token: newToken,
      user: claims
        ? { id: claims.sub, name: claims.name, email: claims.email, role: claims.role }
        : null,
    });
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("docgen_token");
    localStorage.removeItem("docgen_project");
    setAuth({ token: null, user: null });
    setCurrentProjectState(null);
  }, []);

  const setCurrentProject = useCallback((project) => {
    if (project) {
      localStorage.setItem("docgen_project", JSON.stringify(project));
    } else {
      localStorage.removeItem("docgen_project");
    }
    setCurrentProjectState(project);
  }, []);

  /** Helper used by API calls to attach Authorization header. */
  const authHeaders = useCallback(
    () => (token ? { Authorization: `Bearer ${token}` } : {}),
    [token]
  );

  const isAdmin = user?.role === "admin";
  const isApprover = user?.role === "approver" || isAdmin;

  return (
    <AuthContext.Provider value={{
      user, token, login, logout, authHeaders, isAdmin, isApprover,
      currentProject, setCurrentProject,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
