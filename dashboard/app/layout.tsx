import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "bob-resolve",
  description:
    "Decides which records in an agency book of business are the same real person, and explains every merge. Synthetic data only.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
        {children}
      </body>
    </html>
  );
}
