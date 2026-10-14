# Demo Checklist

For showing GradePulse to a school or an investor. The pitch is simple: teachers already give weekly tests; GradePulse shows every week who is falling behind in each subject, and produces the reports the school needs.

## Before the day

1. Use the offline bundle in `deploy/demo/` so the demo does not depend on venue internet. The night before, with internet: `./deploy/demo/run-demo.sh prepare`.
2. On the day: `./deploy/demo/run-demo.sh start`, then `./deploy/demo/run-demo.sh seed` on a fresh machine. This creates the two pilot schools in `deploy/pilot_schools.json`, 14 students each.
3. Enter two or three weeks of scores for one class before you arrive (Scores page, with test dates and names), so the dashboard, progress history and reports have something to show.
4. Open http://localhost:3000 and sign in once to check it works.

## What to show (about 10 minutes)

1. **Dashboard.** Pick a subject and a class: students assessed, needing help, on track, ahead. This is the core of the product.
2. **Scores.** Enter a test for a class in one sheet; return to the dashboard and see it counted.
3. **Progress.** One student's results over time, by subject, with the trend.
4. **Reports.** Print a class summary and a student progress sheet. Schools respond to the parent sheet.
5. **Settings.** Invite a teacher with a link; the school controls who joins.
6. **Privacy.** Sign in as the second pilot school: it sees only its own students, even with the same class names.

## What not to claim

- No "AI accuracy" or recommendation figures. Content suggestions are switched off in the product until schools have a content library and teachers can record whether a suggestion helped.
- No "Neural Score". It is an internal diagnostic and is not shown in the product.
- No usage or outcome numbers until a real pilot has produced them.

## After the demo

`./deploy/demo/run-demo.sh reset` wipes the demo data. Change the pilot passwords in `deploy/pilot_schools.json` before any real pilot.
