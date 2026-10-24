import cfg from '../site.config.json';
import { getCollection, type CollectionEntry } from 'astro:content';

export const SITE_NAME = cfg.siteName;
export const TAGLINE = cfg.tagline;
export const CFG = cfg;
export const CONTACT = cfg.contact;
export const SERVICES = cfg.services;
export const CITIES = cfg.cities.map(([slug, name]) => ({ slug, name }));

export const CATEGORIES: Record<string, string> = {
  'xiangmu': '验血项目',
  'jiage': '价格费用',
  'jigou': '机构选择',
  'yunqi': '孕期检查',
  'tijian': '体检套餐',
  'liucheng': '流程攻略',
  'baogao': '报告解读',
};
export const catSlug = (name: string) =>
  Object.keys(CATEGORIES).find((k) => CATEGORIES[k] === name) ?? 'xiangmu';

// 带 base 前缀的站内链接
export const url = (p = '') => {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '');
  return `${base}/${p.replace(/^\//, '')}`;
};

export async function allPosts(): Promise<CollectionEntry<'posts'>[]> {
  const posts = await getCollection('posts');
  return posts.sort((a, b) => b.data.date.valueOf() - a.data.date.valueOf());
}

export const fmtDate = (d: Date) => d.toISOString().slice(0, 10);

// 咨询入口：有电话用电话，否则去联系页
export const ctaHref = () => (CONTACT.phone ? `tel:${CONTACT.phone}` : url('contact/'));

export const faqLd = (faq: { q: string; a: string }[]) => ({
  '@context': 'https://schema.org', '@type': 'FAQPage',
  mainEntity: faq.map((f) => ({ '@type': 'Question', name: f.q, acceptedAnswer: { '@type': 'Answer', text: f.a } })),
});
