import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import cfg from './site.config.json' with { type: 'json' };

export default defineConfig({
  site: cfg.site,
  base: cfg.base,
  trailingSlash: 'always',
  integrations: [sitemap()],
  build: { format: 'directory' },
});
