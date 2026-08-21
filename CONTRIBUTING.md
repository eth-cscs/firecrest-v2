# Contributing

Contributions to Firecrest are welcome and greatly appreciated. Proper credit will be given to contributors by adding their
names to the `CONTRIBUTORS.md` file. The copyright of Firecrest belongs to ETH Zurich, and external contributors are required to
sign a Contributor License Agreement; the development team will privately contact new contributors during their first
content submission.

## Contribution guidelines

### Submission

- When adding new features or fixing bugs not covered by existing tests, please also provide unit tests.
- Add an entry to the `CHANGELOG.md` file.
- If a change alters the API's or a cluster configuration's existing behavior in a way that is not backward compatible (e.g. a changed default value, a renamed/removed field, a different response shape), prefix the `CHANGELOG.md` entry with `***⚠️ API Breaking***` or `***⚠️ Configuration Breaking***` as appropriate, and describe how to preserve the previous behavior if possible.
- Submit your contributions as GitHub Pull Requests to the main public repository at https://github.com/eth-cscs/firecrest-v2 targeting `master` branch.
