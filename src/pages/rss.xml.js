import rss from '@astrojs/rss';
import { allPosts, SITE_NAME, TAGLINE, url } from '../site';

export async function GET(context) {
  const posts = (await allPosts()).slice(0, 50);
  return rss({
    title: SITE_NAME, description: TAGLINE, site: context.site,
    items: posts.map((p) => ({ title: p.data.title, description: p.data.description, pubDate: p.data.date, link: url(`posts/${p.id}/`) })),
  });
}
