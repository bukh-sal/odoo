# Shared interface foundation, first implementation

The owner accepted the roomier Meridian study on 14 November 2026 and restored
the contextual sidebar to 264 px for long destinations. Use a 44 px data row,
26/34 px page title, 34 px actions and 36 px search control. Reserve shortcut
reminders for on-demand help or the command palette. Keep search visible.

1. Ship a small, application-independent presentation layer in the backend web
   bundle. Share typography, surfaces, controls, focus, sidebar width and row
   rhythm with native list/form views. Retain field rendering and native search.
2. Use one shared filter disclosure in Workboard. Expose an active count and
   labelled fields, keep grouping/sort distinct from filtering, and preserve
   the server query, navigation state and mobile navigation. Adopt the same
   heading, surface, control and sidebar rules in Documents.
3. Compile the actual assets, exercise existing application checks, and inspect
   native and custom views at desktop and narrow widths. Create a separate
   disposable cohort for installed checks and leave the accepted demos available.
   Record observed results and any remaining work before the next shell phase.

Scope is presentation. The full navigation rail, workspace transitions and
remaining application-specific panels have their own later implementation plans.
