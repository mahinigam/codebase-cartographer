import type { Metadata, Viewport } from "next";
import "../styles/app.css";

export const metadata: Metadata = {
  title: "Codebase Cartographer",
  description:
    "Structural forensics dashboard for repository graphing and AI-assisted analysis.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
