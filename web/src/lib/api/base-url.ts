// Where the browser sends API requests. A set NEXT_PUBLIC_API_URL always wins, and an
// empty one means the page's own origin. When it is unset, `next dev` calls FastAPI on
// localhost:8000 directly, and a production build calls the origin that served the page,
// because FastAPI serves the static export and the API together.
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : '')
