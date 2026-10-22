# GitHub repository metadata

Record of what is set on the GitHub repository itself (description, topics,
release), kept here so the value and its rationale survive independently of
whoever last had `gh` access. Update this file in the same commit as any
change made via `gh repo edit` / `gh release create`.

- Description: Claude Code skill for writing and reviewing academic papers and theses (Arabic + English) with integrity enforced by scripts: verified sources, quotes with pages, numbers audited against real analysis output. All free APIs.
- Topics: `academic-writing`, `arabic`, `claude-code`, `claude-skills`, `crossref`, `openalex`, `research`
- Release tag: `v1.0.0`
- Release title: `Research Paper Assistant 1.0.0: first public release with script-enforced sources, quotes and numbers`
- Social preview: `assets/readme/social-preview.png`, not uploaded yet (Settings > General > Social preview)
- Counted facts in README badges: scripts = 18, from `git ls-files 'scripts/*.py' | wc -l` on 2026-10-22

## Change log for this file

- 2026-10-22: Initial record for the v1.0.0 release. Description and topics are the values already set on GitHub, read with `gh repo view supportefy-dev/research-paper-assistant --json description,repositoryTopics`: the description names the mechanism (integrity enforced by scripts) and the three checks (verified sources, quotes with pages, numbers audited against analysis output); the topics name the host (`claude-code`, `claude-skills`), the domain (`academic-writing`, `research`, `arabic`) and the two registries the scripts are built on (`openalex`, `crossref`). The release tag and title are chosen for the first public release; `gh release list` showed no release yet on this date. The script count of 18 is the number behind the README's `tools-18 scripts` badge and the `18 TOOLS` chip in `tools/readme-media/media.json`.
