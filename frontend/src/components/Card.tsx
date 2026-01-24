import { ReactNode } from "react";

export default function Card({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        background: "white",
        borderRadius: 8,
        padding: 16,
        boxShadow: "0 1px 4px rgba(0,0,0,0.08)",
        marginBottom: 16,
      }}
    >
      {children}
    </div>
  );
}
