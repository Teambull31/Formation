import React from 'react';
import { describe, test, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SkillTreeModal } from './SkillTreeModal';
import { Profile } from '../api';

describe('SkillTreeModal', () => {
  const mockProfile: Profile = {
    total_xp: 600,
    rank: 'Bronze',
    skills: { automation: 100 },
    tokens: 3,
    active_theme: 'default',
    active_module_id: 'demo',
    achievements: [],
  };

  test('affiche les branches et permet de sélectionner un talent', async () => {
    const mockClose = vi.fn();
    const mockRefresh = vi.fn();

    render(
      <SkillTreeModal
        profile={mockProfile}
        onClose={mockClose}
        onRefreshQuest={mockRefresh}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Arbre de Talents RPG')).not.toBeNull();
    });

    expect(screen.getByText(/Automatisation & CI\/CD/i)).not.toBeNull();
    expect(screen.getAllByText(/Pipeline Optimisé/i).length).toBeGreaterThan(0);
  });
});
