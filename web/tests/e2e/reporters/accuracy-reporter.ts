import { Reporter, TestCase, TestResult, FullConfig, Suite } from '@playwright/test/reporter';
import * as fs from 'fs';
import * as path from 'path';

export interface AnomalyItem {
  anomalyId: string;
  severity: 'P0' | 'P1' | 'P2' | 'P3';
  category: string;
  title: string;
  details: string;
  reproductionJourney?: string;
  screenshotPath?: string | null;
}

export interface BenchmarkResultItem {
  benchmarkId: string;
  recipeName: string;
  store: string;
  strategy: string;
  ingredient: string;
  matchedProduct: string;
  priceText?: string;
  isAccurate: boolean;
  reason?: string;
}

export interface InvariantResultItem {
  item: string;
  action: string;
  initialStock: string;
  afterActionStock: string;
  revertedStock?: string;
  isPreserved: boolean;
}

export default class AccuracyReporter implements Reporter {
  private startTime: number = Date.now();
  private totalTests: number = 0;
  private passedTests: number = 0;
  private failedTests: number = 0;
  private benchmarks: BenchmarkResultItem[] = [];
  private anomalies: AnomalyItem[] = [];
  private invariants: InvariantResultItem[] = [];

  onBegin(config: FullConfig, suite: Suite): void {
    this.startTime = Date.now();
    this.totalTests = suite.allTests().length;
    this.benchmarks = [];
    this.anomalies = [];
    this.invariants = [];
  }

  onTestEnd(test: TestCase, result: TestResult): void {
    if (result.status === 'passed') {
      this.passedTests++;
    } else if (result.status === 'failed' || result.status === 'timedOut') {
      this.failedTests++;
      this.anomalies.push({
        anomalyId: `FAIL-${Math.random().toString(36).substring(2, 7).toUpperCase()}`,
        severity: 'P1',
        category: 'Test Assertion',
        title: `Test failed: ${test.title}`,
        details: result.error?.message || 'Unknown test failure',
        reproductionJourney: test.location.file,
      });
    }

    // Process annotations collected during the test worker execution
    for (const annotation of test.annotations) {
      if (annotation.type === 'benchmark' && annotation.description) {
        try {
          this.benchmarks.push(JSON.parse(annotation.description));
        } catch {
          // ignore malformed annotation
        }
      } else if (annotation.type === 'anomaly' && annotation.description) {
        try {
          this.anomalies.push(JSON.parse(annotation.description));
        } catch {
          // ignore malformed annotation
        }
      } else if (annotation.type === 'invariant' && annotation.description) {
        try {
          this.invariants.push(JSON.parse(annotation.description));
        } catch {
          // ignore malformed annotation
        }
      }
    }
  }

  onEnd(): void {
    const durationMs = Date.now() - this.startTime;

    const totalAudited = this.benchmarks.length;
    const accurateAudited = this.benchmarks.filter((b) => b.isAccurate).length;
    const accuracyRate = totalAudited > 0
      ? Math.round((accurateAudited / totalAudited) * 100)
      : (this.failedTests === 0 ? 100 : 0);

    const reportMarkdown = this.generateMarkdownReport({
      durationMs,
      accuracyRate,
      benchmarks: this.benchmarks,
      anomalies: this.anomalies,
      invariants: this.invariants,
    });

    const outputDir = path.resolve(process.cwd(), '../docs/audit');
    const rootDir = path.resolve(process.cwd(), '..');
    const targetFile = fs.existsSync(outputDir)
      ? path.join(outputDir, 'e2e-accuracy-report.md')
      : path.join(rootDir, 'docs/audit/e2e-accuracy-report.md');

    try {
      fs.mkdirSync(path.dirname(targetFile), { recursive: true });
      fs.writeFileSync(targetFile, reportMarkdown, 'utf-8');
      console.log(`\n\x1b[32m✔ Accuracy Audit Report generated at: ${targetFile}\x1b[0m`);
    } catch (e) {
      console.error('Failed to write accuracy report:', e);
    }
  }

