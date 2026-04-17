import type { Metadata } from "next";
import { Inter, Fira_Code } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { cn } from "@/lib/utils";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });
const firaCode = Fira_Code({ subsets: ["latin"], variable: "--font-mono", weight: ["400", "500"] });

export const metadata: Metadata = {
  title: "DocChat AI – AI-Powered Document Q&A",
  description:
    "Upload PDFs, audio, and video files. Ask questions and get instant answers powered by Llama 3.1 70B with semantic search and timestamp extraction.",
  keywords: ["AI", "document", "chatbot", "PDF", "audio", "video", "Q&A", "LLM"],
  openGraph: {
    title: "DocChat AI",
    description: "AI-powered document & multimedia Q&A",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={cn(inter.variable, firaCode.variable)}>
      <body className="font-sans antialiased">
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem
          disableTransitionOnChange
        >
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
