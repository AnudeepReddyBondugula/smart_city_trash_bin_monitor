# Smart City Trash Bin Monitor Documentation

Welcome to the official documentation for the **Smart City Trash Bin Monitor** project.

This documentation is organized into focused guides covering the system architecture, deployment, development workflows, testing, operations, and architectural decisions.

Whether you are a new contributor, developer, or reviewer, this documentation is intended to help you understand how the project is designed, how it operates, and how to contribute effectively.

---

# Documentation Structure

## Core Documentation

| Document                 | Description                                                                                          |
| ------------------------ | ---------------------------------------------------------------------------------------------------- |
| **architecture.md**      | High-level system architecture, component interactions, and data flow across the platform.           |
| **deployment.md**        | Deployment guides for Docker and Hybrid Local development environments.                              |
| **configuration.md**     | Environment variables, configuration files, and application settings.                                |
| **simulation-engine.md** | Detailed explanation of the AsyncIO simulation engine, scheduling strategy, and concurrency model.   |
| **database.md**          | PostgreSQL schema, data model, seeding process, and database design decisions.                       |
| **kafka.md**             | Kafka topics, producer architecture, message formats, and streaming workflow.                        |
| **testing.md**           | Unit testing strategy, pytest usage, fixtures, mocking, and testing guidelines.                      |
| **ci-cd.md**             | GitHub Actions workflows, branch policies, CI pipeline, and deployment automation.                   |
| **troubleshooting.md**   | Common development issues, debugging techniques, and known problems.                                 |
| **operations.md**        | Operational runbooks including starting services, seeding data, viewing logs, and maintenance tasks. |
| **project-structure.md** | Explanation of the repository layout and responsibilities of each directory.                         |
| **contributing.md**      | Development workflow, coding standards, branch naming conventions, and pull request process.         |

---

# Architecture Decision Records (ADRs)

The `decisions/` directory contains Architecture Decision Records (ADRs).

An ADR documents **why** a technical decision was made, the alternatives that were considered, and the long-term consequences of that decision.

Unlike implementation documentation, ADRs capture engineering rationale so future contributors understand the reasoning behind the architecture.

Current ADRs include:

| ADR                           | Description                                                                  |
| ----------------------------- | ---------------------------------------------------------------------------- |
| **001-asyncio.md**            | Why the simulator uses AsyncIO instead of threads or processes.              |
| **002-postgresql.md**         | Why PostgreSQL was selected as the persistence layer.                        |
| **003-kafka.md**              | Why Apache Kafka was selected as the event streaming platform.               |
| **004-simulation-manager.md** | Design decisions behind the Simulation Manager and task orchestration model. |

---

# Recommended Reading Order

For new contributors, the following reading order is recommended:

1. **architecture.md**
2. **project-structure.md**
3. **deployment.md**
4. **configuration.md**
5. **simulation-engine.md**
6. **database.md**
7. **kafka.md**
8. **testing.md**
9. **ci-cd.md**
10. **operations.md**
11. **contributing.md**

This sequence provides a gradual introduction, beginning with the overall system architecture before moving into implementation details and development workflows.

---

# Documentation Principles

The project documentation follows these principles:

* **Single Responsibility** – Each document focuses on one subject area.
* **Developer First** – Documentation is written for engineers working on the project.
* **Architecture Driven** – Design decisions are documented alongside implementation details.
* **Living Documentation** – Documentation should evolve alongside the codebase.
* **Production Mindset** – Operational procedures and deployment practices are documented as part of the project.

---

# Keeping Documentation Up-to-Date

Whenever introducing a significant change, contributors should update the relevant documentation.

Examples include:

* Adding or modifying services.
* Changing the deployment process.
* Introducing new environment variables.
* Updating database schemas.
* Creating new Kafka topics.
* Modifying CI/CD workflows.
* Making architectural decisions that affect future development.

If a change introduces a new architectural decision, consider adding a new Architecture Decision Record under the `decisions/` directory.

---

# Documentation Ownership

Documentation is considered part of the project's source code.

Pull requests that modify system behaviour should include corresponding documentation updates where applicable. Keeping documentation synchronized with the implementation ensures the project remains maintainable as it grows.
