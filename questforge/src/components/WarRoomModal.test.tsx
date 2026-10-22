import React from 'react';
import { describe, test, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { WarRoomModal } from './WarRoomModal';

describe('WarRoomModal', () => {
  test('affiche l’en-tête de la War Room et le tableau télémétrique', async () => {
    const mockClose = vi.fn();
    const mockRefresh = vi.fn();

    render(<WarRoomModal onClose={mockClose} onRefreshQuest={mockRefresh} />);

    await waitFor(() => {
      expect(screen.getByText(/War Room — Astreinte Incident P1/i)).not.toBeNull();
    });

    expect(screen.getByText(/Chrono/i)).not.toBeNull();
    expect(screen.getByText(/Erreurs 5xx/i)).not.toBeNull();
  });
});
