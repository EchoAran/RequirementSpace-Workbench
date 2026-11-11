import { act, render, type RenderOptions } from '@testing-library/react';
import type { ReactNode } from 'react';

export async function renderWithEffects(ui: ReactNode, options?: RenderOptions) {
  let view!: ReturnType<typeof render>;
  await act(async () => {
    view = render(ui, options);
  });
  return {
    ...view,
    rerender: async (nextUi: ReactNode) => {
      await act(async () => view.rerender(nextUi));
    },
  };
}
