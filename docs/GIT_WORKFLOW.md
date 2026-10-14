# 6D — local development and private GitHub

October 14, 2026. Arya created [aryamaan06/6D](https://github.com/aryamaan06/6D), and authenticated metadata confirmed it is private and writable. The existing 6d-startup folder is the local Git repository; branch `main`, remote `origin`. GitHub supplements this folder, not a separate codebase.

## Normal workflow

Continue editing and testing in this existing workspace with Codex. Review meaningful changes, commit a working increment, then push that commit to GitHub. Editing a local file alone does not upload it. Do not re-run GitHub's new-repository snippet or append another README title. Git Bash and PowerShell both support Git; the Python/setup instructions currently use PowerShell.

Codex handles staged-file review, commits, branch coordination and pushes for the authorized private build. Check Git status before starting parallel work. Other tools receive bounded assignments; a remote repository does not automatically synchronize simultaneous edits in this folder.

## Included and local-only files

Track source code, tests, constructed examples, package/setup files and useful development documentation. Founder planning remains private context. `.gitignore` excludes `.local/`, `.env*` (except a safe template), generated `work/` and `artifacts/`, Python caches and build environments. Never force-add those excluded paths. No model/API key is needed to clone or read the project code.

The persistent spending ledger is local-only; Git does not back it up. Do not delete or reset it to regain allowance, and do not enable another live-testing environment under the same cumulative approval without accounting for reservations already made. Run initial inference from the configured local machine.

The repository-local author identity uses Arya's GitHub username and account-ID no-reply email, without changing global Git settings. Sign in through Git Credential Manager privately if required; never paste a password or access token into chat or project files.

`.gitattributes` standardizes tracked text on LF line endings so checkouts preserve consistent source bytes across operating systems. Source fingerprints still detect actual changes. Older local evidence created before source-byte normalization remains historical evidence; matching-source reproduction must use its recorded source bytes or create a fresh review, not silently substitute the Git snapshot.

## Public submission later

The current repository is private. Prepare a reviewed public submission with every necessary submitted functionality, setup instructions, honest coverage and an appropriate open-source license. Review internal documents and history before public release. No license or public visibility change is implied by today's private repository connection.
