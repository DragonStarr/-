const icon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="bg" x1="8" x2="56" y1="8" y2="56">
      <stop stop-color="#b6ff2e"/>
      <stop offset="1" stop-color="#07110d"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="18" fill="url(#bg)"/>
  <path d="M17 45V18h7l8 14 8-14h7v27h-8V31l-7 12h-1l-7-12v14z" fill="#f6fff0"/>
  <path d="M9 9h44" stroke="#1d8bff" stroke-width="5" stroke-linecap="round"/>
  <path d="M9 18h44" stroke="#f03b9f" stroke-width="5" stroke-linecap="round"/>
  <path d="M9 27h44" stroke="#2bd7ff" stroke-width="5" stroke-linecap="round"/>
</svg>`;

export function GET() {
  return new Response(icon, {
    headers: {
      "Cache-Control": "public, max-age=31536000, immutable",
      "Content-Type": "image/svg+xml"
    }
  });
}
