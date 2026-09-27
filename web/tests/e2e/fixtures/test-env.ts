import { test as base, Page, expect } from '@playwright/test';
import { execSync } from 'child_process';
import * as path from 'path';
import { getE2EAuthToken, authenticatePage, E2E_USER } from './auth';
import type { AnomalyItem, BenchmarkResultItem, InvariantResultItem } from '../reporters/accuracy-reporter';

export interface TestUserContext {
  id: number;
  email: string;
  token: string;
}

export interface AuditStoreInterface {
  recordBenchmark: (item: BenchmarkResultItem) => void;
  recordAnomaly: (anomaly: AnomalyItem) => void;
  recordInvariant: (invariant: InvariantResultItem) => void;
  recordGap: (gap: { id: string; severity?: 'P0' | 'P1' | 'P2' | 'P3'; category?: string; title: string; details: string; component?: string }) => void;
}

export interface AdamHubFixtures {
  authedPage: Page;
  testUser: TestUserContext;
  resetTestData: () => void;
  auditStore: AuditStoreInterface;
}

export const test = base.extend<AdamHubFixtures>({
  testUser: async ({}, use) => {
    const authData = await getE2EAuthToken();
    await use({
      id: authData.userId,
      email: E2E_USER.email,
      token: authData.token,
    });
  },

  resetTestData: async ({}, use) => {
    const reset = () => {
      try {
        const repoRoot = path.resolve(process.cwd(), '..');
        execSync('uv run python scripts/seed_e2e_tenant.py', {
          cwd: repoRoot,
          stdio: 'pipe',
          timeout: 15000,
        });
      } catch (err) {
        console.warn('resetTestData failed:', err);
      }
    };
    await use(reset);
  },

  auditStore: async ({}, use) => {
    const info = test.info();
    const store: AuditStoreInterface = {
      recordBenchmark: (item: BenchmarkResultItem) => {
        info.annotations.push({
          type: 'benchmark',
          description: JSON.stringify(item),
        });
      },
      recordAnomaly: (anomaly: AnomalyItem) => {
        info.annotations.push({
          type: 'anomaly',
          description: JSON.stringify(anomaly),
        });
      },
      recordInvariant: (invariant: InvariantResultItem) => {
        info.annotations.push({
          type: 'invariant',
          description: JSON.stringify(invariant),
        });
      },
      recordGap: (gap) => {
        info.annotations.push({
          type: 'anomaly',
          description: JSON.stringify({
            anomalyId: gap.id,
            severity: gap.severity || 'P2',
            category: gap.category || 'Missing Feature / UI Gap',
            title: gap.title,
            details: gap.details,
            reproductionJourney: gap.component || 'UI Inspection',
          }),
        });
      },
    };
    await use(store);
  },

  authedPage: async ({ page, testUser, auditStore }, use) => {
    // Attach error and performance listeners
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        const text = msg.text();
        if (!text.includes('favicon.ico') && !text.includes('React Router') && !text.includes('Download the React DevTools')) {
          auditStore.recordAnomaly({
            anomalyId: `CONSOLE-${Math.random().toString(36).substring(2, 7).toUpperCase()}`,
            severity: 'P2',
            category: 'Frontend Console Error',
            title: 'Uncaught Console Error',
            details: text.slice(0, 300),
            reproductionJourney: page.url(),
          });
        }
      }
    });

    page.on('requestfailed', (req) => {
      const url = req.url();
      if (!url.includes('favicon') && !url.includes('.map')) {
        auditStore.recordAnomaly({
          anomalyId: `NET-${Math.random().toString(36).substring(2, 7).toUpperCase()}`,
          severity: 'P1',
          category: 'Network Failure',
          title: `Request failed: ${req.method()} ${url}`,
          details: req.failure()?.errorText || 'Failed to fetch',
          reproductionJourney: page.url(),
        });
      }
    });

    const requestStartTimes = new Map<string, number>();
    page.on('request', (req) => {
      requestStartTimes.set(req.url(), Date.now());
    });

    page.on('requestfinished', (req) => {
      const start = requestStartTimes.get(req.url());
      if (start) {
        const duration = Date.now() - start;
        if (duration > 3000) {
          auditStore.recordAnomaly({
            anomalyId: `SLOW-${Math.random().toString(36).substring(2, 7).toUpperCase()}`,
            severity: 'P3',
            category: 'Performance Regression',
            title: `Slow request (>3s): ${req.url()}`,
            details: `Completed in ${duration}ms`,
            reproductionJourney: page.url(),
          });
        }
        requestStartTimes.delete(req.url());
      }
    });

    // Injects auth token
    await authenticatePage(page, testUser.token);

    await use(page);
  },
});

export { expect };
