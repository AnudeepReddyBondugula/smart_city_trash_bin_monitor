# Feature Documentation

`docs/features/` contains a mixture of current infrastructure notes and planned
platform designs. The only implemented application service in this repository
is `services/data-simulator/`; BinVault, UrbanAPI, and CityScope documents
describe intended future components unless their code is added later.

## Documents currently present

| Area | Status | Entry point |
|---|---|---|
| Data simulator / BinForge | Implemented; operational instructions live in the root README | [`../../README.md`](../../README.md) |
| Docker Compose | Implemented infrastructure | [`DockerCompose/dockercompose_readme.md`](DockerCompose/dockercompose_readme.md) |
| BinVault | Design documentation only | [`binvault/00-BinVaultOverview.md`](binvault/00-BinVaultOverview.md) |
| UrbanAPI | Design documentation only | [`UrbanAPI/urbanapi_readme.md`](UrbanAPI/urbanapi_readme.md) |
| CityScope | Design documentation only | [`CityScope/cityscope_readme.md`](CityScope/cityscope_readme.md) |

Do not infer that a service, API route, migration, or deployment exists solely
because it appears in a design document. Verify it against tracked code and
`docker-compose.yml`.
