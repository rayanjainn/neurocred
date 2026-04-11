"use client";
import { AuthProvider } from "@/dib/authContext";
import { AppShell } from "@/components/AppShell";
import { ReactLenis } from "@studio-freight/react-lenis";
import { ThemeProvider } from "@/components/theme-provider";
import { VoiceControlProvider } from "@/src/voice/VoiceControlProvider";

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <ReactLenis root options={{ lerp: 0.08, duration: 1.2, smoothWheel: true }}>
        <AuthProvider>
          <VoiceControlProvider>
            <AppShell>{children}</AppShell>
          </VoiceControlProvider>
        </AuthProvider>
      </ReactLenis>
    </ThemeProvider>
  );
}
