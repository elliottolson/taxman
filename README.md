# Taxman

**Know what you owe. Understand why.**

Taxman is a free U.S. federal tax estimator being built to make personal taxes easier to understand. The goal is simple: enter your income, see how your tax is calculated, and explore how a change would affect your estimate.

## Project status

Taxman is in early development. This repository currently contains the product roadmap, architecture plans, and illustrative rule examples. A working calculator is not available yet.

## What we're building

The first version will focus on:

- **W-2 income:** wages and federal income tax withheld.
- **1099-INT:** interest income.
- **1099-DIV:** dividends and straightforward capital-gain distributions.
- **Filing status and the standard deduction.**
- **Federal tax estimates:** liability, payments, and an estimated refund or remaining balance.

Support will expand as each tax situation is researched, implemented, and verified. The calculator will identify situations it cannot yet handle so you can understand the limits of an estimate.

## Make the numbers make sense

You should be able to see where a result came from. Taxman is being designed to show the inputs, calculation steps, assumptions, and official sources behind an estimate.

Scenario comparisons will let you explore questions such as how additional interest income or a change in wages affects your taxes. Saved scenarios will let you continue on another browser or computer.

## Free, with privacy built in

Calculations and explanations will be free. Your financial information deserves careful handling: the design calls for private accounts, secure storage, clear document-retention choices, and controls to export or delete saved information.

These are product commitments and design requirements; the account and storage systems have not been implemented yet.

## Follow the project

See the [roadmap](docs/product-roadmap.md) for the planned milestones and initial supported situations.

For participation, see [Contributing](CONTRIBUTING.md). Report sensitive security issues through the [security policy](SECURITY.md).

For the technical design, start with the [development plan](docs/README.md):

- [Tax rules and calculations](docs/rule-system.md)
- [Sources and rule updates](docs/sources-and-imports.md)
- [Data and security](docs/data-and-security.md)
- [Implementation plan](docs/implementation-plan.md)

If you're exploring the repository, the examples are illustrative design artifacts, not validated tax calculations. Please use synthetic information when discussing examples or reporting issues; keep personal financial documents out of public submissions.

## About the name

Taxman takes its name from [“Taxman” by the Beatles](https://www.thebeatles.com/taxman), written by George Harrison and released on *Revolver* in 1966.
