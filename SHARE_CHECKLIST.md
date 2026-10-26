# Share checklist

Before copying, publishing, or archiving this package:

- [ ] `python scripts/article_to_audio.py --config config.example.json --validate-only` succeeds.
- [ ] `python -m unittest discover -s tests -v` succeeds without network access.
- [ ] No real credential, token, Authorization value, private endpoint, account/quota detail, or credential file is included.
- [ ] No private article/source, generated audio, local config, or run output is included.
- [ ] No machine-specific absolute path, home directory, user name, or agent/harness dependency is included.
- [ ] Example models, voices, styles, endpoints, and sources are clearly placeholders or public fixtures.
- [ ] `SKILL.md`, `README.md`, `config.example.json`, `scripts/`, `tests/`, `LICENSE`, and this checklist are present.
- [ ] The archive opens into one `article-to-audio/` directory and preserves UTF-8 file names/content.
- [ ] A secret-pattern scan and an absolute-path scan both return no findings requiring action.
