import React from 'react';
import { describe, test, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
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
