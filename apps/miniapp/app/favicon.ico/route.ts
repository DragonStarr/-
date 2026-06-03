const icon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="8" fill="#10151c"/>
  <path d="M15 -4h10L8 68H-2z" fill="#00a3ff"/>
  <path d="M31 -4h10L24 68H14z" fill="#182d86"/>
  <path d="M47 -4h10L40 68H30z" fill="#f03242"/>
  <circle cx="34" cy="32" r="17" fill="#b6ff2e"/>
  <path d="M24 43V21h5l5 9 5-9h5v22h-6V32l-4 7h-1l-4-7v11z" fill="#10151c"/>
</svg>`;

export function GET() {
  return new Response(icon, {
    headers: {
      "Cache-Control": "public, max-age=31536000, immutable",
      "Content-Type": "image/svg+xml"
    }
  });
}
