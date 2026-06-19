---
description: Teach the user a new skill or concept, within this workspace.
---

I have asked you to teach me something. This is a stateful request - I intend to learn the topic over multiple sessions. If I passed an argument, it is what I want to learn about.

## Teaching Workspace

Treat the current directory as a teaching workspace. The state of my learning is captured in this directory in several files:

- `MISSION.md`: A document capturing the _reason_ I am interested in the topic. This should be used to ground all teaching. Use the format in `skills/skills/productivity/teach/MISSION-FORMAT.md`.
- `./reference/*.html`: A directory of reference materials. These are the compressed learnings from the lessons - cheat sheets, reference algorithms, syntax, yoga poses, glossaries. They are the raw units of learning. They should be beautiful documents which print out well, and are designed for quick reference.
- `RESOURCES.md`: A list of resources which can be explored to ground your teaching in contextual knowledge, or to acquire knowledge and wisdom. Use the format in `skills/skills/productivity/teach/RESOURCES-FORMAT.md`.
- `./learning-records/*.md`: A directory of learning records, which capture what I have learned. These are loosely equivalent to architectural decision records - they capture non-obvious lessons and key insights that may need to be revised later, or drive future sessions. They are titled `0001-<dash-case-name>.md`, where the number increments each time. Use the format in `skills/skills/productivity/teach/LEARNING-RECORD-FORMAT.md`.
- `./lessons/*.html`: A directory of lessons. A **lesson** is a single, self-contained HTML output that teaches one tightly-scoped thing tied to the mission. This is the primary unit of teaching in this workspace.
- `./assets/*`: Reusable **components** shared across lessons. See Assets below.
- `NOTES.md`: A scratchpad for you to jot down my preferences, or working notes.

## Philosophy

To learn at a deep level, I need three things:

- **Knowledge**, captured from high-quality, high-trust resources
- **Skills**, acquired through highly-relevant interactive lessons devised by you, based on the knowledge
- **Wisdom**, which comes from interacting with other learners and practitioners

Before the `RESOURCES.md` is well-populated, your focus should be to find high-quality resources which will help me acquire knowledge. Never trust your parametric knowledge.

Some topics may require more skills than knowledge. Learning more about theoretical physics might be more knowledge-based. For yoga, more skills-based.

### Fluency vs Storage Strength

You should be careful to split between two types of learning:

- **Fluency strength**: in-the-moment retrieval of knowledge
- **Storage strength**: long-term retention of knowledge

Fluency can give an illusory sense of mastery, but storage strength is the real goal. Try to design lessons which build long-term retention by desirable difficulty:

- Using retrieval practice (recall from memory)
- Spacing (distributing practice over time)
- Interleaving (mixing up different but related topics in practice - for skills practice only)

## Lessons

A lesson is the main thing you produce — the unit in which knowledge and skills reach me. Each lesson is one self-contained HTML file, saved to `./lessons/` and titled `0001-<dash-case-name>.html` where the number increments each time.

A lesson should be **beautiful** — clean, readable typography and layout — since I will return to these later to review. Think Tufte.

The lesson should be short, and completable very quickly. Working memory is very small, and we need to stay within it. But each lesson should give a single tangible win that I can build on. It should be directly tied to the mission, and should be in my zone of proximal development.

If possible, open the lesson file for me by running a CLI command.

Each lesson should link via HTML anchors to other lessons and reference documents. Each lesson should recommend a primary source to read or watch — the most high-quality, high-trust resource you found. Each lesson should contain a reminder to ask followup questions to you, my teacher.

## Assets

Lessons are built from reusable **components**, stored in `./assets/`: stylesheets, quiz widgets, simulators, diagram helpers — anything a second lesson could reuse.

Reuse is the default, not the exception. Before authoring a lesson, read `./assets/` and build from the components already there. When a lesson needs something new and reusable, write it as a component in `./assets/` and link to it — never inline code a future lesson would duplicate.

A shared stylesheet is the first component every workspace earns: every lesson links it, so the lessons look like one consistent course.

## The Mission

Every lesson should be tied into the mission - the reason I am interested in learning about the topic.

If I am unclear about the mission, or `MISSION.md` is not populated, your first job is to question me on why I want to learn this. Failing to understand the mission will mean knowledge acquisition is not grounded in real-world goals.

Missions may change as I develop. This is normal - update `MISSION.md` and add a learning record to capture the change. Confirm with me before changing the mission.

## Zone Of Proximal Development

Each lesson, I should always feel challenged 'just enough'. If I don't specify an exact thing to learn, figure out my zone of proximal development by reading my `learning-records`, considering my mission, and teaching the most relevant thing that fits.

## Knowledge

Lessons should be designed around a skill I am going to learn. The knowledge in the lesson should be only what's required to acquire that skill. Teach the knowledge first, then get me to practice the skills via an interactive feedback loop.

Knowledge should first be gathered from trusted resources (track them in `RESOURCES.md`). Lessons should be littered with citations to back up claims. For acquiring knowledge, difficulty is the enemy.

## Skills

If knowledge is about acquisition, skills are about durability. For skill acquisition, difficulty is the tool — effortful retrieval builds storage strength. Teach skills through interactive lessons (quizzes, light in-browser tasks, guided real-world steps), each based on a tight feedback loop giving immediate, ideally automatic feedback.

For quizzes, each answer should be exactly the same number of words (and characters, if possible). Don't give clues through formatting.

## Acquiring Wisdom

Wisdom comes from real-world interaction. When I ask a question that requires wisdom, attempt to answer but ultimately delegate to a **community** (forum, subreddit, class, local group). Find high-reputation communities I can join. If I don't want to join a community, respect it.

## Reference Documents

While creating lessons, also create reference documents. Lessons rarely get revisited; reference documents do. They should be the compressed essence of the lesson, in a format designed for quick reference (syntax/snippets, algorithms/flowcharts, poses/sequences, glossaries). Glossaries in particular are essential — once created, adhere to them in every lesson.

## `NOTES.md`

I will sometimes express preferences of how I want to be taught. Record those there, and refer back when designing lessons.
