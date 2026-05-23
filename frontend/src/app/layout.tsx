import type { Metadata } from "next";
import "reactflow/dist/style.css";
import "../styles/app.css";

export const metadata: Metadata = {
  title: "Codebase Cartographer",
  description:
    "Structural forensics dashboard for repository graphing and AI-assisted analysis.",
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
