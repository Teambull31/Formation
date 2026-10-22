import React from 'react';
import { describe, test, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ClaudeCodePromptModal } from './ClaudeCodePromptModal';

describe('ClaudeCodePromptModal', () => {
  test('affiche le prompt et permet de le copier et de fermer', () => {
    const handleClose = vi.fn();
    render(<ClaudeCodePromptModal onClose={handleClose} />);

    // Check title presence via heading
    expect(
      screen.getByRole('heading', { name: /Prompt Claude Code/i })
    ).not.toBeNull();

    // Find and click copy button
    const copyBtn = screen.getByText(/Copier le Prompt/i);
    expect(copyBtn).not.toBeNull();
    fireEvent.click(copyBtn);

    expect(screen.getByText(/Copié dans le presse-papier !/i)).not.toBeNull();

    // Find and click close button
    const closeBtn = screen.getByText('Fermer');
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });
});
