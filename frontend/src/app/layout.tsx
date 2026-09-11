import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Inquiro — Da pergunta ao insight",
  description:
    "Plataforma inteligente que transforma perguntas em linguagem natural em consultas SQL precisas.",
};

// Aplica a preferência de tema antes da hidratação — evita flash de dark→light.
const THEME_SCRIPT = `(function(){try{if(localStorage.getItem('inquiro-theme')==='light'){document.documentElement.classList.add('light')}}catch(e){}})();`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="pt-BR"
      className={`${inter.variable} ${jetbrainsMono.variable} dark h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="flex h-full min-h-full flex-col font-sans">{children}</body>
    </html>
  );
}
