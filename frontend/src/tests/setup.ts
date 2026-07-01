import { afterEach, vi } from 'vitest';

const defaultFetch = vi.fn(async () =>
  new Response(JSON.stringify({}), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
);

vi.stubGlobal('fetch', defaultFetch);

afterEach(() => {
  defaultFetch.mockClear();
});
