import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Matchbook — Resume alignment",
  description: "Compare a resume with a job description and get evidence based suggestions.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
