const assert = require('node:assert/strict');
const { test } = require('node:test');
const needsBackendChecks = require('./backend-pre-commit.cjs');
const { needsBackendTests } = needsBackendChecks;

// Replace only the external API; test the real path decision.
function input(files, changedFiles = files.length) {
  return {
    context: {
      eventName: 'pull_request',
      repo: { owner: 'example', repo: 'audit' },
      payload: { pull_request: { number: 1815, changed_files: changedFiles } },
    },
    github: { rest: { pulls: { listFiles: {} } }, paginate: async () => files },
  };
}

for (const [name, files, expected] of [
  ['frontend only', [{ filename: 'src/frontend/page.vue' }], false],
  ['shared docs only', [{ filename: 'README.md' }], false],
  ['backend', [{ filename: 'src/backend/apps/api.py' }], true],
  ['backend tooling', [{ filename: 'agent/backend/tools/check.sh' }], true],
  ['workflow', [{ filename: '.github/workflows/pre-commit.yml' }], true],
  ['detector', [{ filename: '.github/scripts/backend-pre-commit.cjs' }], true],
  ['detector tests', [{ filename: '.github/scripts/backend-pre-commit.test.cjs' }], true],
  ['mixed', [{ filename: 'src/frontend/page.vue' }, { filename: 'src/backend/api.py' }], true],
  ['deleted backend', [{ filename: 'src/backend/old.py', status: 'removed' }], true],
  ['renamed out of backend', [{ filename: 'archive/old.py', previous_filename: 'src/backend/old.py' }], true],
  ['renamed into backend', [{ filename: 'src/backend/new.py', previous_filename: 'archive/new.py' }], true],
  ['similar directory is not backend', [{ filename: 'src/backend-extra/demo.py' }], false],
]) {
  test(name, async () => assert.equal(await needsBackendChecks(input(files)), expected));
}

test('backend beyond first API page is not missed', async () => {
  const files = Array.from({ length: 100 }, (_, n) => ({ filename: 'src/frontend/' + n + '.vue' }));
  files.push({ filename: 'src/backend/api.py' });
  assert.equal(await needsBackendChecks(input(files)), true);
});

test('incomplete API list conservatively runs checks', async () => {
  assert.equal(await needsBackendChecks(input([{ filename: 'README.md' }], 3001)), true);
});

test('API failure fails detection', async () => {
  const args = input([]);
  args.github.paginate = async () => { throw new Error('API unavailable'); };
  await assert.rejects(needsBackendChecks(args), /API unavailable/);
});

for (const eventName of ['push', 'workflow_dispatch']) {
  test(eventName + ' always runs without querying PR files', async () => {
    assert.equal(await needsBackendChecks({ context: { eventName } }), true);
  });
}

for (const [name, files, expected] of [
  ['frontend only', [{ filename: 'src/frontend/page.vue' }], false],
  ['renamed inside frontend', [
    { filename: 'src/frontend/new.vue', previous_filename: 'src/frontend/old.vue', status: 'renamed' },
  ], false],
  ['backend only', [{ filename: 'src/backend/apps/api.py' }], true],
  ['mixed', [{ filename: 'src/frontend/page.vue' }, { filename: 'src/backend/api.py' }], true],
  ['shared tooling', [{ filename: 'agent/shared/tools/check.sh' }], true],
  ['unittest workflow', [{ filename: '.github/workflows/unittest.yml' }], true],
  ['deleted backend', [{ filename: 'src/backend/old.py', status: 'removed' }], true],
  ['renamed into frontend', [
    { filename: 'src/frontend/page.vue', previous_filename: 'src/backend/old.py', status: 'renamed' },
  ], true],
  ['renamed out of frontend', [
    { filename: 'assets/sample.js', previous_filename: 'src/frontend/sample.js', status: 'renamed' },
  ], true],
  ['unknown rename source', [{ filename: 'src/frontend/page.vue', status: 'renamed' }], true],
  ['similar directory is not frontend', [{ filename: 'src/frontend-extra/page.vue' }], true],
  ['empty files', [], true],
]) {
  test('backend unit tests: ' + name, async () => {
    assert.equal(await needsBackendTests(input(files)), expected);
  });
}

test('backend unit tests run when the changed-file list is incomplete', async () => {
  const files = [{ filename: 'src/frontend/page.vue' }];
  assert.equal(await needsBackendTests(input(files, 3001)), true);
});

test('backend unit tests run when the changed-file API fails', async () => {
  const args = input([]);
  args.github.paginate = async () => { throw new Error('API unavailable'); };
  assert.equal(await needsBackendTests(args), true);
});

for (const eventName of ['push', 'workflow_dispatch']) {
  test('backend unit tests always run on ' + eventName + ' without querying PR files', async () => {
    assert.equal(await needsBackendTests({ context: { eventName } }), true);
  });
}
