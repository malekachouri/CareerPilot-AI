import Link from "next/link";

const MODULES = [
  { name: "Interview Tests Hub", text: "Licensed question banks, timed tests and your private test notes.", phase: 1 },
  { name: "AI Interview Coach", text: "Explanations, grading and mock interviews on a local LLM.", phase: 2 },
  { name: "Global Job Radar", text: "Jobs from official APIs and public ATS boards, with alerts.", phase: 3 },
  { name: "Coding & DevOps Challenges", text: "Sandboxed code, Kubernetes, IaC and CI/CD scenarios.", phase: 4 },
  { name: "Career Analytics", text: "Skill ratings, weaknesses and an interview readiness score.", phase: 5 },
  { name: "English Academy", text: "Speaking, listening, reading, writing and technical English.", phase: 6 },
];

export default function Home() {
  return (
    <div className="space-y-12">
      <section className="space-y-4">
        <h1 className="text-4xl font-bold tracking-tight">Prepare interviews. Find jobs. Keep growing.</h1>
        <p className="max-w-2xl text-lg text-muted">
          CareerPilot AI is a self-hosted platform for DevOps, Cloud and AI engineers. It runs on free and
          open-source software, including local AI models.
        </p>
        <div className="flex gap-3">
          <Link
            href="/register"
            className="rounded-md bg-accent px-4 py-2 font-medium text-accent-foreground hover:opacity-90"
          >
            Create an account
          </Link>
          <Link href="/login" className="rounded-md border border-border px-4 py-2 font-medium hover:bg-surface">
            Log in
          </Link>
        </div>
      </section>

      <section aria-labelledby="modules" className="space-y-4">
        <h2 id="modules" className="text-xl font-semibold">
          Modules
        </h2>
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {MODULES.map((m) => (
            <li key={m.name} className="rounded-lg border border-border bg-surface p-4">
              <p className="font-medium">{m.name}</p>
              <p className="mt-1 text-sm text-muted">{m.text}</p>
              <p className="mt-3 text-xs font-medium text-accent">Planned for phase {m.phase}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
