import React from 'react';
import { describe, test, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { WeeklyScreen } from './Weekly';
import { api } from '../api';

describe('WeeklyScreen', () => {
  test("après un import refusé (422 avec errors), la liste des erreurs s'affiche et aucun message de succès n'apparaît", async () => {
    // Mock importModule to reject with 422 errors
    const errorObj: any = new Error('HTTP 422');
    errorObj.status = 422;
    errorObj.errors = [
      'Fichier manquant: module.json',
      'Question q1: answer (5) hors limites pour options (taille 3)',
    ];

    vi.spyOn(api, 'importModule').mockRejectedValueOnce(errorObj);
    const mockOnImported = vi.fn();

    render(<WeeklyScreen onModuleImported={mockOnImported} />);

    // Click on import button
    const importButton = screen.getByRole('button', { name: /Valider et Importer le Module/i });
    fireEvent.click(importButton);

    // Wait for errors to appear in UI
    await waitFor(() => {
      expect(screen.getByText(/Import refusé : 2 anomalies détectées/i)).not.toBeNull();
    });

    expect(screen.getByText('Fichier manquant: module.json')).not.toBeNull();
    expect(
      screen.getByText('Question q1: answer (5) hors limites pour options (taille 3)')
    ).not.toBeNull();

    // Verify no success message appears
    expect(screen.queryByText(/importé et validé avec succès/i)).toBeNull();
    expect(mockOnImported).not.toHaveBeenCalled();
  });
});
