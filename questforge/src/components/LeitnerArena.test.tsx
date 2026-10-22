import React from 'react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LeitnerArena } from './LeitnerArena';
import { api } from '../api';

vi.mock('canvas-confetti', () => ({ default: vi.fn() }));

const question = {
  id: 'q_test',
  text: 'Quelle option est la bonne ?',
  options: ['Option A', 'Option B', 'Option C', 'Option D'],
  explain: '',
  box: 0,
};

function renderArena() {
  return render(<LeitnerArena onClose={vi.fn()} onRefreshQuest={vi.fn()} onSelectLesson={vi.fn()} />);
}

describe('LeitnerArena', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, 'getReviews').mockResolvedValue({ due: [question], boxesCount: [1, 0, 0, 0, 0] });
  });

  test('le verdict vient du serveur, pas de la position de l\'option', async () => {
    const answer = vi
      .spyOn(api, 'answerQcm')
      .mockResolvedValue({ correct: true, explanation: 'Parce que A.', remedial_lesson_id: null });
    renderArena();

    // l'option 0 (et non 1) est la bonne côté serveur
    fireEvent.click(await screen.findByText('Option A'));
    fireEvent.click(screen.getByText('Valider la réponse'));

    await waitFor(() => expect(screen.getByText(/Bonne réponse/)).not.toBeNull());
    expect(answer).toHaveBeenCalledWith('q_test', 0);
    expect(screen.getByText('Parce que A.')).not.toBeNull();
  });

  test('choisir la 2e option n\'est pas correct si le serveur dit le contraire', async () => {
    vi.spyOn(api, 'answerQcm').mockResolvedValue({
      correct: false,
      explanation: 'Non, c\'était A.',
      remedial_lesson_id: 'l1',
    });
    renderArena();

    fireEvent.click(await screen.findByText('Option B'));
    fireEvent.click(screen.getByText('Valider la réponse'));

    await waitFor(() => expect(screen.getByText(/Erreur : rétrogradé/)).not.toBeNull());
    expect(screen.queryByText(/Bonne réponse/)).toBeNull();
  });
});
