/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // The production image copies .next/standalone and runs server.js directly,
  // so the runtime carries only the modules actually imported.
  // See docker/frontend.Dockerfile.
  output: 'standalone',

  // Nginx owns the public origin and routes /api, /lti, /admin, /static and
  // /media to Django (docker/nginx/conf.d/app.conf). Next.js must not also
  // claim those paths.
  poweredByHeader: false,

  eslint: {
    // Linting runs as its own CI step (task 0.6), so a lint failure is not
    // disguised as a build failure.
    ignoreDuringBuilds: true,
  },

  typescript: {
    // Type errors DO fail the build. This is the one gate that must not be
    // deferred: a type error is a defect, not a style opinion.
    ignoreBuildErrors: false,
  },
};

export default nextConfig;
