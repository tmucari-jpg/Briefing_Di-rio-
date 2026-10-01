# Command Center Visual Inheritance

This project is managed under the Project Command Center Design System.

Source of truth:
- Command Center: docs/14_DESIGN_SYSTEM.md
- Project specification: docs/01_MASTER_SPEC.md

## Required inheritance

The project should inherit these principles:
- clear hierarchy
- system-first typography
- consistent spacing
- restrained surfaces and borders
- 44px minimum interactive targets
- visible keyboard focus
- responsive mobile experience
- reduced-motion support
- functional animation only
- primary actions visually distinct
- no decorative UI that competes with content

## Project identity

This project keeps its own brand, content, imagery and domain-specific visual language. Inheritance does not mean copying Apple or another product.

## Implementation rule

When modifying the UI, reuse the project's existing component layer where possible. New components should consume centralized tokens rather than hard-coded visual values.

Before release, perform a visual review against the Command Center Design System.
