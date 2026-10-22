import React from 'react';
import { describe, test, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CompanionBar } from './CompanionBar';
import { InventoryItem } from '../api';

describe('CompanionBar', () => {
  const dummyCompanion: InventoryItem = {
    item_id: 'char_hopper',
    name: "Grace l'Amirale",
    type: 'character',
    rarity: 'rare',
    count: 1,
    avatar: '⚓',
    lore: 'Inventrice du compilateur et dompteuse de papillons de nuit.',
    perk: {
      id: 'perk_hopper',
      name: 'Chasse aux Papillons',
      description: "1 premier indice de TP offert sans déduction d'XP chaque jour.",
      bonusType: 'free_hint',
    },
  };

  test('affiche le nom du compagnon et son perk associé', () => {
    const mockOpenTeam = vi.fn();
    render(<CompanionBar companion={dummyCompanion} onOpenTeam={mockOpenTeam} />);

    expect(screen.getByText("Grace l'Amirale")).not.toBeNull();
    expect(screen.getByText('Chasse aux Papillons')).not.toBeNull();
  });

  test("permet de faire défiler les pensées et d'ouvrir l'équipe", () => {
    const mockOpenTeam = vi.fn();
    render(<CompanionBar companion={dummyCompanion} onOpenTeam={mockOpenTeam} />);

    // Click to expand the companion details
    const expandButton = screen.getByRole('button');
    fireEvent.click(expandButton);

    const teamButton = screen.getByText(/Changer de compagnon dans l'Équipe/i);
    fireEvent.click(teamButton);
    expect(mockOpenTeam).toHaveBeenCalledTimes(1);
  });
});
