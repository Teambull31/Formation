import React from 'react';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BossScreen } from './Boss';
import { api, BossEntity, BossData, resetOfflineDemo } from '../api';

const realBoss: BossEntity = {
  id: 'boss_terraform',
  title: 'Le Gardien du State Terraform',
  description: 'Un dépôt négligé.',
  avatar: '🐉',
  color: 'from-violet-500/20 to-indigo-950/40 border-violet-700/50',
  phases: [
    { pattern_id: 'p1', label: 'Phase 1 : config cassée', check: 'main.tf valide', remedial_lesson_id: 'tf1' },
  ],
};
const realData: BossData = { boss: realBoss, attempts_count: 0, history: [] };

function renderBoss(bossData: BossData | null = null) {
  return render(<BossScreen bossData={bossData} loading={false} onRefresh={vi.fn()} onSelectLesson={vi.fn()} />);
}

describe('BossScreen', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    resetOfflineDemo();
  });

  test('affiche les boss fournis par le backend à la place de la démo', async () => {
    vi.spyOn(api, 'getBosses').mockResolvedValue([realBoss]);
    vi.spyOn(api, 'getBoss').mockResolvedValue(realData);
    renderBoss(null);

    await waitFor(() => expect(screen.getAllByText('Le Gardien du State Terraform').length).toBeGreaterThan(0));
    expect(screen.getByText(/Vérification : main\.tf valide/)).not.toBeNull();
    expect(screen.queryByText(/Léviathan/)).toBeNull();
    expect(screen.queryByText(/Combat simulé/)).toBeNull();
  });

  describe('sans backend', () => {
    beforeEach(() => {
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend injoignable')));
      resetOfflineDemo();
    });

    test('la démo annonce que les combats sont simulés', async () => {
      renderBoss(null);
      await waitFor(() => expect(screen.getAllByText(/Combat simulé/).length).toBeGreaterThan(0));
      expect(screen.queryByText(/echo "CoreDNS/)).toBeNull();
    });
  });
});
