import React from 'react';
import { describe, test, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { CustomChallengeModal } from './CustomChallengeModal';

// Mock canvas-confetti
vi.mock('canvas-confetti', () => ({
  default: vi.fn(),
}));

describe('CustomChallengeModal', () => {
  test('génère un défi sans afficher la solution directement sous les yeux', async () => {
    const mockClose = vi.fn();
    const mockRefresh = vi.fn();

    render(
      <CustomChallengeModal
        onClose={mockClose}
        onRefreshQuest={mockRefresh}
      />
    );

    // Initial state: suggestions are present
    expect(screen.getByText('Générateur Instantané de Défis & TP')).not.toBeNull();
    const caddyButton = screen.getByText(/Reverse Proxy Caddy avec mTLS/i);
    expect(caddyButton).not.toBeNull();

    // Click quick topic
    fireEvent.click(caddyButton);

    // Verify challenge result appears asynchronously
    const challengeTitle = await screen.findByText(/Mission Spéciale/i);
    expect(challengeTitle).not.toBeNull();

    // Verify solution command is NOT shown directly
    expect(screen.queryByText(/Commande corrigée :/i)).toBeNull();

    // The accordion button to reveal solution is present
    const revealButton = screen.getByText(/Révéler la solution corrigée/i);
    expect(revealButton).not.toBeNull();

    // Clicking it reveals the solution
    fireEvent.click(revealButton);
    expect(screen.getByText(/Commande corrigée :/i)).not.toBeNull();

    // Verify validation button works
    const validateButton = screen.getByText(/Valider ce Défi dans l'Espace de Travail/i);
    fireEvent.click(validateButton);

    await waitFor(() => {
      expect(screen.getByText(/Défi personnalisé validé avec succès/i)).not.toBeNull();
    });
    expect(mockRefresh).toHaveBeenCalled();
  });
});
