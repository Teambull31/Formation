import React from 'react';
import { describe, test, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LessonScreen } from './Lesson';
import { api } from '../api';

// Mock canvas-confetti
vi.mock('canvas-confetti', () => ({
  default: vi.fn(),
}));

describe('LessonScreen - TP and Vim Support', () => {
  test('affiche le bouton TP avec mention déjà validé si isTpCompleted est vrai', async () => {
    render(
      <LessonScreen
        lessonId="l1"
        initialTab="tp"
        isTpCompleted={true}
        onBack={vi.fn()}
        onRefreshQuest={vi.fn()}
      />
    );

    // Should indicate TP is already validated
    await waitFor(
      () => {
        expect(
          screen.getByText(/Tester à nouveau le TP \(Déjà validé ✓\)/i)
        ).not.toBeNull();
      },
      { timeout: 4000 }
    );

    // Check Vim tools toolbar
    expect(screen.getByText(/Outils :/i)).not.toBeNull();
    expect(screen.getByText('vim config.json')).not.toBeNull();
    expect(screen.getByText(/Guide Vim/i)).not.toBeNull();

    // Toggle Vim guide
    fireEvent.click(screen.getByText(/Guide Vim/i));
    expect(screen.getByText(/Raccourcis Essentiels Vim/i)).not.toBeNull();
    expect(screen.getByText(/Sauvegarder & quitter/i)).not.toBeNull();
  });
});
