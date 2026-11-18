# PR reviews

OpenCode inspects requested PR changes and posts a code review as a PR comment.
This setup is ported from [eth-cscs/alps-extended-images](https://github.com/eth-cscs/alps-extended-images/tree/main/.github/review), whose README documents the design in full.
PR content is untrusted, so model execution is separated from GitHub authorization and publication.
The reviewer does not execute PR code or tests, modify the checkout, or publish anything itself.

## Request a review

Post a new top-level comment in the PR's Conversation tab:

```text
/oc-review Focus on the scheduler client error handling.
```

- Reviews are on demand only; opening or updating a PR does not trigger one.
- Same-repository and fork PRs are supported.
  Inline diff comments and edits to existing comments do not trigger reviews.
- The command is case-insensitive, and request text is optional.
- The requester must have repository write access (write, maintain or admin).
- An `eyes` reaction confirms acceptance, not completion.
- A `confused` reaction indicates a failure, including a timeout.
  Re-run the failed jobs from the Actions tab, or post a new command.
- After updating the PR, post another command to review the new head.
  A newer authorized request cancels the earlier review for the same PR.

## Workflow and trust boundaries

The [caller workflow](../workflows/opencode-review.yml) validates the command and the author's write access, then calls the [worker workflow](../workflows/opencode-review-worker.yml) from `master`.

| Job | Responsibility | GitHub token permissions |
| --- | --- | --- |
| `authorize` | Validate the request before starting the worker | `contents: read` |
| `acknowledge` | React to the accepted request | `pull-requests: write` |
| `review` | Recheck access, prepare context, run the container, and extract review text | `contents: read`, `pull-requests: read` |
| `finish` | Publish a successful review or report failure on the request | `pull-requests: write` |

The write-enabled jobs have no source checkout, inference key, or model process, and the model never receives a GitHub token.
Workflows, host helpers, configuration and instructions are always loaded from the default branch (`master`), so PR changes to them are review material and do not affect the review that runs on that PR.

- [host/context.py](host/context.py) resolves the PR head through the API, verifies the checkout, and renders metadata, the merge-base diff and the review history collected by [host/history.py](host/history.py).
- [host/run.py](host/run.py) runs the reviewer container with a read-only root filesystem, dropped capabilities, read-only input mounts and only `CSCS_INFERENCE_API_KEY` forwarded.
- [host/extract.py](host/extract.py) keeps only the final review text, excluding reasoning and tool output.
- The `finish` job skips publication if the PR head moved since the reviewed commit.

## Layout

| Location | Role |
| --- | --- |
| [`host/`](host/) | Python helpers executed on the GitHub runner; tests in `host/tests/` |
| [`config/opencode.json`](config/opencode.json) | Model, provider, agents, permissions and generation settings |
| [`config/limits.json`](config/limits.json) | Inspection and finalization deadlines |
| `CONTRIBUTING.md` (repository root) | Repository guidance given to the reviewer, mounted as `/instructions/AGENTS.md` |

Configuration changes on `master` apply to later reviews without rebuilding anything.

## Reviewer image

The container image, including the reviewer policy (`grumpy-reviewer.md`) and phase runner, is built and published by alps-extended-images.
The worker pins it by digest in `OPENCODE_REVIEW_IMAGE`; it is pulled anonymously from GHCR.
To pick up a new image, copy the digest pin from alps-extended-images' `opencode-review-worker.yml`.
Update `config/` and `host/` from the same alps-extended-images commit at the same time, because the configuration format and event protocol must match the image.

## Deployment

Provide the repository or organization secret `CSCS_INFERENCE_KEY`.
The worker exposes it only to the inference step as `CSCS_INFERENCE_API_KEY`.
The caller, worker, host helpers and configuration must be on `master` for reviews to run.

## Local checks

```bash
pytest -c /dev/null --rootdir . .github/review/host/tests
```

The `test_cleanup_timeout_preserves_failure_and_checks_source` cases assume `/bin/false` exists, so they fail on macOS but pass on Linux CI.
