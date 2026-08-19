## Description

Brief description of changes

## Type of Change

- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix/feature causing existing functionality to change)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)
- [ ] Performance improvement
- [ ] Test improvements
- [ ] Chore / Maintenance

## Related Issues

Closes #123
Relates to #456

## Changes Made

- 
- 
- 

## Testing

### Test Coverage

- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] UI tests added/updated
- [ ] Manual testing performed

### Test Results

```bash
# Paste test output here
pytest tests/ -v --tb=short
```

### Manual Testing Checklist

- [ ] Application starts without errors
- [ ] Document upload works
- [ ] Training can be initiated
- [ ] Inference works
- [ ] UI is responsive at 1080p/1440p/4K
- [ ] Theme switching works
- [ ] Settings persist across restarts

## Screenshots (if applicable)

| Before | After |
|--------|-------|
| ![before](url) | ![after](url) |

## Breaking Changes

If this is a breaking change, describe:
1. What breaks
2. Migration path
3. Deprecation timeline

## Checklist

- [ ] Code follows style guidelines (`ruff check src/ tests/`)
- [ ] Code is formatted (`ruff format src/ tests/`)
- [ ] Type checking passes (`mypy src/`)
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated (README, API docs, CHANGELOG)
- [ ] No sensitive data committed (keys, passwords, tokens)
- [ ] Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
- [ ] CHANGELOG.md updated (see [Keep a Changelog](https://keepachangelog.com/))
- [ ] Version bumped if applicable (patch/minor/major)

## Additional Notes

Any additional information, configuration, or data that might be necessary to reproduce or understand the changes.