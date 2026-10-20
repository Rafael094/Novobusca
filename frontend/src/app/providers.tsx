"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { AuthProvider } from "./auth-context";
import { ChatProvider } from "./chat-context";
import { ThemeProvider } from "./theme-context";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            refetchOnWindowFocus: false,
            staleTime: 15_000,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <AuthProvider>
          <ChatProvider>{children}</ChatProvider>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
