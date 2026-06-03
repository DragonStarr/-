import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "мпомощник",
  description: "Оператор дня для селлеров и ПВЗ",
  applicationName: "мпомощник",
  appleWebApp: {
    capable: true,
    title: "мпомощник",
    statusBarStyle: "black-translucent"
  },
  icons: {
    icon: "/favicon.ico"
  }
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#b6ff2e"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
