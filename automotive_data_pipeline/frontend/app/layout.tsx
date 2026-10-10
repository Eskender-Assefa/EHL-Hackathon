import "./styles.css";

export const metadata = { title: "BMW PM Cockpit", description: "Evidence-linked requirement decisions" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
