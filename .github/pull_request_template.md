## Summary

- [ ] Public API behavior remains backward-compatible
- [ ] Private logic stays in `DotSoundPrivateCore`

## Boundary Checklist

- [ ] I did not hardcode internal bridge constants in public code
- [ ] I did not add secrets or privileged tokens to source files
- [ ] I updated boundary docs when changing public/private scope

## Verification

- [ ] Boundary policy check passed
- [ ] Tests relevant to the change passed

