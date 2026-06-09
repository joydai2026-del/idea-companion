# Notion Demo Runbook

## Positioning

This is a Notion product demo, not an AI voice demo.

The claim:

> Notion can be the memory layer and operating surface for a personal AI product.

Idea Companion proves that with one loop:

Voice conversation -> Notion Conversation row -> Notion Report request -> Modal worker writes a teaching workspace -> Telegram links back to Notion.

## What To Show

| Moment | Screen | Why it matters |
|---|---|---|
| Start | Notion dashboard | Notion is the product home, not the afterthought. |
| Talk | Telegram Mini App | Capture happens when JJ is walking and cannot type. |
| Save | In-app note and Telegram ping | A voice command becomes structured Notion work. |
| Organize | Conversations DB | Notion stores the raw memory. |
| Produce | Reports DB | Notion tracks requested, in progress, and ready learning artifacts. |
| Read | Finished report page | Notion becomes the study surface with mission, concept cards, glossary candidates, practice loop, quiz, citations, and images. |

## Notion Page Structure

For the cleanest demo, the Notion page should have four visible sections:

1. Today on a walk
   - A linked view of recent Conversations.
   - Sort newest first.
   - Show Title, Date, Summary, Language, Requests.

2. Reports to read
   - A linked view of Reports.
   - Group or filter by Status.
   - Show Topic, Type, Status, Created, Depth.

3. Learning memory
   - A compact gallery of finished reports.
   - Use Topic as the card title.
   - Use cover images when available.
   - Open one report and show the mission tie-in, concept cards, glossary candidates, practice loop, learning record, and quiz questions.

4. Demo control panel
   - Live app URL.
   - Health URL.
   - Telegram bot name.
   - One checkbox list for pre-demo checks.

## Critical Checks Before Demo

| Check | Pass means |
|---|---|
| Tutor health endpoint returns ok | Modal app is awake and has OpenAI config. |
| Health shows Notion DBs present | The app can write Notion rows. |
| Health shows auth enforced | The Mini App is private to JJ. |
| Telegram opens the Mini App | Phone-first path works. |
| End session creates a Conversation row | Notion receives the walk memory. |
| Report request creates a Report row | Voice command becomes structured work. |
| Report row becomes Ready | Worker completed the Notion artifact. |
| Telegram ping includes Notion link | Walk-to-desk handoff works. |
| Finished report has mission, concept cards, glossary, practice, and quiz | The product teaches and helps JJ retain, not just capture notes. |

## Critical Feedback

Do not lead with "this is a realtime voice tutor." That makes Notion feel replaceable.

Lead with:

> Notion is the database, dashboard, and reading surface. The voice agent is just the capture layer for when I am walking.

Also avoid showing the repo first. Show Notion first, then Telegram, then back to Notion.

## Fallback Demo

If live voice fails:

1. Show the Notion dashboard.
2. Show a previously created Conversation page.
3. Show a Report row.
4. Open a finished report with sources and image.
5. Show the concept cards and quiz.
6. Say: "The live capture layer is phone-dependent. The Notion product loop is the important part."

## Fancy Demo Upgrade

The strongest version of the demo is a two-minute transformation:

1. Start on the Notion dashboard and show the Reports board grouped by Status.
2. Ask the voice tutor for a deep report with pictures.
3. End the session.
4. Watch a new Conversation page and Report page appear.
5. Open the Report page after it flips to Ready.
6. Point to the finished artifact sections: mission tie-in, 5-bullet summary, walking explanation, concept cards, glossary candidates, practice loop, learning record, quiz, sources, image.
7. Close by saying: "The voice agent captures the moment. Notion turns it into memory, teaching, practice, and retrieval."

## Teach Skill Pattern

This demo borrows the best part of Matt Pocock's `teach` skill: learning should be stateful. A good teaching workspace has a mission, trusted resources, reference material, learning records, and tight feedback loops.

For Idea Companion, the Notion version is:

- Mission tie-in: why this topic matters to JJ.
- Trusted resources: current sources worth revisiting.
- Concept cards: the raw units of future lessons.
- Glossary candidates: terms to promote only after JJ can use them.
- Learning record: what changed in JJ's understanding.
- Practice loop: a tiny exercise with feedback criteria.
- Quiz: active recall for later.
