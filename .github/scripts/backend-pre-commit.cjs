function isBackendPath(path) {
  return path.startsWith('src/backend/') ||
    path.startsWith('agent/backend/') ||
    path === '.github/workflows/pre-commit.yml' ||
    path === '.github/scripts/backend-pre-commit.cjs' ||
    path === '.github/scripts/backend-pre-commit.test.cjs';
}

async function listPullRequestFiles({ github, context }) {
  const pr = context.payload.pull_request;
  const files = await github.paginate(github.rest.pulls.listFiles, {
    ...context.repo,
    pull_number: pr.number,
    per_page: 100,
  });

  // GitHub caps this endpoint at 3,000 files. Never skip on a partial list.
  return Number.isInteger(pr.changed_files) && files.length === pr.changed_files ? files : null;
}

module.exports = async function needsBackendChecks(input) {
  if (input.context.eventName !== 'pull_request') return true;

  const files = await listPullRequestFiles(input);
  return files === null || files.some(({ filename, previous_filename }) =>
    isBackendPath(filename) || (previous_filename && isBackendPath(previous_filename))
  );
};

function isFrontendPath(path) {
  return typeof path === 'string' && path.startsWith('src/frontend/');
}

module.exports.needsBackendTests = async function needsBackendTests(input) {
  if (input.context.eventName !== 'pull_request') return true;

  let files;
  try {
    files = await listPullRequestFiles(input);
  } catch {
    // Run the tests if GitHub cannot provide the changed-file list.
    return true;
  }

  return !files?.length || files.some(({ filename, previous_filename, status }) =>
    !isFrontendPath(filename) ||
    ((previous_filename !== undefined || status === 'renamed') && !isFrontendPath(previous_filename))
  );
};
