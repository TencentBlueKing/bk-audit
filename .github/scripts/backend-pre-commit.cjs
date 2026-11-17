function isBackendPath(path) {
  return path.startsWith('src/backend/') ||
    path.startsWith('agent/backend/') ||
    path === '.github/workflows/pre-commit.yml' ||
    path === '.github/scripts/backend-pre-commit.cjs' ||
    path === '.github/scripts/backend-pre-commit.test.cjs';
}

module.exports = async function needsBackendChecks({ github, context }) {
  if (context.eventName !== 'pull_request') return true;

  const pr = context.payload.pull_request;
  const files = await github.paginate(github.rest.pulls.listFiles, {
    ...context.repo,
    pull_number: pr.number,
    per_page: 100,
  });

  // GitHub caps this endpoint at 3,000 files. Never skip on a partial list.
  if (!Number.isInteger(pr.changed_files) || files.length !== pr.changed_files) return true;

  return files.some(({ filename, previous_filename }) =>
    isBackendPath(filename) || (previous_filename && isBackendPath(previous_filename))
  );
};
