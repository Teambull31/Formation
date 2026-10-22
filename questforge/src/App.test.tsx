import React from 'react';
import { describe, test, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import App from './App';

describe('App - Focus Mode', () => {
  test('active et désactive le Mode Focus en masquant la navigation inférieure', async () => {
    render(<App />);

    // Initially, bottom navigation is visible
    expect(screen.getByRole('navigation')).not.toBeNull();

    // Find and click the Focus button in the header
    const focusButton = screen.getByTitle(/Activer le mode Focus/i);
    expect(focusButton).not.toBeNull();
    fireEvent.click(focusButton);

    // Focus mode is now active: badge appears
    expect(screen.getByText('SESSION INTENSE')).not.toBeNull();

    // Bottom navigation should now be hidden
    expect(screen.queryByRole('navigation')).toBeNull();

    // Floating exit button should be present
    const exitButton = screen.getByText(/Quitter le mode Focus/i);
    expect(exitButton).not.toBeNull();

    // Clicking exit button restores normal navigation
    fireEvent.click(exitButton);
    expect(screen.getByRole('navigation')).not.toBeNull();
    expect(screen.queryByText('SESSION INTENSE')).toBeNull();
  });
});


describe('App - mode démo hors-ligne', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test('affiche un bandeau explicite quand le backend est injoignable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend injoignable')));
    render(<App />);

    await waitFor(() => expect(screen.getByRole('status')).not.toBeNull());
    expect(screen.getByRole('status').textContent).toMatch(/Mode démo hors-ligne/);
    expect(screen.getByRole('button', { name: 'Réinitialiser' })).not.toBeNull();
  });

  test('pas de bandeau quand le backend répond', async () => {
    const quest = {
      day: '2026-10-22',
      steps: [],
      bonus: null,
      imposed_topic: null,
      streak: 0,
      profile: { total_xp: 0, rank: 'Bronze', skills: {}, tokens: 0 },
    };
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (url: string) =>
        url.includes('/api/quest')
          ? { ok: true, status: 200, json: async () => quest }
          : { ok: true, status: 200, json: async () => ({}) }
      )
    );
    render(<App />);

    await waitFor(() => expect(screen.getByText("Étapes de la quête")).not.toBeNull());
    expect(screen.queryByRole('status')).toBeNull();
  });
});
