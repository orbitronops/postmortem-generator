# Security

## What the generator can do

- Read an incident JSON file (and optionally a triage audit log) you give it.
- Print a postmortem (Markdown or JSON), or write it to a file you name.

## What the generator cannot do

- It has no network access in the demo path.
- It cannot run `kubectl`, shell commands, or any mutating Kubernetes action.
- It stores no credentials. There is no place to put a token or API key in the demo.
- It cannot name or blame a person: action-item owners are roles, and the
  blameless wording is enforced by a test (`test_generated_postmortem_is_blameless`).

## Handling real incidents

Do not put real customer data, real incident logs with secrets, or real
people's names in an example or an issue in this repo. The sample incident
uses fictional service and team names only.

## Reporting a problem

Open an issue in this repo. Do not include real cluster credentials or real
customer data in any issue or example.
