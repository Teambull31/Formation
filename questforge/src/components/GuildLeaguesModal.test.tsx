import React from 'react';
import { describe, test, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { GuildLeaguesModal } from './GuildLeaguesModal';
import { api, resetOfflineDemo } from '../api';

const league = {
  currentTier: 'gold' as const,
  timeRemainingDays: 3,
  leaderboard: [{ rank: 1, name: 'Sarah_SRE', avatar: '👩‍💻', xpThisWeek: 490, tier: 'gold' as const }],
  guildMissions: [
    { id: 'm1', title: 'Runbooks', description: 'Fiche', target: 10, current: 10, unit: 'Runbooks', completed: true, rewardTokens: 1 },
  ],
};

describe('GuildLeaguesModal', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    resetOfflineDemo();
  });

  test('annonce la simulation et ne propose aucune récompense réclamable', async () => {
    vi.spyOn(api, 'getLeagueData').mockResolvedValue(league);
    render(<GuildLeaguesModal onClose={vi.fn()} />);

    await waitFor(() => expect(screen.getByText(/Ligue & Guilde SRE · Simulation/)).not.toBeNull());
    fireEvent.click(screen.getByText('Missions Collectives de Guilde'));

    expect(screen.getByText(/ces missions et les autres joueurs sont fictifs/)).not.toBeNull();
    expect(screen.getByText('Objectif atteint (fictif)')).not.toBeNull();
    expect(screen.queryByText(/Réclamer/)).toBeNull();
    expect(screen.queryByText(/\+1 Jetons/)).toBeNull();
    expect(screen.queryByText(/temps réel/)).toBeNull();
  });

  test('en démo, réclamer une mission ne donne jamais de jeton', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend injoignable')));
    resetOfflineDemo();
    const before = (await api.getTeam()).profile.tokens;
    const res = await api.claimGuildMission('m1');
    expect(res.tokensAwarded).toBe(0);
    expect((await api.getTeam()).profile.tokens).toBe(before);
  });
});
