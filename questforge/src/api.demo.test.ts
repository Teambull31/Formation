import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { api, resetOfflineDemo } from './api';
import { renderLesson } from './renderLesson';

// Sans backend, l'API retombe sur les données de démonstration locales.
beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend injoignable')));
  resetOfflineDemo();
});

afterEach(() => {
  vi.unstubAllGlobals();
  resetOfflineDemo();
});

describe('démo hors-ligne : module Terraform', () => {
  test('le module est proposé avec ses métadonnées issues de module.json', async () => {
    const modules = await api.getModules();
    const tf = modules.find((m) => m.id === 'terraform');
    expect(tf).toMatchObject({ skill: 'terraform', lessonsCount: 3, totalMinutes: 55 });
    expect(tf!.icon).toBeTruthy();
  });

  test('les leçons viennent des fichiers du module : cours, QCM avec réponses et TP', async () => {
    const lesson = await api.getLesson('tf2');
    expect(lesson.module_id).toBe('terraform');
    expect(renderLesson(lesson.body_md)).toContain('<strong>');
    expect(renderLesson(lesson.body_md)).toContain('class="key"');
    expect(lesson.qcm.map((q) => q.id)).toEqual(['tf2_q_contrat', 'tf2_q_doc', 'tf2_q_obligatoire']);
    expect(lesson.tp).toMatchObject({ id: 'tf2_tp', total_hints: 3 });
  });

  test('les indices sont ceux du TP, par niveau', async () => {
    const first = await api.getTpHint('tf1_tp', 1);
    const third = await api.getTpHint('tf1_tp', 3);
    expect(first.hint).toMatch(/bloc terraform/);
    expect(third.hint).toMatch(/resource "local_file" "hello"/);
    expect(third.level).toBe(3);
  });

  test('la quête avance de leçon en leçon quand les étapes sont terminées', async () => {
    await api.switchModule('terraform');
    const first = await api.getQuest(30);
    expect(first.profile.active_module_id).toBe('terraform');
    expect(first.steps.map((s) => s.lesson_id)).toEqual(['tf1', 'tf1', 'tf1']);

    for (const kind of ['lesson', 'qcm', 'tp']) await api.completeStep(kind, 'tf1');
    const second = await api.getQuest(30);
    expect(second.steps.map((s) => s.lesson_id)).toEqual(['tf2', 'tf2', 'tf2']);
  });
});
