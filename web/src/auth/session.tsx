// Login for the web app (CONTEXT §9 "Cognito", §7.1 auth). Tracker: M1-05.
//
// The rest of the app only uses `useSession()`. Two implementations sit behind it:
// - Cognito (normal builds): react-oidc-context does the OAuth authorization code flow
//   with PKCE against the user pool, through Cognito's managed login pages. The access
//   token goes on every API call (the API's JWT authorizer expects access tokens).
// - Mock (VITE_USE_MOCKS=true): always signed in as a demo listener, no network.

import { createContext, useContext, useEffect, useMemo } from "react";
import type { ReactNode } from "react";
import { AuthProvider, useAuth } from "react-oidc-context";
import { WebStorageStateStore } from "oidc-client-ts";
import type { UserManagerSettings } from "oidc-client-ts";
import { setTokenProvider, setUnauthorizedHandler } from "../lib/api";
import type { RuntimeConfig } from "../lib/config";

export interface Session {
  status: "loading" | "signedOut" | "signedIn" | "error";
  /** Email of the signed-in user, if any. */
  email: string | null;
  /** Error text when status is "error" (e.g. the login redirect failed). */
  error: string | null;
  /** True in mock mode: there is no real login. */
  isMock: boolean;
  signIn: () => void;
  signOut: () => void;
}

const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within a SessionProvider");
  return ctx;
}

/** Whether `config` has the Cognito values a real login needs. */
export function hasCognitoConfig(config: RuntimeConfig): boolean {
  return Boolean(config.userPoolId && config.webClientId && config.cognitoDomain);
}

/**
 * The redirect target after login and logout. Must match the web client's callback and
 * logout URLs exactly: the CloudFront URL or http://localhost:5173, with no trailing slash.
 */
function appOrigin(): string {
  return window.location.origin;
}

export function oidcSettings(config: RuntimeConfig): UserManagerSettings {
  return {
    authority: `https://cognito-idp.${config.region}.amazonaws.com/${config.userPoolId}`,
    client_id: config.webClientId,
    redirect_uri: appOrigin(),
    response_type: "code", // authorization code; oidc-client-ts adds PKCE automatically
    scope: "openid email profile",
    // Stay signed in across tabs and reloads; tokens are refreshed before they expire.
    userStore: new WebStorageStateStore({ store: window.localStorage }),
    automaticSilentRenew: true,
  };
}

/** Cognito's logout endpoint clears its own session cookie, then returns to the app. */
export function cognitoLogoutUrl(config: RuntimeConfig): string {
  const params = new URLSearchParams({ client_id: config.webClientId, logout_uri: appOrigin() });
  return `${config.cognitoDomain}/logout?${params}`;
}

/** Remove ?code=…&state=… from the address bar after a successful login. */
function onSigninCallback(): void {
  window.history.replaceState({}, document.title, window.location.pathname);
}

export function SessionProvider({
  config,
  mock,
  children,
}: {
  config: RuntimeConfig;
  mock: boolean;
  children: ReactNode;
}) {
  if (mock) return <MockSession>{children}</MockSession>;
  return (
    <AuthProvider {...oidcSettings(config)} onSigninCallback={onSigninCallback}>
      <CognitoSession config={config}>{children}</CognitoSession>
    </AuthProvider>
  );
}

function MockSession({ children }: { children: ReactNode }) {
  const value = useMemo<Session>(
    () => ({
      status: "signedIn",
      email: "demo@earshot.test",
      error: null,
      isMock: true,
      signIn: () => {},
      signOut: () => {},
    }),
    [],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

function CognitoSession({ config, children }: { config: RuntimeConfig; children: ReactNode }) {
  const auth = useAuth();
  const accessToken = auth.user?.access_token ?? null;

  // Keep the API client's token in sync with the current user.
  useEffect(() => {
    setTokenProvider(() => accessToken);
  }, [accessToken]);

  // A 401 from the API means the token is gone or no longer valid: forget it, so the
  // app shows the login screen instead of a broken page.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      void auth.removeUser();
    });
    return () => setUnauthorizedHandler(null);
  }, [auth]);

  const value = useMemo<Session>(() => {
    const signIn = () => {
      void auth.signinRedirect();
    };
    const signOut = () => {
      void auth.removeUser().then(() => {
        window.location.assign(cognitoLogoutUrl(config));
      });
    };
    let status: Session["status"] = "signedOut";
    if (auth.isLoading) status = "loading";
    else if (auth.error) status = "error";
    else if (auth.isAuthenticated) status = "signedIn";
    const email = (auth.user?.profile.email as string | undefined) ?? null;
    return { status, email, error: auth.error?.message ?? null, isMock: false, signIn, signOut };
  }, [auth, config]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
