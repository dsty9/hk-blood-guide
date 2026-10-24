import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const posts = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/posts' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    date: z.coerce.date(),
    updated: z.coerce.date().optional(),
    category: z.string(),
    tags: z.array(z.string()).default([]),
    keyword: z.string().optional(),
    cover: z.string().optional(),
    infographic: z.string().optional(),
    photo: z.string().optional(),
    photoAlt: z.string().optional(),
    photoCredit: z.string().optional(),
    photoCreditUrl: z.string().optional(),
    keypoints: z.array(z.string()).default([]),
    faq: z.array(z.object({ q: z.string(), a: z.string() })).default([]),
  }),
});

// 城市页、服务页：一次性生成的落地页正文
const landing = (dir: string) => defineCollection({
  loader: glob({ pattern: '**/*.md', base: `./src/content/${dir}` }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    faq: z.array(z.object({ q: z.string(), a: z.string() })).default([]),
  }),
});

export const collections = { posts, cities: landing('cities'), services: landing('services') };
