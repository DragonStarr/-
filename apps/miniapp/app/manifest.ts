import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "мпомощник: Оператор дня",
    short_name: "мпомощник",
    description: "Telegram Mini App и PWA для ежедневных дел селлера и ПВЗ.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#eef3ef",
    theme_color: "#b6ff2e",
    icons: [
      {
        src: "/favicon.ico",
        sizes: "any",
        type: "image/svg+xml"
      }
    ]
  };
}
