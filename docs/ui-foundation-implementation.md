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

## Using the foundation in an application

Core 0.2.7 loads the foundation through the backend web bundle. Use `.mp-page`
on the custom page and `.mp-page-title` on its heading. Use `--mp-ui-sidebar`
in a desktop grid and collapse navigation at the app's narrow breakpoint.
Treat `--mp-ui-row` as a minimum so wrapped labels and enlarged text can grow.
The locally packaged Geist face covers Latin. The font stack falls back to the
system UI for other scripts. Font and icon files stay off the network.

Import `QueryDisclosure` from `@web/interface/query_disclosure` in an Owl
component and register it in `static components`. Supply the translated label,
the number of active choices, and labelled controls through the default slot.
The caller owns query state, scope, pagination and refresh.

```xml
<QueryDisclosure label="'Filters'" count="activeFilterCount">
    <label>Priority
        <select t-model="state.priority" t-on-change="refresh">
            <option value="">All priorities</option>
            <option value="high">High</option>
        </select>
    </label>
</QueryDisclosure>
```

The summary opens with Enter or Space. Tab reaches the fields in order, Escape
returns focus to the summary, and choosing another control outside closes the
disclosure. Use the existing native search menu for a generated view. Keep
shortcut keycaps in the command palette or help, away from routine navigation.
