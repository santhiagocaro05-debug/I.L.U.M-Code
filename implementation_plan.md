# Smart Home Side Panel Integration Plan

## Goal Description
Integrate the newly created `SmartHomeWidget` (glass‑styled side panel) into the main application UI so that users can control smart‑home devices from a persistent, visually premium lateral panel.

## User Review Required
> [!IMPORTANT]
> The panel will be added as a `QDockWidget` on the left side of the `MainWindow`.  This changes the layout hierarchy and may affect existing tab‑based navigation.  Please confirm that a dockable side panel is acceptable, or specify an alternative (e.g., embed directly in the central widget layout).

## Open Questions
> [!WARNING]
> - **Placement**: Should the panel be permanently visible, or toggleable via a toolbar button?
> - **Size**: Current `SmartHomeWidget` is 260‑300 px wide.  Does this fit comfortably with the existing UI on typical screens?
> - **Theme sync**: The widget uses `C_PANEL`, `C_TEXT`, and `C_PRI`.  Do we need to update any theme loading logic to ensure the panel respects user‑selected themes?

## Proposed Changes
---
### ui.py
- **Import** `SmartHomeWidget`.
- **Create** a `QDockWidget` (or embed directly) in `MainWindow.__init__` after the tab widget is set up.
- **Add** the dock widget to the left side: `self.addDockWidget(Qt.LeftDockWidgetArea, dock)`.
- **Add** a toggle action/button in the header to show/hide the smart‑home panel.
- **Apply** glass shadow via `apply_glass_shadow` (already handled inside the widget).

### ui_smart_home.py (minor)
- Ensure the widget’s `setMinimumWidth`/`MaximumWidth` align with the dock width.
- Optionally expose a method `refresh_devices` that can be called from the main window if needed.

### actions/smart_home.py (no change)
- Already provides `smart_home` function; ensure any needed imports are present.

## Verification Plan
### Automated Tests
- Run the application and verify the dock appears on the left with correct styling.
- Toggle visibility and ensure the rest of the UI resizes correctly.
- Click device toggles and confirm actions are sent without errors (mock backend).

### Manual Verification
- Launch the UI, interact with the Smart Home panel, and confirm glass‑morphism appearance matches other panels.
- Verify theme changes (gold, cyan, etc.) propagate to the side panel colors.
