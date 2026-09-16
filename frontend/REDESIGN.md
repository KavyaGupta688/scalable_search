# Nexus frontend redesign

Implemented on `Feature/Re-designed-frontend`. The starting uncommitted work was retained; this redesign does not change the backend, authentication service, route guards, route paths, or the original mock-data collection.

## Design

- Dark navy foundation with royal blue, periwinkle, and pale blue accents from the supplied palette.
- Bricolage Grotesque headings and DM Sans text, loaded through Google Fonts with system fallbacks.
- Shared palette tokens in `src/index.css`, exposed through Tailwind; shared layouts and component styling in `src/redesign.css`.
- Reusable branding, authentication layout, panels, buttons, and headings in `src/components/DesignSystem.jsx`.
- All 13 active routes restyled. Admin navigation supports an expanded sidebar, icon rail, and mobile drawer. Existing legacy frontend files remain available.
- Dialogs support focus containment, Escape dismissal, and focus restoration. Reduced-motion preferences are respected.

## Public experience simplification

- The landing page focuses on finding, previewing, and downloading datasets. Its hero and popular-dataset cards reference the original shared mock records, with accessible metadata previews and existing sign-in links.
- Removed the technical architecture, interactive demonstration, infrastructure, and promotional capability sections, along with their unused state, separate demo records, icons, and styles.
- Removed orbital artwork and decorative mini headings across active routes. Authentication panels use a simple gradient and concise copy; operational labels and status information remain in the workspace.
- Checked all 13 active routes at 1440px, 834px, and 390px with no page-level overflow. Live user/admin login and redirects passed. The live catalog returned an empty result, so controlled unavailable-API responses were used to verify prototype search/filtering, file previews, selection, and download-history completion without a fabricated archive.
- Landing preview dialogs were checked for focus containment, Escape dismissal, and focus restoration. Existing build and six service regression checks pass.

## Navigation cleanup

- Landing navigation uses centered “Why Nexus” and “Discover datasets” links. The final action is one rounded “Start exploring” button to user login; the footer admin link is removed.
- Landing carousels advance one card every five seconds through five hero records and six popular records. Hero cards slide downward, growing from 90% to full size in the middle and shrinking as they leave. Hover lets an active hero slide finish before pausing with three complete cards; keyboard focus settles it immediately without removing the focused card. Popular cards slide right to left and also finish the current slide before pausing on hover, showing three complete cards on desktop, two on tablets, and one on phones. Open previews pause both tracks, and reduced-motion preferences disable movement while retaining the larger middle hero card. There are no play/pause buttons. Offscreen cards cannot receive keyboard focus. Verified scaling, completed-slide hover pause, previews, CTA destination, and overflow from 320px through desktop widths.

- The sidebar logo toggles expanded and compact navigation. Its contents scroll independently below the fixed logo, keeping every module and sign-out reachable in short windows and the mobile drawer.
- Removed the admin breadcrumb/environment/search strip and decorative status/navigation dots. Mobile retains an accessible Menu button; status labels use DM Sans.
- Workspace Home links and the user header's landing-page logo link have been removed. Signed-in visitors who open the landing page directly can return through Back to workspace without losing their session. Catalog actions route to the appropriate authenticated workspace.
- Verified scrolling at 450px desktop/tablet heights, a 520px mobile drawer, keyboard dismissal/focus restoration, collapse/expand, both roles' Home/reload/return flows, and no horizontal overflow from 320px through 1538px.

## Dialog and sidebar scrolling

- All six dialog types render outside animated page containers, centered in the viewport with constrained height and scrollable content. Connector forms keep their header and actions visible while the fields scroll.
- Hidden sidebar scrollbars preserve wheel, touch, and keyboard scrolling. Removed the prototype workspace message box.
- Checked all six dialogs at desktop, tablet, and phone sizes for centering, reachable bottom actions, and overflow. Confirmed wheel scrolling, background scroll locking, focus containment, Escape dismissal, and focus restoration. Production build and all six regression tests pass.

## Prototype service behavior

- Offline search now awaits the mock service and maps its actual record fields, filters, result count, and limit correctly.
- New fallback connectors survive list refreshes and navigation within the current browser session; they intentionally do not persist across a full reload.
- Download initiation and status updates share the existing `nexus_downloads` store. Existing history is retained. Prototype completion without an archive URL is clearly labelled, and unavailable real-job status is not converted into simulated success.

## Verification

From this directory:

```sh
npm run dev
npm run build
npm test
```

Six regression tests cover successful/offline search, connector retention, prototype/real download history, and unavailable download status.

Browser checks use isolated, controlled API fixtures. They cover user/admin login, registration validation, role redirects, search/filtering, previews/bookmarks, batch selection, download lifecycle states, connector forms, ingestion details, enrichment, audit CSV export, user creation, sidebar controls, and keyboard dialog behavior.

All 13 routes were checked at 1440px, 834px, and 390px widths. Production storage transfers, real archive generation, and unfinished backend adapters remain outside this frontend redesign. Authentication still requires the existing backend. Browser fixture accounts and responses are test-only and are not included in the application.
