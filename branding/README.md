# Event assets

This directory contains the curated web assets used by this Red Hat event,
not a mirror of the internal Brand Portal. Provenance is in `sources.json`.
The fonts have their own included SIL Open Font License texts. Red Hat marks
and artwork retain their owners' rights and are not relicensed by MIT.

The Open Tech Quest mark and code motif are original images from the event
organizer's supplied slide 5. The mark uses white lettering with transparent
areas, so place it on the event's indigo masthead. Do not reconstruct it from
typed text or alter the mark's proportions.

Public product technology icons are available for OpenShift, Ansible, RHEL,
and AI. Security uses the OpenShift product icon at the organizer’s request.
These remain separate from the generated room illustrations.

Add future selected web exports here, with provenance; never add raw private
catalogue archives, session data or credential-bearing download URLs. Room
theme settings can reference the resulting local plugin asset URLs without
changing room IDs, challenge sequence, starts or solve history.

## Generated room illustrations

`room-art/` contains five original architectural quest environments generated
with the built-in OpenAI image-generation tool in Codex. They are event
illustrations, not official Red Hat product artwork. The prompt set is in
`room-art/prompts.json`; provenance is listed in `sources.json`. Generated
illustrations and prompts are distributed under this repository's MIT license.
Official product marks, the event logo and fonts retain their separate notices.

Each room has a 1536px header WebP and a 640px card WebP. The browser chooses
the appropriate size; card artwork loads lazily. The same scene appears in
the lobby and room header. A room's **Hero image URL** overrides its bundled
illustration without changing challenge content, membership or timing.
