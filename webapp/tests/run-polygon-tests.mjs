import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
const loadModule = createRequire(import.meta.url);
const output = mkdtempSync(join(tmpdir(), 'gravel-polygon-tests-'));
try {
  const compile = spawnSync(process.execPath, [loadModule.resolve('typescript/bin/tsc'),
    '--target', 'ES2022', '--module', 'commonjs', '--skipLibCheck', '--outDir', output,
    'app/lib/polygonStore.ts', 'app/lib/polygonEditing.ts'], { stdio: 'inherit' });
  if (compile.status !== 0) process.exitCode = compile.status || 1;
  else {
    const tests = spawnSync(process.execPath, ['tests/polygon-interactions.test.mjs'], {
      stdio: 'inherit', env: { ...process.env, POLYGON_TEST_BUILD_DIR: output },
    });
    process.exitCode = tests.status ?? 1;
  }
} finally {
  rmSync(output, { recursive: true, force: true });
}
