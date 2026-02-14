import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        lifecycle: {
          onboarded: "#6B7280",
          licensed: "#3B82F6",
          first_sale: "#8B5CF6",
          active: "#10B981",
          productive: "#059669",
          at_risk: "#F59E0B",
          dormant: "#EF4444",
          lapsed: "#9CA3AF",
          terminated: "#374151",
        },
      },
    },
  },
  plugins: [],
};
export default config;
