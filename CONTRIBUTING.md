# Contributing

Conventions for humans and agents. Short on purpose - follow it strictly.

## Branches

`main` is protected: changes land only through PRs with green CI.

| Prefix      | Use for                              | Example                    |
|-------------|--------------------------------------|----------------------------|
| `feat/`     | user-visible functionality           | `feat/search-pagination`   |
| `fix/`      | bug fixes                            | `fix/invite-expiry-check`  |
| `refactor/` | behaviour-preserving code changes    | `refactor/delivery-service`|
| `chore/`    | tooling, deps, config                | `chore/add-mypy`           |
| `ci/`       | GitHub Actions / deployment          | `ci/build-docker-image`    |
| `docs/`     | documentation only                   | `docs/adr-hosting`         |

## Commit messages - [Conventional Commits](https://www.conventionalcommits.org/)

```
<type>(<scope>): <imperative summary, ≤ 72 chars, no period>

<optional body: WHY the change was made, wrapped at 72>

<optional footer: Refs #12, BREAKING CHANGE: ...>
```

- **Types:** `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `chore`, `ci`, `build`
- **Scopes:** `bot`, `core`, `providers`, `db`, `config`, `infra`, `ci`, `docs`, `deps`
- Examples:
  - `feat(bot): paginate search results by editing the message`
  - `fix(providers): handle SoundCloud tracks without artwork`
  - `docs(adr): record decision to use PostgreSQL`
- You can always go outside of mentioned types and scope values if its more clear.

Full example with a body:

```
feat(core): de-duplicate concurrent downloads of the same track

Two friends tapping the same track within seconds triggered two
yt-dlp downloads and two uploads. The second request now awaits the
first one's future and reuses its Telegram file_id.

Refs #14
```

Commits inside a PR branch can be small and messy (`wip`, `fixup`) - they get squashed.
Only the PR title + description end up on `main`, so make those good.

## Pull requests

- One logical change per PR, ideally < ~400 changed lines.
- PR title = the Conventional Commit summary (it becomes the squash commit).
- Description follows [the PR template](.github/pull_request_template.md):
  **Summary** (what + why), **Changes** (bullet list), **How to test**,
  **Notes for reviewer** (anything non-obvious, trade-offs, follow-ups), **Checklist**.
- Write the description for someone reading `git log` a year from now.
- Merge strategy: **squash and merge** → `main` history is one clean commit per PR.
- Delete the branch after merge.

## Versioning & changelog

- [SemVer](https://semver.org/) tags: `v0.MINOR.PATCH` until the Mini App ships as `v1.0.0`.
- Each roadmap phase ends with a minor version tag.
- [`CHANGELOG.md`](CHANGELOG.md) follows [Keep a Changelog](https://keepachangelog.com/);
  every PR adds a line under `Unreleased`.

## Writing style

Applies to commits, PR descriptions, issues, docs and code comments.

- Use a plain hyphen `-`, never em/en dashes (`—`, `–`).
- No AI attribution: no "Generated with ...", no `Co-Authored-By` lines for tools.

## Code style

- Formatting and linting: `ruff`. Types: `mypy --strict`. No exceptions without a comment.
- Docstrings: Google style on public modules, classes, functions.
- Comments explain **why**; the code explains what.
- `TODO`s reference an issue: `# TODO(#12): support Bandcamp`.
- Tests mirror `src/` layout; name them `test_<behaviour>`.

### Comments & docstrings by example

```python
class DeliveryService:
    """Sends tracks to users as Telegram audio, reusing cached file_ids.

    Owns the download → upload → cache cycle so handlers never touch yt-dlp.
    """

    async def send(self, chat_id: int, track: Track) -> None:
        """Deliver ``track`` to ``chat_id``.

        Args:
            chat_id: Telegram chat to send the audio to.
            track: Track to deliver; must come from a provider search.

        Raises:
            TrackTooLongError: If the track exceeds the configured max duration.
        """
        # Telegram caps bot uploads at 50 MB; long DJ sets exceed it even at 128 kbps.
        if track.duration > self._max_duration:
            raise TrackTooLongError(track)
        ...
```

- ✅ `# Telegram caps bot uploads at 50 MB; ...` - explains a constraint you can't see.
- ❌ `# check if track is too long` - repeats the code.
- One-line docstrings are fine for small private helpers; skip `Args:` when obvious.

## Decisions

Significant or hard-to-reverse decisions get an ADR in `docs/adr/`
(copy `0000-template.md`, next number, status `Proposed` → `Accepted` on merge).