  private generateMarkdownReport(data: {
    durationMs: number;
    accuracyRate: number;
    benchmarks: BenchmarkResultItem[];
    anomalies: AnomalyItem[];
    invariants: InvariantResultItem[];
  }): string {
    const dateStr = new Date().toISOString();
    const durationSec = (data.durationMs / 1000).toFixed(1);

    let md = `# E2E Browser Automation & System Accuracy Audit Report\n\n`;
    md += `**Execution Date**: ${dateStr}  \n`;
    md += `**Total Execution Time**: ${durationSec}s  \n`;
    md += `**Tests**: Total: ${this.totalTests} | Passed: ${this.passedTests} | Failed: ${this.failedTests}  \n`;
    md += `**Global Retail Accuracy Score**: **${data.accuracyRate}%**  \n\n`;

    md += `## 1. Executive Summary\n\n`;
    if (data.accuracyRate === 100 && this.failedTests === 0) {
      md += `> [!NOTE]\n> **STATUS: PASS (100% Accuracy)**  \n> All automated user journeys and canonical supermarket matching benchmarks passed with zero absurd substitutions.\n\n`;
    } else {
      md += `> [!WARNING]\n> **STATUS: ATTENTION REQUIRED**  \n> Accuracy rate is ${data.accuracyRate}%. Detected anomalies require attention.\n\n`;
    }

    md += `## 2. Supermarket Matching & Culinary Accuracy Benchmarks\n\n`;
    if (data.benchmarks.length === 0) {
      md += `*No supermarket matching benchmarks executed during this run (e.g. smoke run).*\n\n`;
    } else {
      md += `| Benchmark / Recipe | Store | Strategy | Ingredient | Matched Retail Product | Price | Status | Notes |\n`;
      md += `| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n`;
      for (const b of data.benchmarks) {
        const status = b.isAccurate ? '✅ PASS' : '❌ FAIL';
        md += `| ${b.recipeName} | ${b.store} | ${b.strategy} | ${b.ingredient} | ${b.matchedProduct} | ${b.priceText || 'N/A'} | ${status} | ${b.reason || 'Accurate'} |\n`;
      }
      md += `\n`;
    }

    md += `## 3. Pantry Inventory Invariants\n\n`;
    if (data.invariants.length === 0) {
      md += `*No pantry invariant tests executed during this run.*\n\n`;
    } else {
      md += `| Item | Action Tested | Initial Stock | Resulting Stock | Stock After Revert | Status |\n`;
      md += `| :--- | :--- | :--- | :--- | :--- | :--- |\n`;
      for (const inv of data.invariants) {
        const status = inv.isPreserved ? '✅ INVARIANT KEPT' : '❌ DRIFT DETECTED';
        md += `| ${inv.item} | ${inv.action} | ${inv.initialStock} | ${inv.afterActionStock} | ${inv.revertedStock || 'N/A'} | ${status} |\n`;
      }
      md += `\n`;
    }

    md += `## 4. Detected UI Gaps & Anomaly Catalog\n\n`;
    if (data.anomalies.length === 0) {
      md += `*Zero anomalies or gaps detected during this test run.*\n\n`;
    } else {
      md += `| ID | Severity | Category | Title | Details |\n`;
      md += `| :--- | :--- | :--- | :--- | :--- |\n`;
      for (const a of data.anomalies) {
        md += `| ${a.anomalyId} | **${a.severity}** | ${a.category} | ${a.title} | ${a.details.replace(/\n/g, ' ')} |\n`;
      }
      md += `\n`;
    }

    md += `## 5. Next Steps & Recommendations\n\n`;
    md += `- Run visual headed verification with \`npm run test:e2e:headed\` to observe browser interactions.\n`;
    md += `- Review any P0/P1 anomalies before deploying to production.\n`;
    md += `- Keep SupermarketSearchCache updated with genuine store products to ensure 100% matching fidelity.\n`;

    return md;
  }
}
