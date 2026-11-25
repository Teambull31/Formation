// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('../api', async (orig) => {
  const real = await orig<typeof import('../api')>()
  return { ...real, getOral: vi.fn(), answerOral: vi.fn(), addPanne: vi.fn(), getMissions: vi.fn(), checkMission: vi.fn(),
    proveMission: vi.fn(), getArticles: vi.fn(), saveArticle: vi.fn(), getCert: vi.fn(), setCert: vi.fn() }
})
import * as api from '../api'
import Oral from './Oral'
import Panne from './Panne'
import Missions from './Missions'
import Articles from './Articles'
import Cert from './Cert'

afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals() })

test('révision orale : lit, écoute, envoie la réponse dictée', async () => {
  const spoken: string[] = []
  vi.stubGlobal('SpeechSynthesisUtterance', class { text: string; onend?: () => void; constructor(t: string) { this.text = t } })
  vi.stubGlobal('speechSynthesis', { speak: (u: { text: string; onend?: () => void }) => { spoken.push(u.text); setTimeout(() => u.onend?.(), 0) }, cancel: vi.fn() })
  vi.stubGlobal('webkitSpeechRecognition', class {
    onresult: ((e: unknown) => void) | null = null
    onend: (() => void) | null = null
    start() { setTimeout(() => { this.onresult?.({ results: [[{ transcript: 'workflow' }]] }); this.onend?.() }, 0) }
    stop() {}
  })
  vi.mocked(api.getOral).mockResolvedValue({ items: [{ kind: 'card', id: 'c1', prompt: 'Un blanc est un fichier YAML.' }] })
  vi.mocked(api.answerOral).mockResolvedValue({ correct: true, answer: 'workflow', explain: '' })
  render(<Oral />)
  fireEvent.click(screen.getByText('Commencer la révision orale'))
  await waitFor(() => expect(api.answerOral).toHaveBeenCalledWith('card', 'c1', 'workflow'))
  await waitFor(() => expect(spoken.some((t) => t.startsWith('Terminé : 1 sur 1'))).toBe(true))
  expect(spoken.some((t) => t.includes('Un blanc est un fichier YAML.'))).toBe(true)
})

test('révision orale indisponible sans reconnaissance vocale', () => {
  render(<Oral />)
  expect(screen.getByText(/Reconnaissance vocale indisponible/)).toBeTruthy()
})

test('panne résolue devient une carte', async () => {
  vi.mocked(api.addPanne).mockResolvedValue({ id: 'panne-1' })
  const onAdded = vi.fn()
  render(<Panne onAdded={onAdded} />)
  fireEvent.click(screen.getByText(/J'ai résolu une panne/))
  fireEvent.change(screen.getByLabelText('Symptôme'), { target: { value: 'checkout refusé' } })
  fireEvent.change(screen.getByLabelText('Cause'), { target: { value: 'fichiers root' } })
  fireEvent.change(screen.getByLabelText('Correction'), { target: { value: 'vider le workspace' } })
  fireEvent.click(screen.getByText('Créer la carte'))
  await waitFor(() => expect(onAdded).toHaveBeenCalled())
  expect(api.addPanne).toHaveBeenCalledWith('checkout refusé', 'fichiers root', 'vider le workspace')
})

test('mission : vérification et lien de preuve', async () => {
  const m = { id: 'm1', module: 'cicd', title: 'CI mcs', goal: 'G', steps: ['a'], checkable: true, done: false, proof: null, ready: true }
  vi.mocked(api.getMissions).mockResolvedValue([m])
  vi.mocked(api.checkMission).mockResolvedValue({ passed: false, output: 'run rouge', xp: 0 })
  vi.mocked(api.proveMission).mockResolvedValue({ xp: 200 })
  render(<Missions />)
  fireEvent.click(await screen.findByText('Vérifier sur ce PC'))
  expect(await screen.findByText(/run rouge/)).toBeTruthy()
  fireEvent.change(screen.getByPlaceholderText('https://github.com/…'), { target: { value: 'https://github.com/a/b/pull/1' } })
  fireEvent.click(screen.getByText('Valider'))
  await waitFor(() => expect(api.proveMission).toHaveBeenCalledWith('m1', 'https://github.com/a/b/pull/1'))
})

test('article : compteur de mots et enregistrement', async () => {
  vi.mocked(api.getArticles).mockResolvedValue([{ id: 'cicd', title: 'CI/CD', text: '', unlocked: true }])
  vi.mocked(api.saveArticle).mockResolvedValue({ xp: 50, words: 3 })
  render(<Articles />)
  fireEvent.change(await screen.findByLabelText(/CI\/CD/), { target: { value: 'un deux trois' } })
  expect(screen.getByText('CI/CD · 3 mots')).toBeTruthy()
  fireEvent.click(screen.getByText('Enregistrer'))
  expect(await screen.findByText(/\+50 XP/)).toBeTruthy()
})

test('certification : choisir puis afficher le compte à rebours', async () => {
  const opts = [{ key: 'terraform', title: 'HashiCorp Terraform Associate' }]
  vi.mocked(api.getCert).mockResolvedValueOnce({ key: null, date: null, title: null, days_left: null, options: opts })
    .mockResolvedValue({ key: 'terraform', date: '2027-01-10', title: 'HashiCorp Terraform Associate', days_left: 46, options: opts })
  vi.mocked(api.setCert).mockResolvedValue({ ok: true })
  render(<Cert />)
  fireEvent.click(await screen.findByText(/Viser une certification/))
  fireEvent.change(screen.getByLabelText("Date de l'examen"), { target: { value: '2027-01-10' } })
  await act(async () => { fireEvent.click(screen.getByText('Enregistrer')) })
  expect(api.setCert).toHaveBeenCalledWith('terraform', '2027-01-10')
  expect(await screen.findByText(/J-46/)).toBeTruthy()
})
